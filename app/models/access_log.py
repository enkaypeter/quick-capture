from sqlalchemy.sql import func

from app.extensions import db


class AccessAction:
    """Read-side events. Writes are recorded in `audit_logs` instead."""

    VIEWED_CASE = "viewed_case"
    DOWNLOADED_ATTACHMENT = "downloaded_attachment"
    PLAYED_VOICE_NOTE = "played_voice_note"
    VIEWED_AUDIT_TRAIL = "viewed_audit_trail"
    EXPORTED_REPORT = "exported_report"
    SEARCHED = "searched"

    CHOICES = [
        VIEWED_CASE,
        DOWNLOADED_ATTACHMENT,
        PLAYED_VOICE_NOTE,
        VIEWED_AUDIT_TRAIL,
        EXPORTED_REPORT,
        SEARCHED,
    ]


class AccessLog(db.Model):
    """Who read what.

    Blocker 10. The existing audit trail answers "who changed this record".
    After a safeguarding incident the question asked is "who looked at it",
    and nothing recorded that.

    Kept in its own table rather than folded into `audit_logs` for two
    reasons: reads are far more numerous than writes and would drown the
    change history, and some read events (a CSV export) belong to no single
    case, which `audit_logs.case_id` does not allow.
    """

    __tablename__ = "access_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # Nullable: a report export spans every case.
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=True, index=True)
    action = db.Column(db.String(50), nullable=False)
    # Free-text identifier of the thing accessed, e.g. "attachment:42".
    # Never holds case content.
    resource = db.Column(db.String(200), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=func.now(), index=True
    )

    user = db.relationship("User", lazy="select")

    def __repr__(self):
        return f"<AccessLog {self.action} user={self.user_id} case={self.case_id}>"
