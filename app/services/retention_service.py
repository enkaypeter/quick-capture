"""Permanent erasure and retention.

Blocker 11. Deleting a case previously only set `archived_at`, so the record
and its files stayed on disk indefinitely. That makes an Article 17 erasure
request impossible to satisfy and leaves special-category data with no end
date.

Two entry points:

* `purge_case` - immediate, deliberate destruction (an erasure request, or a
  record created in error)
* `purge_expired_cases` - the scheduled retention job

Both destroy the case, its child records, its audit and access log rows, and
its files on disk, then write an `ErasureLog` row. That row is the evidence
the destruction happened, so it holds counts and the case reference only -
never the data that was erased.
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import List, Optional

from app.extensions import db
from app.models.access_log import AccessLog
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.case_action import CaseAction
from app.models.case_attachment import CaseAttachment
from app.models.case_interaction import CaseInteraction, InteractionTag
from app.models.case_note import CaseNote
from app.models.erasure_log import ErasureLog
from app.models.follow_up_task import FollowUpTask

logger = logging.getLogger(__name__)

REASON_ERASURE_REQUEST = "erasure_request"
REASON_RETENTION_POLICY = "retention_policy"


@dataclass
class PurgeResult:
    case_identifier: str
    records_deleted: int = 0
    files_deleted: int = 0


@dataclass
class RetentionRunResult:
    """Summary of a scheduled retention run, for the operator's log."""

    cases_purged: List[PurgeResult] = field(default_factory=list)
    access_logs_pruned: int = 0
    login_attempts_pruned: int = 0

    @property
    def case_count(self) -> int:
        return len(self.cases_purged)


class RetentionService:
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder

    def purge_case(
        self,
        case: Case,
        reason: str,
        requested_by_user_id: Optional[int] = None,
    ) -> PurgeResult:
        """Permanently destroy a case, its children, its logs and its files."""
        result = self.destroy_case(case)

        entry = ErasureLog(
            case_identifier=result.case_identifier,
            requested_by_user_id=requested_by_user_id,
            reason=reason,
            records_deleted=result.records_deleted,
            files_deleted=result.files_deleted,
        )
        db.session.add(entry)
        db.session.commit()

        logger.info(
            f"Purged case {result.case_identifier}: {result.records_deleted} "
            f"record(s), {result.files_deleted} file(s), reason={reason}"
        )
        return result

    def destroy_case(self, case: Case) -> PurgeResult:
        """Delete a case, its children, its logs and its files, unrecorded.

        Only for fictional data (the demo reset). Erasing a real person's
        record must go through `purge_case`, which leaves the evidence row.
        """
        identifier = case.identifier
        files_deleted = self._delete_case_files(case)
        records_deleted = self._delete_case_records(case.id)
        return PurgeResult(
            case_identifier=identifier,
            records_deleted=records_deleted,
            files_deleted=files_deleted,
        )

    def find_expired_cases(self, retention_days: int) -> List[Case]:
        """Archived cases whose retention period has elapsed."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        return (
            Case.query.filter(
                Case.archived_at.isnot(None),
                Case.archived_at < cutoff,
            ).all()
        )

    def purge_expired_cases(self, retention_days: int) -> List[PurgeResult]:
        """Purge every archived case past the retention period."""
        return [
            self.purge_case(case, reason=REASON_RETENTION_POLICY)
            for case in self.find_expired_cases(retention_days)
        ]

    def get_erasure_log(self, limit: int = 100) -> List[ErasureLog]:
        return (
            ErasureLog.query.order_by(ErasureLog.purged_at.desc())
            .limit(limit)
            .all()
        )

    # --- Internals -------------------------------------------------------

    def _delete_case_files(self, case: Case) -> int:
        """Remove the case's attachment directory and its voice note."""
        deleted = 0

        case_dir = os.path.join(self.upload_folder, str(case.id))
        if os.path.isdir(case_dir):
            deleted += sum(len(files) for _, _, files in os.walk(case_dir))
            shutil.rmtree(case_dir, ignore_errors=True)

        if case.voice_note_path:
            voice_path = os.path.join(self.upload_folder, case.voice_note_path)
            if os.path.isfile(voice_path):
                try:
                    os.remove(voice_path)
                    deleted += 1
                except OSError as exc:
                    # Report the failure rather than claiming a clean erasure.
                    logger.error(f"Could not delete voice note {voice_path}: {exc}")

        return deleted

    def _delete_case_records(self, case_id: int) -> int:
        """Delete the case row and everything that references it.

        Interaction tags are removed before their parent interactions because
        they have no cascade of their own.
        """
        deleted = 0

        interaction_ids = [
            row[0]
            for row in db.session.query(CaseInteraction.id)
            .filter_by(case_id=case_id)
            .all()
        ]
        if interaction_ids:
            deleted += (
                InteractionTag.query.filter(
                    InteractionTag.interaction_id.in_(interaction_ids)
                ).delete(synchronize_session=False)
            )

        for model in (
            CaseNote,
            CaseAction,
            CaseInteraction,
            FollowUpTask,
            CaseAttachment,
            AuditLog,
            AccessLog,
        ):
            deleted += model.query.filter_by(case_id=case_id).delete(
                synchronize_session=False
            )

        deleted += Case.query.filter_by(id=case_id).delete(
            synchronize_session=False
        )
        db.session.commit()
        return deleted
