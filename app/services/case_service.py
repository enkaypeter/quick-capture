import logging
import os
from datetime import UTC, date, datetime
from typing import Optional, Tuple

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.models.case import (
    ETHNICITY_CHOICES,
    Case,
    CaseCategory,
    ConsentStatus,
    Project,
    RiskRating,
)
from app.models.case_attachment import AttachmentKind, CaseAttachment
from app.models.case_interaction import CaseInteraction, InteractionTag, InteractionTagType
from app.models.case_note import CaseNote, NoteSource
from app.models.follow_up_task import FollowUpStatus, FollowUpTask
from app.models.user import User
from app.repositories.case_repository import CaseRepository
from app.repositories.case_note_repository import CaseNoteRepository
from app.services.audit_service import AuditService
from app.services.html_service import sanitize_html
from app.services.identifier_service import IdentifierService
from app.services.transcription_client import TranscriptionClient
from app.extensions import db

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {"webm", "ogg", "mp3", "wav", "m4a"}
ALLOWED_ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "txt"}
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}


class CaseService:
    def __init__(self):
        self.case_repo = CaseRepository()
        self.note_repo = CaseNoteRepository()
        self.identifier_service = IdentifierService()
        self.transcription_client = TranscriptionClient()
        self.audit_service = AuditService()

    def create_case(
        self,
        user_id: int,
        full_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        location_w3w: Optional[str] = None,
        location_lat: Optional[float] = None,
        location_lng: Optional[float] = None,
        notes_content: Optional[str] = None,
        category: Optional[str] = None,
        voice_note_file: Optional[FileStorage] = None,
        voice_transcript: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        physical_description: Optional[str] = None,
        other_contact: Optional[str] = None,
        consent_status: Optional[str] = None,
        consent_date: Optional[str] = None,
        risk_rating: Optional[str] = None,
        risk_notes: Optional[str] = None,
        mental_health_notes: Optional[str] = None,
        current_situation: Optional[str] = None,
        ethnicity: Optional[str] = None,
        ni_number: Optional[str] = None,
        location_address: Optional[str] = None,
        project: Optional[str] = None,
        key_worker_id: Optional[int] = None,
        consent_image: Optional[FileStorage] = None,
    ) -> Tuple[Optional[Case], Optional[str]]:
        """Create a new case/interaction.

        Args:
            voice_transcript: Pre-transcribed text from the voice note
                (transcription happens on the frontend before submit).

        Returns:
            Tuple of (case, error_message). On success error_message is None.
        """
        # Validate category
        if category and category not in CaseCategory.CHOICES:
            return None, f"Invalid category. Must be one of: {', '.join(CaseCategory.CHOICES)}"

        if not category:
            category = CaseCategory.NON_CASELOAD

        consent_status = consent_status or ConsentStatus.DEFAULT
        risk_rating = risk_rating or RiskRating.DEFAULT
        error = self._validate_choices(
            consent_status=consent_status,
            risk_rating=risk_rating,
            project=project,
            ethnicity=ethnicity,
        )
        if error:
            return None, error

        if key_worker_id is None:
            key_worker_id = user_id
        elif db.session.get(User, key_worker_id) is None:
            return None, "Choose a key worker from the list."

        if consent_image and consent_image.filename:
            if self._extension(consent_image.filename) not in ALLOWED_IMAGE_EXTENSIONS:
                return None, "The consent and risk image must be a PNG or JPEG."

        calculated_age = self._calculate_age(date_of_birth)
        if calculated_age is not None:
            age = calculated_age

        if not self._has_minimum_identifying_detail(
            full_name=full_name,
            phone_number=phone_number,
            location_w3w=location_w3w,
            notes_content=notes_content,
            voice_transcript=voice_transcript,
            date_of_birth=date_of_birth,
            physical_description=physical_description,
            location_address=location_address,
            other_contact=other_contact,
            ni_number=ni_number,
        ):
            return None, "Add at least one identifying detail or note before creating a case."

        # Generate identifier
        identifier = self.identifier_service.generate(
            location_w3w=location_w3w,
            notes=notes_content,
        )

        # Handle voice note upload
        voice_note_path = None
        if voice_note_file and voice_note_file.filename:
            voice_note_path = self._save_voice_note(voice_note_file, identifier)
            if voice_note_path is None:
                return None, "Invalid audio file format."

        case = self.case_repo.create(
            identifier=identifier,
            full_name=full_name or None,
            phone_number=phone_number or None,
            location_w3w=location_w3w or None,
            location_lat=location_lat,
            location_lng=location_lng,
            voice_note_path=voice_note_path,
            category=category,
            user_id=user_id,
            date_of_birth=date_of_birth or None,
            age=age,
            gender=gender or None,
            physical_description=physical_description or None,
            other_contact=other_contact or None,
            consent_status=consent_status,
            consent_date=consent_date or None,
            risk_rating=risk_rating,
            risk_notes=risk_notes or None,
            mental_health_notes=mental_health_notes or None,
            current_situation=current_situation or None,
            ethnicity=ethnicity or None,
            ni_number=(ni_number or "").strip().upper() or None,
            location_address=location_address or None,
            project=project or None,
            assigned_user_id=key_worker_id,
        )

        # Audit: log case creation
        self.audit_service.log_create(
            case_id=case.id,
            user_id=user_id,
            field_name="case",
            new_value=f"Created case {case.identifier}",
        )

        # Create note: transcription takes precedence over manual
        if voice_transcript:
            self.add_note(
                case_id=case.id,
                content=f"<p>{voice_transcript}</p>",
                source=NoteSource.TRANSCRIPTION,
                user_id=user_id,
            )
        elif notes_content and self._has_meaningful_content(notes_content):
            self.add_note(
                case_id=case.id,
                content=notes_content,
                source=NoteSource.MANUAL,
                user_id=user_id,
            )

        if consent_image and consent_image.filename:
            self.add_attachment(
                case_id=case.id,
                user_id=user_id,
                file=consent_image,
                kind=AttachmentKind.CONSENT_RISK,
            )

        return case, None

    def get_cases_for_user(self, user_id: int) -> list[Case]:
        return self.case_repo.get_active()

    def search_cases(self, query: str) -> list[Case]:
        return self.case_repo.search_active(query)

    def get_cases_needing_review(self) -> list[Case]:
        return self.case_repo.get_needing_review()

    def get_key_worker_choices(self) -> list[User]:
        return User.query.order_by(User.first_name.asc(), User.id.asc()).all()

    def get_case(self, case_id: int) -> Optional[Case]:
        return self.case_repo.get_by_id(case_id)

    def get_notes_for_case(self, case_id: int) -> list[CaseNote]:
        return self.note_repo.get_by_case_id(case_id)

    def update_case_fields(
        self,
        case: Case,
        user_id: int,
        full_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        ni_number: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        physical_description: Optional[str] = None,
        other_contact: Optional[str] = None,
        consent_status: Optional[str] = None,
        consent_date: Optional[str] = None,
        risk_rating: Optional[str] = None,
        risk_notes: Optional[str] = None,
        mental_health_notes: Optional[str] = None,
        current_situation: Optional[str] = None,
        ethnicity: Optional[str] = None,
        location_address: Optional[str] = None,
        project: Optional[str] = None,
        key_worker_id=None,
    ) -> Tuple[Optional[Case], Optional[str]]:
        """Update editable case fields with audit logging.

        The what3words location, identifier and created_at remain immutable.
        A field passed as None is left unchanged; an empty string clears it.
        """
        error = self._validate_choices(
            consent_status=consent_status or None,
            risk_rating=risk_rating or None,
            project=project or None,
            ethnicity=ethnicity or None,
        )
        if error:
            return None, error

        updates = {}
        if key_worker_id is not None:
            key_worker_id, error = self._resolve_key_worker(key_worker_id)
            if error:
                return None, error
            if key_worker_id != case.assigned_user_id:
                old_worker = db.session.get(User, case.assigned_user_id) if case.assigned_user_id else None
                new_worker = db.session.get(User, key_worker_id) if key_worker_id else None
                self.audit_service.log_update(
                    case_id=case.id,
                    user_id=user_id,
                    field_name="key_worker",
                    old_value=old_worker.first_name if old_worker else "",
                    new_value=new_worker.first_name if new_worker else "",
                )
                updates["assigned_user_id"] = key_worker_id

        editable_fields = {
            "full_name": full_name,
            "phone_number": phone_number,
            "ni_number": ni_number,
            "date_of_birth": date_of_birth,
            "age": age,
            "gender": gender,
            "physical_description": physical_description,
            "other_contact": other_contact,
            "consent_status": consent_status,
            "consent_date": consent_date,
            "risk_rating": risk_rating,
            "risk_notes": risk_notes,
            "mental_health_notes": mental_health_notes,
            "current_situation": current_situation,
            "ethnicity": ethnicity,
            "location_address": location_address,
            "project": project,
        }
        calculated_age = self._calculate_age(date_of_birth)
        if calculated_age is not None:
            editable_fields["age"] = calculated_age

        for field_name, value in editable_fields.items():
            if value is None:
                continue

            if field_name == "age":
                try:
                    value = int(value) if value != "" else None
                except (TypeError, ValueError):
                    return None, "Age must be a number."
            elif isinstance(value, str):
                value = value.strip() or None
                if field_name == "ni_number" and value:
                    value = value.upper()

            old_value = getattr(case, field_name)
            if value != old_value:
                self.audit_service.log_update(
                    case_id=case.id,
                    user_id=user_id,
                    field_name=field_name,
                    old_value=str(old_value or ""),
                    new_value=str(value or ""),
                )
                updates[field_name] = value

        if updates:
            return self.case_repo.update(case, **updates), None

        return case, None

    def update_note_content(
        self, note_id: int, content: str, user_id: int
    ) -> Tuple[Optional[CaseNote], Optional[str]]:
        """Update the content of an existing note with audit logging."""
        note = self.note_repo.get_by_id(note_id)
        if not note:
            return None, "Note not found"

        if not content or not content.strip():
            return None, "Note content cannot be empty"

        updated = self.note_repo.update(note, content=sanitize_html(content))

        self.audit_service.log_update(
            case_id=note.case_id,
            user_id=user_id,
            field_name=f"note:{note.id}",
            old_value="(content edited)",
            new_value="(content updated)",
        )

        return updated, None

    def add_note(
        self,
        case_id: int,
        content: str,
        source: str = NoteSource.MANUAL,
        needs_review: bool = False,
        user_id: Optional[int] = None,
    ) -> CaseNote:
        """Add a note to a case.

        Transcribed notes are automatically flagged for review.
        """
        if source == NoteSource.TRANSCRIPTION:
            needs_review = True

        content = sanitize_html(content)

        note = self.note_repo.create(
            case_id=case_id,
            content=content,
            source=source,
            needs_review=needs_review,
        )

        # Audit: log note creation
        if user_id:
            self.audit_service.log_create(
                case_id=case_id,
                user_id=user_id,
                field_name=f"note:{note.id}",
                new_value=f"Added {source} note",
            )

        return note

    def add_interaction(
        self,
        case_id: int,
        user_id: int,
        note_content: Optional[str] = None,
        tag_types: Optional[list[str]] = None,
        outcome: Optional[str] = None,
        location_w3w: Optional[str] = None,
        location_lat: Optional[float] = None,
        location_lng: Optional[float] = None,
    ) -> Tuple[Optional[CaseInteraction], Optional[str]]:
        tag_types = tag_types or []
        valid_tags = [t for t in tag_types if t in InteractionTagType.CHOICES]
        clean_note = sanitize_html(note_content or "")

        if not valid_tags and not self._has_meaningful_content(clean_note) and not outcome:
            return None, "Add a note, quick tag, or outcome before saving the interaction."

        interaction = CaseInteraction(
            case_id=case_id,
            user_id=user_id,
            note_content=clean_note or None,
            outcome=(outcome or "").strip() or None,
            location_w3w=(location_w3w or "").strip() or None,
            location_lat=location_lat,
            location_lng=location_lng,
        )
        db.session.add(interaction)
        db.session.flush()

        for tag_type in valid_tags:
            db.session.add(
                InteractionTag(
                    interaction_id=interaction.id,
                    tag_type=tag_type,
                    label=InteractionTagType.LABELS[tag_type],
                )
            )

        db.session.commit()

        self.audit_service.log_create(
            case_id=case_id,
            user_id=user_id,
            field_name=f"interaction:{interaction.id}",
            new_value=f"Added interaction ({len(valid_tags)} tags)",
        )
        return interaction, None

    def get_interactions_for_case(self, case_id: int) -> list[CaseInteraction]:
        return CaseInteraction.query.filter_by(case_id=case_id).order_by(
            CaseInteraction.occurred_at.desc()
        ).all()

    def add_follow_up_task(
        self,
        case_id: int,
        user_id: int,
        title: str,
        due_date: Optional[str] = None,
    ) -> Tuple[Optional[FollowUpTask], Optional[str]]:
        title = (title or "").strip()
        if not title:
            return None, "Follow-up title is required."

        task = FollowUpTask(
            case_id=case_id,
            created_by_user_id=user_id,
            assigned_user_id=user_id,
            title=title,
            due_date=(due_date or "").strip() or None,
        )
        db.session.add(task)
        db.session.commit()

        self.audit_service.log_create(
            case_id=case_id,
            user_id=user_id,
            field_name=f"follow_up:{task.id}",
            new_value=title,
        )
        return task, None

    def complete_follow_up_task(
        self,
        task_id: int,
        user_id: int,
    ) -> Tuple[Optional[FollowUpTask], Optional[str]]:
        task = db.session.get(FollowUpTask, task_id)
        if not task:
            return None, "Follow-up task not found."

        task.status = FollowUpStatus.DONE
        task.completed_at = datetime.now(UTC)
        db.session.commit()

        self.audit_service.log_update(
            case_id=task.case_id,
            user_id=user_id,
            field_name=f"follow_up:{task.id}",
            old_value="open",
            new_value="done",
        )
        return task, None

    def get_follow_ups_for_case(self, case_id: int) -> list[FollowUpTask]:
        return FollowUpTask.query.filter_by(case_id=case_id).order_by(
            FollowUpTask.status.asc(),
            FollowUpTask.due_date.asc(),
            FollowUpTask.created_at.desc(),
        ).all()

    def get_upcoming_follow_ups(self) -> list[FollowUpTask]:
        return FollowUpTask.query.filter_by(status=FollowUpStatus.OPEN).order_by(
            FollowUpTask.due_date.asc(),
            FollowUpTask.created_at.desc(),
        ).all()

    def add_attachment(
        self,
        case_id: int,
        user_id: int,
        file: FileStorage,
        interaction_id: Optional[int] = None,
        kind: Optional[str] = None,
    ) -> Tuple[Optional[CaseAttachment], Optional[str]]:
        if not file or not file.filename:
            return None, "Choose a file to upload."

        ext = self._extension(file.filename)
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            return None, "Unsupported file type."
        if kind == AttachmentKind.CONSENT_RISK and ext not in ALLOWED_IMAGE_EXTENSIONS:
            return None, "The consent and risk image must be a PNG or JPEG."

        case_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], str(case_id))
        os.makedirs(case_dir, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        original = secure_filename(file.filename)
        stored_name = f"{timestamp}_{original}"
        stored_path = os.path.join(str(case_id), stored_name)
        absolute_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_path)
        file.save(absolute_path)

        attachment = CaseAttachment(
            case_id=case_id,
            interaction_id=interaction_id,
            user_id=user_id,
            original_filename=original,
            stored_path=stored_path,
            content_type=file.content_type,
            size_bytes=os.path.getsize(absolute_path),
            kind=kind,
        )
        db.session.add(attachment)
        db.session.commit()

        self.audit_service.log_create(
            case_id=case_id,
            user_id=user_id,
            field_name=f"attachment:{attachment.id}",
            new_value=original,
        )
        return attachment, None

    def get_attachments_for_case(self, case_id: int) -> list[CaseAttachment]:
        return CaseAttachment.query.filter_by(case_id=case_id).order_by(
            CaseAttachment.created_at.desc()
        ).all()

    def reporting_summary(self) -> dict:
        cases = self.case_repo.get_active()
        interactions = CaseInteraction.query.all()
        tag_counts = {}
        for tag in InteractionTag.query.all():
            tag_counts[tag.label] = tag_counts.get(tag.label, 0) + 1

        project_counts = {}
        risk_counts = {}
        situation_counts = {}
        for case in cases:
            project_label = Project.LABELS.get(case.project, "Not set")
            project_counts[project_label] = project_counts.get(project_label, 0) + 1
            risk_counts[case.risk_rating] = risk_counts.get(case.risk_rating, 0) + 1
            if case.current_situation:
                situation_counts[case.current_situation] = situation_counts.get(case.current_situation, 0) + 1

        return {
            "total_cases": len(cases),
            "total_interactions": len(interactions),
            "project_counts": project_counts,
            "risk_counts": risk_counts,
            "situation_counts": situation_counts,
            "tag_counts": tag_counts,
        }

    def mark_note_reviewed(self, note_id: int, user_id: Optional[int] = None) -> Optional[CaseNote]:
        """Mark a transcribed note as reviewed."""
        note = self.note_repo.get_by_id(note_id)
        if note:
            updated = self.note_repo.update(note, needs_review=False)
            if user_id:
                self.audit_service.log_update(
                    case_id=note.case_id,
                    user_id=user_id,
                    field_name=f"note:{note.id}",
                    old_value="needs_review=True",
                    new_value="needs_review=False",
                )
            return updated
        return None

    def delete_note(self, note_id: int, user_id: Optional[int] = None) -> bool:
        """Delete a specific note."""
        note = self.note_repo.get_by_id(note_id)
        if note:
            case_id = note.case_id
            if user_id:
                self.audit_service.log_delete(
                    case_id=case_id,
                    user_id=user_id,
                    field_name=f"note:{note.id}",
                    old_value=f"Deleted {note.source} note",
                )
            self.note_repo.delete(note)
            return True
        return False

    def update_category(
        self, case: Case, category: str, user_id: Optional[int] = None,
        ni_number: Optional[str] = None,
    ) -> Tuple[Optional[Case], Optional[str]]:
        """Update case category with audit logging.

        Category progression is one-way:
          non-caseload → caseload → client
        Downgrading is not allowed once a case has progressed.
        When switching to 'client', ni_number is required.
        """
        if category not in CaseCategory.CHOICES:
            return None, f"Invalid category. Must be one of: {', '.join(CaseCategory.CHOICES)}"

        # Enforce one-way category progression
        category_order = {
            CaseCategory.NON_CASELOAD: 0,
            CaseCategory.CASELOAD: 1,
            CaseCategory.CLIENT: 2,
        }
        current_level = category_order.get(case.category, 0)
        new_level = category_order.get(category, 0)

        if new_level < current_level:
            return None, f"Cannot downgrade category from '{case.category}' to '{category}'"

        # Validate NI number is provided when switching to client
        if category == CaseCategory.CLIENT:
            if not ni_number and not case.ni_number:
                return None, "National Insurance number is required for client cases"

        old_category = case.category
        updates = {"category": category}

        # Update NI number if provided
        if ni_number is not None and ni_number != (case.ni_number or ""):
            if user_id:
                self.audit_service.log_update(
                    case_id=case.id,
                    user_id=user_id,
                    field_name="ni_number",
                    old_value=case.ni_number or "",
                    new_value=ni_number,
                )
            updates["ni_number"] = ni_number or None

        updated = self.case_repo.update(case, **updates)

        if user_id and old_category != category:
            self.audit_service.log_update(
                case_id=case.id,
                user_id=user_id,
                field_name="category",
                old_value=old_category,
                new_value=category,
            )

        return updated, None

    def update_ni_number(
        self, case: Case, ni_number: str, user_id: int
    ) -> Tuple[Optional[Case], Optional[str]]:
        """Update National Insurance number with audit logging."""
        if not ni_number or not ni_number.strip():
            return None, "NI number is required"

        old_ni = case.ni_number or ""
        ni_number = ni_number.strip()

        if old_ni == ni_number:
            return case, None

        updated = self.case_repo.update(case, ni_number=ni_number)

        self.audit_service.log_update(
            case_id=case.id,
            user_id=user_id,
            field_name="ni_number",
            old_value=old_ni,
            new_value=ni_number,
        )

        return updated, None

    def get_actions_for_case(self, case_id: int) -> list:
        """Get all actions for a case."""
        from app.repositories.case_action_repository import CaseActionRepository
        action_repo = CaseActionRepository()
        return action_repo.get_by_case_id(case_id)

    def update_actions(
        self,
        case_id: int,
        user_id: int,
        actions: list,
    ) -> list:
        """Replace case actions with the provided list.

        Each action dict should have: action_type, label, completed.
        Predefined actions use their type as action_type.
        Custom actions use "custom" as action_type with a user-provided label.
        """
        from app.models.case_action import CaseAction, PredefinedAction
        from app.repositories.case_action_repository import CaseActionRepository

        action_repo = CaseActionRepository()

        # Remove existing actions
        action_repo.delete_by_case_id(case_id)

        # Create new actions
        created = []
        for action_data in actions:
            action_type = action_data.get("action_type", "custom")
            label = action_data.get("label", "")
            completed = action_data.get("completed", False)

            if not label:
                # Use predefined label if available
                label = PredefinedAction.LABELS.get(action_type, action_type)

            action = action_repo.create(
                case_id=case_id,
                action_type=action_type,
                label=label,
                completed=completed,
            )
            created.append(action)

        # Audit
        self.audit_service.log_update(
            case_id=case_id,
            user_id=user_id,
            field_name="actions",
            old_value=None,
            new_value=f"Updated actions ({len(created)} items)",
        )

        return created

    def delete_case(self, case: Case, user_id: Optional[int] = None) -> None:
        """Archive a case without destroying safeguarding history."""
        if user_id:
            self.audit_service.log_delete(
                case_id=case.id,
                user_id=user_id,
                field_name="case",
                old_value=f"Archived case {case.identifier}",
            )

        self.case_repo.update(case, archived_at=datetime.now(UTC))

    def _save_voice_note(
        self, file: FileStorage, identifier: str
    ) -> Optional[str]:
        """Save a voice note file and return its relative path."""
        if not file.filename:
            return None

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return None

        filename = secure_filename(f"{identifier}_voice.{ext}")
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)

        file.save(os.path.join(upload_dir, filename))
        return filename

    @staticmethod
    def _extension(filename: str) -> str:
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    def _validate_choices(
        self,
        consent_status: Optional[str] = None,
        risk_rating: Optional[str] = None,
        project: Optional[str] = None,
        ethnicity: Optional[str] = None,
    ) -> Optional[str]:
        if consent_status and consent_status not in ConsentStatus.CHOICES:
            return "Choose a consent status from the list."
        if risk_rating and risk_rating not in RiskRating.CHOICES:
            return "Choose a risk rating from the list."
        if project and project not in Project.CHOICES:
            return "Choose a project from the list."
        if ethnicity and ethnicity not in ETHNICITY_CHOICES:
            return "Choose an ethnicity from the list."
        return None

    def _resolve_key_worker(self, key_worker_id) -> Tuple[Optional[int], Optional[str]]:
        """Turn a submitted key worker value into a user id (None clears it)."""
        if key_worker_id in ("", None):
            return None, None
        try:
            worker_id = int(key_worker_id)
        except (TypeError, ValueError):
            return None, "Choose a key worker from the list."
        if db.session.get(User, worker_id) is None:
            return None, "Choose a key worker from the list."
        return worker_id, None

    def _has_meaningful_content(self, html_content: str) -> bool:
        """Check if HTML content has actual text (not just empty tags).

        Older versions of the app used a rich-text editor that could submit
        empty HTML tags; keep this defensive check for existing clients.
        """
        import re
        # Strip all HTML tags
        text = re.sub(r"<[^>]+>", "", html_content)
        # Strip whitespace and common empty placeholders
        text = text.replace("\n", "").replace("\r", "").strip()
        return len(text) > 0

    def _calculate_age(self, date_of_birth: Optional[str]) -> Optional[int]:
        if not date_of_birth:
            return None

        try:
            born = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

        today = date.today()
        if born > today:
            return None

        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def _has_minimum_identifying_detail(
        self,
        full_name: Optional[str],
        phone_number: Optional[str],
        location_w3w: Optional[str],
        notes_content: Optional[str],
        voice_transcript: Optional[str],
        date_of_birth: Optional[str],
        physical_description: Optional[str],
        location_address: Optional[str] = None,
        other_contact: Optional[str] = None,
        ni_number: Optional[str] = None,
    ) -> bool:
        return any([
            bool((location_address or "").strip()),
            bool((other_contact or "").strip()),
            bool((ni_number or "").strip()),
            bool((full_name or "").strip()),
            bool((phone_number or "").strip()),
            bool((location_w3w or "").strip()),
            self._has_meaningful_content(notes_content or ""),
            bool((voice_transcript or "").strip()),
            bool((date_of_birth or "").strip()),
            bool((physical_description or "").strip()),
        ])

    def _transcribe_and_create_note(self, case: Case) -> None:
        """Send voice note to transcription service and create a note.

        This runs synchronously — the worker waits a few seconds for the
        transcription to complete. If the service is unavailable or fails,
        we log the error but don't block case creation.
        """
        audio_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], case.voice_note_path
        )

        transcript = self.transcription_client.transcribe(audio_path)

        if transcript:
            self.add_note(
                case_id=case.id,
                content=f"<p>{transcript}</p>",
                source=NoteSource.TRANSCRIPTION,
            )
            logger.info(
                f"Transcription note created for case {case.identifier}"
            )
        else:
            logger.warning(
                f"Transcription failed for case {case.identifier}, "
                f"voice note saved but no transcript note created"
            )
