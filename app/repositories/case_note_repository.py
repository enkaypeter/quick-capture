from app.models.case_note import CaseNote
from app.repositories.base import BaseRepository


class CaseNoteRepository(BaseRepository[CaseNote]):
    model = CaseNote

    def get_by_case_id(self, case_id: int) -> list[CaseNote]:
        return CaseNote.query.filter_by(case_id=case_id).order_by(
            CaseNote.created_at.desc()
        ).all()

    def get_pending_review(self, case_id: int) -> list[CaseNote]:
        """Get notes that need human review (transcriptions)."""
        return CaseNote.query.filter_by(
            case_id=case_id, needs_review=True
        ).order_by(CaseNote.created_at.desc()).all()
