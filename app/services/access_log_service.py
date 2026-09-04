"""Recording who read case data.

Blocker 10. The `audit_logs` table answers "who changed this record". After a
safeguarding incident the question actually asked is "who looked at it", and
nothing recorded that.

Repeat views by the same user within a short window collapse into one entry.
Without that, a worker scrolling one case produces dozens of rows and the log
becomes unreadable exactly when someone needs to read it.
"""

from datetime import UTC, datetime, timedelta
from typing import List, Optional

from app.extensions import db
from app.models.access_log import AccessAction, AccessLog

# User-Agent strings are long and attacker-controlled; store a bounded slice.
MAX_USER_AGENT_LENGTH = 300


class AccessLogService:
    def __init__(self, dedupe_minutes: int = 5):
        self.dedupe_minutes = dedupe_minutes

    @classmethod
    def from_config(cls, config) -> "AccessLogService":
        return cls(dedupe_minutes=config["ACCESS_LOG_DEDUPE_MINUTES"])

    def record(
        self,
        user_id: int,
        action: str,
        case_id: Optional[int] = None,
        resource: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AccessLog]:
        """Record a read event, or return None if it was deduplicated."""
        if self._recently_logged(user_id, action, case_id, resource):
            return None

        entry = AccessLog(
            user_id=user_id,
            case_id=case_id,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:MAX_USER_AGENT_LENGTH] or None,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    def get_for_case(self, case_id: int, limit: int = 50) -> List[AccessLog]:
        return (
            AccessLog.query.filter_by(case_id=case_id)
            .order_by(AccessLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_for_user(self, user_id: int, limit: int = 100) -> List[AccessLog]:
        return (
            AccessLog.query.filter_by(user_id=user_id)
            .order_by(AccessLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent(self, limit: int = 200) -> List[AccessLog]:
        return (
            AccessLog.query.order_by(AccessLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def prune(self, older_than_days: int) -> int:
        """Delete access log rows past their retention period."""
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        deleted = AccessLog.query.filter(AccessLog.created_at < cutoff).delete()
        db.session.commit()
        return deleted

    def delete_for_case(self, case_id: int) -> int:
        """Remove every access log row for a case, used during erasure."""
        deleted = AccessLog.query.filter_by(case_id=case_id).delete()
        db.session.commit()
        return deleted

    def _recently_logged(
        self,
        user_id: int,
        action: str,
        case_id: Optional[int],
        resource: Optional[str],
    ) -> bool:
        if self.dedupe_minutes <= 0:
            return False

        cutoff = datetime.now(UTC) - timedelta(minutes=self.dedupe_minutes)
        return (
            AccessLog.query.filter(
                AccessLog.user_id == user_id,
                AccessLog.action == action,
                AccessLog.case_id.is_(case_id) if case_id is None
                else AccessLog.case_id == case_id,
                AccessLog.resource.is_(resource) if resource is None
                else AccessLog.resource == resource,
                AccessLog.created_at >= cutoff,
            ).first()
            is not None
        )


__all__ = ["AccessAction", "AccessLogService"]
