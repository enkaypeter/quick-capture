from sqlalchemy.sql import func

from app.extensions import db


class FollowUpStatus:
    OPEN = "open"
    DONE = "done"

    CHOICES = [OPEN, DONE]


class FollowUpTask(db.Model):
    __tablename__ = "follow_up_tasks"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=FollowUpStatus.OPEN)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    creator = db.relationship("User", foreign_keys=[created_by_user_id], lazy="select")
    assignee = db.relationship("User", foreign_keys=[assigned_user_id], lazy="select")
