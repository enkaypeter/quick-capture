from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for audit log data access."""

    model = AuditLog

    def get_by_case_id(self, case_id: int) -> list[AuditLog]:
        """Get all audit entries for a case, most recent first."""
        return (
            AuditLog.query.filter_by(case_id=case_id)
            .order_by(AuditLog.timestamp.desc())
            .all()
        )

    def get_by_user_id(self, user_id: int) -> list[AuditLog]:
        """Get all audit entries by a specific user."""
        return (
            AuditLog.query.filter_by(user_id=user_id)
            .order_by(AuditLog.timestamp.desc())
            .all()
        )

    def get_recent_for_case(
        self, case_id: int, limit: int = 50
    ) -> list[AuditLog]:
        """Get the most recent audit entries for a case."""
        return (
            AuditLog.query.filter_by(case_id=case_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )
