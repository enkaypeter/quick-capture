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

        # Create the initial manual note if content was provided
        if notes_content and self._has_meaningful_content(notes_content):
            self.add_note(
                case_id=case.id,
                content=notes_content,
                source=NoteSource.MANUAL,
            )

        # Create transcription note if transcript was provided from the frontend
        if voice_transcript:
            self.add_note(
                case_id=case.id,
                content=f"<p>{voice_transcript}</p>",
                source=NoteSource.TRANSCRIPTION,
            )

        return case, None

    def get_cases_for_user(self, user_id: int) -> list[Case]:
        return self.case_repo.get_by_user_id(user_id)

    def get_case(self, case_id: int) -> Optional[Case]:
        return self.case_repo.get_by_id(case_id)

    def get_notes_for_case(self, case_id: int) -> list[CaseNote]:
        return self.note_repo.get_by_case_id(case_id)

    def add_note(
        self,
        case_id: int,
        content: str,
        source: str = NoteSource.MANUAL,
        needs_review: bool = False,
    ) -> CaseNote:
        """Add a note to a case.

        Transcribed notes are automatically flagged for review.
        """
        if source == NoteSource.TRANSCRIPTION:
            needs_review = True

        return self.note_repo.create(
            case_id=case_id,
            content=content,
            source=source,
            needs_review=needs_review,
        )

    def mark_note_reviewed(self, note_id: int) -> Optional[CaseNote]:
        """Mark a transcribed note as reviewed."""
        note = self.note_repo.get_by_id(note_id)
        if note:
            return self.note_repo.update(note, needs_review=False)
        return None

    def delete_note(self, note_id: int) -> bool:
        """Delete a specific note."""
        note = self.note_repo.get_by_id(note_id)
        if note:
            self.note_repo.delete(note)
            return True
        return False

    def update_category(self, case: Case, category: str) -> Tuple[Optional[Case], Optional[str]]:
        if category not in CaseCategory.CHOICES:
            return None, f"Invalid category. Must be one of: {', '.join(CaseCategory.CHOICES)}"
        return self.case_repo.update(case, category=category), None

    def delete_case(self, case: Case) -> None:
        """Delete a case and clean up associated files."""
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
