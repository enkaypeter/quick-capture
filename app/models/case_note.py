from sqlalchemy.sql import func

from app.extensions import db


class NoteSource:
    MANUAL = "manual"
    TRANSCRIPTION = "transcription"

    CHOICES = [MANUAL, TRANSCRIPTION]


class CaseNote(db.Model):
    __tablename__ = "case_notes"

    id = db.Column(db.Integer, primary_key=True)

    # Rich text content (HTML)
    content = db.Column(db.Text, nullable=False)

    # Source of the note
    source = db.Column(
        db.String(20),
        nullable=False,
        default=NoteSource.MANUAL,
    )

    # Whether this note needs human review (True for transcriptions)
    needs_review = db.Column(db.Boolean, nullable=False, default=False)

    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    # Foreign key to the parent case
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)

    def __repr__(self):
        return f"<CaseNote {self.id} source={self.source}>"
