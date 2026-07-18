import os
from typing import Optional, Tuple

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.models.case import Case, CaseCategory
from app.repositories.case_repository import CaseRepository
from app.services.identifier_service import IdentifierService

ALLOWED_AUDIO_EXTENSIONS = {"webm", "ogg", "mp3", "wav", "m4a"}


class CaseService:
    def __init__(self):
        self.case_repo = CaseRepository()
        self.identifier_service = IdentifierService()

    def create_case(
        self,
        user_id: int,
        full_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        location_w3w: Optional[str] = None,
        location_lat: Optional[float] = None,
        location_lng: Optional[float] = None,
        notes: Optional[str] = None,
        category: Optional[str] = None,
        voice_note_file: Optional[FileStorage] = None,
    ) -> Tuple[Optional[Case], Optional[str]]:
        """Create a new case/interaction.

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
            notes=notes,
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
            notes=notes or None,
            voice_note_path=voice_note_path,
            category=category,
            user_id=user_id,
        )

        return case, None

    def get_cases_for_user(self, user_id: int) -> list[Case]:
        return self.case_repo.get_by_user_id(user_id)

    def get_case(self, case_id: int) -> Optional[Case]:
        return self.case_repo.get_by_id(case_id)

    def update_case_notes(self, case: Case, notes: str) -> Case:
        return self.case_repo.update(case, notes=notes)

    def update_category(self, case: Case, category: str) -> Tuple[Optional[Case], Optional[str]]:
        if category not in CaseCategory.CHOICES:
            return None, f"Invalid category. Must be one of: {', '.join(CaseCategory.CHOICES)}"
        return self.case_repo.update(case, category=category), None

    def delete_case(self, case: Case) -> None:
        # Clean up voice note file if it exists
        if case.voice_note_path:
            file_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], case.voice_note_path
            )
            if os.path.exists(file_path):
                os.remove(file_path)
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
