from sqlalchemy.sql import func

from app.extensions import db


class InteractionTagType:
    WELFARE_CHECK = "welfare_check"
    FOOD_DRINK = "food_drink"
    SLEEPING_BAG = "sleeping_bag"
    TAXI_BOOKED = "taxi_booked"
    GP_SUPPORT = "gp_support"
    HOUSING_SUPPORT = "housing_support"
    BENEFITS_SUPPORT = "benefits_support"
    SIGNPOSTED = "signposted"
    MEDICATION_CHECK = "medication_check"
    OTHER = "other"

    CHOICES = [
        WELFARE_CHECK,
        FOOD_DRINK,
        SLEEPING_BAG,
        TAXI_BOOKED,
        GP_SUPPORT,
        HOUSING_SUPPORT,
        BENEFITS_SUPPORT,
        SIGNPOSTED,
        MEDICATION_CHECK,
        OTHER,
    ]

    LABELS = {
        WELFARE_CHECK: "Welfare check",
        FOOD_DRINK: "Food/drink provided",
        SLEEPING_BAG: "Sleeping bag provided",
        TAXI_BOOKED: "Taxi booked",
        GP_SUPPORT: "GP support",
        HOUSING_SUPPORT: "Housing support",
        BENEFITS_SUPPORT: "Benefits support",
        SIGNPOSTED: "Signposted",
        MEDICATION_CHECK: "Medication check",
        OTHER: "Other",
    }


class CaseInteraction(db.Model):
    __tablename__ = "case_interactions"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    note_content = db.Column(db.Text, nullable=True)
    outcome = db.Column(db.String(200), nullable=True)
    location_w3w = db.Column(db.String(200), nullable=True)
    location_lat = db.Column(db.Float, nullable=True)
    location_lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    worker = db.relationship("User", lazy="select")
    tags = db.relationship(
        "InteractionTag",
        backref="interaction",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    attachments = db.relationship(
        "CaseAttachment",
        backref="interaction",
        lazy="dynamic",
    )


class InteractionTag(db.Model):
    __tablename__ = "interaction_tags"

    id = db.Column(db.Integer, primary_key=True)
    interaction_id = db.Column(db.Integer, db.ForeignKey("case_interactions.id"), nullable=False)
    tag_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
