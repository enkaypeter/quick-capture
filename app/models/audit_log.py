from sqlalchemy.sql import func

from app.extensions import db


class AuditAction:
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"

    CHOICES = [CREATED, UPDATED, DELETED]


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    # Which case was affected
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)

    # Who performed the action
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # What type of action (created, updated, deleted)
    action = db.Column(db.String(20), nullable=False)

    # What entity/field was changed (e.g. "full_name", "note:42", "category")
    field_name = db.Column(db.String(100), nullable=False)

    # Previous value (null for creates)
    old_value = db.Column(db.Text, nullable=True)

    # New value (null for deletes)
    new_value = db.Column(db.Text, nullable=True)

    # When it happened
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

    # Relationships
    user = db.relationship("User", backref="audit_logs", lazy="select")

    def __repr__(self):
        return f"<AuditLog {self.id} case={self.case_id} action={self.action} field={self.field_name}>"
