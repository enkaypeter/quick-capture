from sqlalchemy.sql import func

from app.extensions import db
from app.security.crypto import EncryptedText


class CaseCategory:
    NON_CASELOAD = "non-caseload"
    CASELOAD = "caseload"
    CLIENT = "client"

    CHOICES = [NON_CASELOAD, CASELOAD, CLIENT]


class Case(db.Model):
    __tablename__ = "cases"

    id = db.Column(db.Integer, primary_key=True)
    # Identifier - auto-generated when name is unknown
    identifier = db.Column(db.String(100), unique=True, nullable=False)

    # Basic info from the form
    full_name = db.Column(db.String(200), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.String(10), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    physical_description = db.Column(db.Text, nullable=True)
    other_contact = db.Column(db.String(200), nullable=True)

    # Location - stored as What3Words address + raw coords
    location_w3w = db.Column(db.String(200), nullable=True)
    location_lat = db.Column(db.Float, nullable=True)
    location_lng = db.Column(db.Float, nullable=True)

    # Voice note - path to stored audio file
    voice_note_path = db.Column(db.String(500), nullable=True)

    # Category - defaults to non-caseload
    category = db.Column(
        db.String(20),
        nullable=False,
        default=CaseCategory.NON_CASELOAD,
    )

    # National Insurance number (required when category is "client").
    # Encrypted at rest (blocker 5) - no query filters on it, so losing
    # SQL searchability costs nothing here.
    ni_number = db.Column(EncryptedText, nullable=True)

    consent_status = db.Column(db.String(20), nullable=False, default="unknown")
    consent_date = db.Column(db.String(10), nullable=True)

    risk_rating = db.Column(db.String(20), nullable=False, default="unknown")
    # Risk and mental health notes are Article 9 special-category data and
    # are encrypted at rest. Dashboard search deliberately does not cover
    # them, so encryption does not break any existing query.
    risk_notes = db.Column(EncryptedText, nullable=True)
    mental_health_notes = db.Column(EncryptedText, nullable=True)
    current_situation = db.Column(db.String(100), nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Foreign key to the social worker who created it
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Relationship to case notes
    notes = db.relationship(
        "CaseNote", backref="case", lazy="dynamic", cascade="all, delete-orphan"
    )

    # Relationship to case actions (caseload category)
    actions = db.relationship(
        "CaseAction", backref="case", lazy="dynamic", cascade="all, delete-orphan"
    )

    interactions = db.relationship(
        "CaseInteraction",
        backref="case",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    follow_up_tasks = db.relationship(
        "FollowUpTask",
        backref="case",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    attachments = db.relationship(
        "CaseAttachment",
        backref="case",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Case {self.identifier}>"
