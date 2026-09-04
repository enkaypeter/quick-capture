"""Time-based one-time password (TOTP) multi-factor authentication.

Blocker 8. An admin account can create invite codes, read every case and
permanently erase records. A password alone is not a proportionate control
for that, especially on shared devices used in the field.

Enrolment is a two-step flow deliberately: a secret is generated and shown,
but `mfa_enabled` only becomes true once the user has proved they can
generate a code from it. That prevents locking someone out of their own
account with a secret their authenticator never actually received.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import List, Optional, Tuple

import pyotp
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.user import MfaRecoveryCode, User

RECOVERY_CODE_COUNT = 8
# Number of 30-second steps either side of now that are accepted. One step
# tolerates a slow typist and modest clock drift without meaningfully
# widening the window.
TOTP_VALID_WINDOW = 1


@dataclass
class MfaEnrolment:
    """Everything the setup page needs to show, and nothing it does not."""

    secret: str
    provisioning_uri: str
    recovery_codes: List[str]


class MfaService:
    def is_required_for(self, user: User, required_roles: List[str]) -> bool:
        """Whether this user's role obliges them to enrol."""
        return getattr(user, "role", None) in required_roles

    def needs_enrolment(self, user: User, required_roles: List[str]) -> bool:
        """Whether this user must enrol before using the app."""
        return self.is_required_for(user, required_roles) and not user.mfa_enabled

    # --- Enrolment -------------------------------------------------------

    def begin_enrolment(self, user: User, issuer: str) -> MfaEnrolment:
        """Generate (but do not activate) a new TOTP secret for a user.

        Calling this again before confirmation replaces the pending secret,
        which is the recovery path for someone who lost the QR code.
        """
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.mfa_enabled = False
        user.mfa_confirmed_at = None
        db.session.commit()

        provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name=issuer
        )

        return MfaEnrolment(
            secret=secret,
            provisioning_uri=provisioning_uri,
            # Shown alongside the QR code so the user records them at the same
            # time. They are only persisted once enrolment is confirmed.
            recovery_codes=[],
        )

    def confirm_enrolment(
        self, user: User, code: str
    ) -> Tuple[bool, Optional[str], List[str]]:
        """Activate MFA once the user proves they can generate a valid code.

        Returns (success, error_message, recovery_codes).
        """
        if not user.totp_secret:
            return False, "Start setup again - no pending secret was found.", []

        if not self._verify_totp(user.totp_secret, code):
            return False, "That code was not correct. Try the next one.", []

        user.mfa_enabled = True
        user.mfa_confirmed_at = datetime.now(UTC)
        recovery_codes = self._issue_recovery_codes(user)
        db.session.commit()

        return True, None, recovery_codes

    def disable(self, user: User) -> None:
        """Turn MFA off and destroy the secret and any unused recovery codes."""
        user.totp_secret = None
        user.mfa_enabled = False
        user.mfa_confirmed_at = None
        MfaRecoveryCode.query.filter_by(user_id=user.id).delete()
        db.session.commit()

    # --- Verification ----------------------------------------------------

    def verify(self, user: User, code: str) -> Tuple[bool, Optional[str]]:
        """Verify a login-time code, accepting either a TOTP or a recovery code."""
        code = (code or "").strip().replace(" ", "")
        if not code:
            return False, "Enter the 6-digit code from your authenticator app."

        if user.totp_secret and self._verify_totp(user.totp_secret, code):
            return True, None

        if self._consume_recovery_code(user, code):
            return True, None

        return False, "That code was not correct. Try again."

    def unused_recovery_code_count(self, user: User) -> int:
        return MfaRecoveryCode.query.filter_by(
            user_id=user.id, used_at=None
        ).count()

    def regenerate_recovery_codes(self, user: User) -> List[str]:
        """Replace every recovery code. Previously issued codes stop working."""
        MfaRecoveryCode.query.filter_by(user_id=user.id).delete()
        codes = self._issue_recovery_codes(user)
        db.session.commit()
        return codes

    # --- Internals -------------------------------------------------------

    @staticmethod
    def _verify_totp(secret: str, code: str) -> bool:
        code = (code or "").strip().replace(" ", "")
        if not code:
            return False
        return pyotp.TOTP(secret).verify(code, valid_window=TOTP_VALID_WINDOW)

    def _issue_recovery_codes(self, user: User) -> List[str]:
        """Create fresh recovery codes, returning the plaintext to show once."""
        codes = []
        for _ in range(RECOVERY_CODE_COUNT):
            # Grouped for legibility when written on paper.
            code = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}"
            codes.append(code)
            db.session.add(
                MfaRecoveryCode(
                    user_id=user.id,
                    code_hash=generate_password_hash(code, method="pbkdf2:sha256"),
                )
            )
        db.session.flush()
        return codes

    def _consume_recovery_code(self, user: User, code: str) -> bool:
        """Match and burn a recovery code. Each one works exactly once."""
        candidates = MfaRecoveryCode.query.filter_by(
            user_id=user.id, used_at=None
        ).all()

        for candidate in candidates:
            if check_password_hash(candidate.code_hash, code):
                candidate.used_at = datetime.now(UTC)
                db.session.commit()
                return True

        return False
