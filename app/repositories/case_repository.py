from typing import Optional

from sqlalchemy import or_

from app.models.case import Case
from app.repositories.base import BaseRepository


class CaseRepository(BaseRepository[Case]):
    model = Case

    def get_by_identifier(self, identifier: str) -> Optional[Case]:
        return Case.query.filter_by(identifier=identifier).first()

    def get_by_user_id(self, user_id: int) -> list[Case]:
        return Case.query.filter_by(user_id=user_id).order_by(
            Case.created_at.desc()
        ).all()

    def get_active(self) -> list[Case]:
        return Case.query.filter(Case.archived_at.is_(None)).order_by(
            Case.updated_at.desc()
        ).all()

    def search_active(self, query: str) -> list[Case]:
        term = f"%{query.strip()}%"
        if not query.strip():
            return self.get_active()

        return Case.query.filter(
            Case.archived_at.is_(None),
            or_(
                Case.identifier.ilike(term),
                Case.full_name.ilike(term),
                Case.phone_number.ilike(term),
                Case.location_w3w.ilike(term),
                Case.date_of_birth.ilike(term),
                Case.gender.ilike(term),
                Case.physical_description.ilike(term),
                Case.other_contact.ilike(term),
                Case.current_situation.ilike(term),
            ),
        ).order_by(Case.updated_at.desc()).all()

    def get_by_category(self, category: str) -> list[Case]:
        return Case.query.filter_by(category=category).order_by(
            Case.created_at.desc()
        ).all()

    def get_by_user_and_category(self, user_id: int, category: str) -> list[Case]:
        return Case.query.filter_by(
            user_id=user_id, category=category
        ).order_by(Case.created_at.desc()).all()

    def count_by_location_prefix(self, prefix: str) -> int:
        """Count cases whose identifier starts with a given prefix.

        Used for generating sequential identifiers like LOC-Keyword-001.
        """
        return Case.query.filter(
            Case.identifier.like(f"{prefix}%")
        ).count()

    def identifier_exists(self, identifier: str) -> bool:
        return Case.query.filter_by(identifier=identifier).first() is not None
