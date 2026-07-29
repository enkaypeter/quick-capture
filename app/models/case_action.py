from sqlalchemy.sql import func

from app.extensions import db


class PredefinedAction:
    """Predefined actions available for caseload cases."""

    HOME_VISIT = "home_visit"
    REFERRAL_GP = "referral_gp"
    BENEFITS_APPLICATION = "benefits_application"
    HOUSING_REFERRAL = "housing_referral"
    MENTAL_HEALTH_REFERRAL = "mental_health_referral"
    SUBSTANCE_SUPPORT = "substance_support"
    FOOD_BANK_REFERRAL = "food_bank_referral"
    APPOINTMENT_BOOKED = "appointment_booked"

    CHOICES = [
        HOME_VISIT,
        REFERRAL_GP,
        BENEFITS_APPLICATION,
        HOUSING_REFERRAL,
        MENTAL_HEALTH_REFERRAL,
        SUBSTANCE_SUPPORT,
        FOOD_BANK_REFERRAL,
        APPOINTMENT_BOOKED,
    ]

    LABELS = {
        HOME_VISIT: "Home visit",
        REFERRAL_GP: "Referral to GP",
        BENEFITS_APPLICATION: "Benefits application",
        HOUSING_REFERRAL: "Housing referral",
        MENTAL_HEALTH_REFERRAL: "Mental health referral",
        SUBSTANCE_SUPPORT: "Substance misuse support",
        FOOD_BANK_REFERRAL: "Food bank referral",
        APPOINTMENT_BOOKED: "Appointment booked",
    }


class CaseAction(db.Model):
    __tablename__ = "case_actions"

    id = db.Column(db.Integer, primary_key=True)

    # Parent case
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False)

    # Action type: one of PredefinedAction.CHOICES or "custom"
    action_type = db.Column(db.String(50), nullable=False)

    # Human-readable label (predefined label or user-entered custom text)
    label = db.Column(db.String(200), nullable=False)

    # Whether this action has been completed
    completed = db.Column(db.Boolean, nullable=False, default=False)

    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        return f"<CaseAction {self.id} type={self.action_type} completed={self.completed}>"
