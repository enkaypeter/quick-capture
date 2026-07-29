import logging
from typing import Optional

from app.models.audit_log import AuditAction, AuditLog
from app.repositories.audit_log_repository import AuditLogRepository

logger = logging.getLogger(__name__)


class AuditService:
    """Service for recording audit trail entries.

    Every mutation to a case or its related entities (notes, actions, category)
    should be logged through this service.
    """

    def __init__(self):
        self.repo = AuditLogRepository()

    def log_create(
        self,
        case_id: int,
        user_id: int,
        field_name: str,
        new_value: Optional[str] = None,
    ) -> AuditLog:
        """Log a creation event."""
        return self.repo.create(
            case_id=case_id,
            user_id=user_id,
            action=AuditAction.CREATED,
            field_name=field_name,
            old_value=None,
            new_value=new_value,
        )

    def log_update(
        self,
        case_id: int,
        user_id: int,
        field_name: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
    ) -> AuditLog:
        """Log an update event."""
        return self.repo.create(
            case_id=case_id,
            user_id=user_id,
            action=AuditAction.UPDATED,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
        )

    def log_delete(
        self,
        case_id: int,
        user_id: int,
        field_name: str,
        old_value: Optional[str] = None,
    ) -> AuditLog:
        """Log a deletion event."""
        return self.repo.create(
            case_id=case_id,
            user_id=user_id,
            action=AuditAction.DELETED,
            field_name=field_name,
            old_value=old_value,
            new_value=None,
        )

    def get_audit_trail(self, case_id: int, limit: int = 50) -> list[AuditLog]:
        """Get the audit trail for a case."""
        return self.repo.get_recent_for_case(case_id, limit=limit)
