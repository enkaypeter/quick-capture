from sqlalchemy.sql import func

from app.extensions import db


class InviteCodeStatus:
    ACTIVE = "active"
    USED = "used"
    DENIED = "denied"

    CHOICES = [ACTIVE, USED, DENIED]


class InviteCode(db.Model):
    __tablename__ = "invite_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    label = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=InviteCodeStatus.ACTIVE)
    max_uses = db.Column(db.Integer, nullable=False, default=1)
    uses = db.Column(db.Integer, nullable=False, default=0)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    used_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    creator = db.relationship("User", foreign_keys=[created_by_user_id], lazy="select")
    used_by = db.relationship("User", foreign_keys=[used_by_user_id], lazy="select")
