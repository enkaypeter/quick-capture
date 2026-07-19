from sqlalchemy.sql import func

from app.extensions import db


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

    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    # Foreign key to the social worker who created it
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Relationship to case notes
    notes = db.relationship(
        "CaseNote", backref="case", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Case {self.identifier}>"
