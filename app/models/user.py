from flask_login import UserMixin
from sqlalchemy.sql import func

from app.extensions import db
from app.security.crypto import EncryptedText


class UserRole:
    WORKER = "worker"
    ADMIN = "admin"

    CHOICES = [WORKER, ADMIN]


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=UserRole.WORKER)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    # --- Multi-factor authentication (blocker 8) --------------------------
    # The TOTP shared secret is a credential in its own right: whoever reads
    # it can generate valid codes forever. Encrypted at rest for the same
    # reason the password is hashed.
    totp_secret = db.Column(EncryptedText, nullable=True)
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    mfa_confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Lockout state (blocker 3) ----------------------------------------
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    cases = db.relationship(
        "Case",
        foreign_keys="Case.user_id",
        backref="worker",
        lazy="dynamic",
    )
    assigned_cases = db.relationship(
        "Case",
        foreign_keys="Case.assigned_user_id",
        backref="assigned_worker",
        lazy="dynamic",
    )
    recovery_codes = db.relationship(
        "MfaRecoveryCode",
        backref="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def __repr__(self):
        return f"<User {self.email}>"


class MfaRecoveryCode(db.Model):
    """Single-use codes for a user who has lost their authenticator app.

    Without these, an admin who loses their phone locks the charity out of
    its own case records. Stored hashed, like passwords.
    """

    __tablename__ = "mfa_recovery_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code_hash = db.Column(db.String(256), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())

    def __repr__(self):
        state = "used" if self.used_at else "unused"
        return f"<MfaRecoveryCode user={self.user_id} {state}>"
