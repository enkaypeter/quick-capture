from app.models.case_action import CaseAction
from app.repositories.base import BaseRepository


class CaseActionRepository(BaseRepository[CaseAction]):
    """Repository for case action data access."""

    model = CaseAction

    def get_by_case_id(self, case_id: int) -> list[CaseAction]:
        """Get all actions for a case."""
        return (
            CaseAction.query.filter_by(case_id=case_id)
            .order_by(CaseAction.created_at.asc())
            .all()
        )

    def get_completed_for_case(self, case_id: int) -> list[CaseAction]:
        """Get all completed actions for a case."""
        return (
            CaseAction.query.filter_by(case_id=case_id, completed=True)
            .order_by(CaseAction.created_at.asc())
            .all()
        )

    def delete_by_case_id(self, case_id: int) -> int:
        """Delete all actions for a case. Returns count deleted."""
        from app.extensions import db
        count = CaseAction.query.filter_by(case_id=case_id).delete()
        db.session.commit()
        return count
