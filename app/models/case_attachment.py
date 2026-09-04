from sqlalchemy.sql import func

from app.extensions import db


class CaseAttachment(db.Model):
    __tablename__ = "case_attachments"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)
    interaction_id = db.Column(db.Integer, db.ForeignKey("case_interactions.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(100), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    uploader = db.relationship("User", lazy="select")
