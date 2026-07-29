import logging
import os
from typing import Optional, Tuple

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.models.case import Case, CaseCategory
from app.models.case_note import CaseNote, NoteSource
from app.repositories.case_repository import CaseRepository
from app.repositories.case_note_repository import CaseNoteRepository
from app.services.audit_service import AuditService
from app.services.identifier_service import IdentifierService
from app.services.transcription_client import TranscriptionClient

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {"webm", "ogg", "mp3", "wav", "m4a"}


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

        return case, None

    def get_cases_for_user(self, user_id: int) -> list[Case]:
        return self.case_repo.get_by_user_id(user_id)

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
    ) -> Tuple[Optional[Case], Optional[str]]:
        """Update editable case fields with audit logging.

        Only full_name and phone_number are editable.
        Location and created_at are immutable.
        """
        updates = {}

        if full_name is not None and full_name != case.full_name:
            self.audit_service.log_update(
                case_id=case.id,
                user_id=user_id,
                field_name="full_name",
                old_value=case.full_name or "",
                new_value=full_name,
            )
            updates["full_name"] = full_name or None

        if phone_number is not None and phone_number != case.phone_number:
            self.audit_service.log_update(
                case_id=case.id,
                user_id=user_id,
                field_name="phone_number",
                old_value=case.phone_number or "",
                new_value=phone_number,
            )
            updates["phone_number"] = phone_number or None

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

        old_content = note.content
        updated = self.note_repo.update(note, content=content)

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
        """Delete a case and clean up associated files."""
        if user_id:
            self.audit_service.log_delete(
                case_id=case.id,
                user_id=user_id,
                field_name="case",
                old_value=f"Deleted case {case.identifier}",
            )

        if case.voice_note_path:
            file_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], case.voice_note_path
            )
            if os.path.exists(file_path):
                os.remove(file_path)
        # Notes are cascade-deleted via the relationship
        self.case_repo.delete(case)

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

    def _has_meaningful_content(self, html_content: str) -> bool:
        """Check if HTML content has actual text (not just empty tags).

        Quill sends '<p><br></p>' when the editor is empty.
        """
        import re
        # Strip all HTML tags
        text = re.sub(r"<[^>]+>", "", html_content)
        # Strip whitespace and common empty placeholders
        text = text.replace("\n", "").replace("\r", "").strip()
        return len(text) > 0

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
