"""Login throttling and account lockout.

Blocker 3. `/login` previously accepted unlimited attempts, which makes
credential stuffing against a small, guessable set of charity email addresses
trivial.

Two independent limits are applied:

* per account - protects one worker's password from being guessed
* per IP address - protects the whole staff list from being sprayed at once

State lives in the `login_attempts` table rather than process memory because
production runs several gunicorn workers, and an in-memory counter would give
an attacker one full allowance per worker.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.extensions import db
from app.models.login_attempt import LoginAttempt
from app.models.user import User


@dataclass
class ThrottleDecision:
    """The outcome of a throttle check."""

    allowed: bool
    retry_after_seconds: int = 0
    reason: Optional[str] = None

    @property
    def retry_after_minutes(self) -> int:
        """Whole minutes, rounded up, for display to the user."""
        return max(1, -(-self.retry_after_seconds // 60))


class LoginThrottleService:
    def __init__(
        self,
        max_attempts_per_account: int = 5,
        max_attempts_per_ip: int = 20,
        window_minutes: int = 15,
        lockout_minutes: int = 15,
    ):
        self.max_attempts_per_account = max_attempts_per_account
        self.max_attempts_per_ip = max_attempts_per_ip
        self.window_minutes = window_minutes
        self.lockout_minutes = lockout_minutes

    @classmethod
    def from_config(cls, config) -> "LoginThrottleService":
        return cls(
            max_attempts_per_account=config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"],
            max_attempts_per_ip=config["LOGIN_MAX_ATTEMPTS_PER_IP"],
            window_minutes=config["LOGIN_ATTEMPT_WINDOW_MINUTES"],
            lockout_minutes=config["LOGIN_LOCKOUT_MINUTES"],
        )

    # --- Checks ----------------------------------------------------------

    def check(self, email: Optional[str], ip_address: Optional[str]) -> ThrottleDecision:
        """Decide whether this login attempt may proceed."""
        email = self._normalise_email(email)
        now = datetime.now(UTC)

        user = User.query.filter_by(email=email).first() if email else None
        if user and user.locked_until:
            locked_until = self._as_aware(user.locked_until)
            if locked_until > now:
                return ThrottleDecision(
                    allowed=False,
                    retry_after_seconds=int((locked_until - now).total_seconds()),
                    reason="account_locked",
                )

        if email:
            account_failures = self._recent_failures(email=email)
            if account_failures >= self.max_attempts_per_account:
                return ThrottleDecision(
                    allowed=False,
                    retry_after_seconds=self.lockout_minutes * 60,
                    reason="account_locked",
                )

        if ip_address:
            ip_failures = self._recent_failures(ip_address=ip_address)
            if ip_failures >= self.max_attempts_per_ip:
                return ThrottleDecision(
                    allowed=False,
                    retry_after_seconds=self.lockout_minutes * 60,
                    reason="ip_throttled",
                )

        return ThrottleDecision(allowed=True)

    # --- Recording -------------------------------------------------------

    def record_failure(
        self, email: Optional[str], ip_address: Optional[str]
    ) -> ThrottleDecision:
        """Record a failed attempt and lock the account if it tipped the limit."""
        email = self._normalise_email(email)
        self._record(email, ip_address, successful=False)

        if not email:
            return ThrottleDecision(allowed=True)

        failures = self._recent_failures(email=email)
        if failures < self.max_attempts_per_account:
            return ThrottleDecision(allowed=True)

        user = User.query.filter_by(email=email).first()
        if user:
            user.locked_until = datetime.now(UTC) + timedelta(
                minutes=self.lockout_minutes
            )
            db.session.commit()

        return ThrottleDecision(
            allowed=False,
            retry_after_seconds=self.lockout_minutes * 60,
            reason="account_locked",
        )

    def record_success(self, email: Optional[str], ip_address: Optional[str]) -> None:
        """Record a successful login and clear the account's failure state."""
        email = self._normalise_email(email)
        self._record(email, ip_address, successful=True)

        if not email:
            return

        # Clearing past failures is what stops a successful login from being
        # followed by a lockout triggered by earlier typos.
        LoginAttempt.query.filter_by(email=email, successful=False).delete()

        user = User.query.filter_by(email=email).first()
        if user and user.locked_until:
            user.locked_until = None

        db.session.commit()

    def unlock(self, user: User) -> None:
        """Administratively clear a lockout."""
        user.locked_until = None
        LoginAttempt.query.filter_by(email=user.email, successful=False).delete()
        db.session.commit()

    # --- Maintenance -----------------------------------------------------

    def prune(self, older_than_days: int) -> int:
        """Delete attempt rows past their retention period. Returns the count."""
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        deleted = LoginAttempt.query.filter(LoginAttempt.created_at < cutoff).delete()
        db.session.commit()
        return deleted

    # --- Internals -------------------------------------------------------

    def _record(
        self, email: Optional[str], ip_address: Optional[str], successful: bool
    ) -> None:
        db.session.add(
            LoginAttempt(
                email=email,
                ip_address=ip_address,
                successful=successful,
            )
        )
        db.session.commit()

    def _recent_failures(
        self, email: Optional[str] = None, ip_address: Optional[str] = None
    ) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=self.window_minutes)
        query = LoginAttempt.query.filter(
            LoginAttempt.successful.is_(False),
            LoginAttempt.created_at >= cutoff,
        )
        if email:
            query = query.filter(LoginAttempt.email == email)
        if ip_address:
            query = query.filter(LoginAttempt.ip_address == ip_address)
        return query.count()

    @staticmethod
    def _normalise_email(email: Optional[str]) -> Optional[str]:
        return email.strip().lower() if email else None

    @staticmethod
    def _as_aware(value: datetime) -> datetime:
        """SQLite hands back naive datetimes; treat them as UTC."""
        return value if value.tzinfo else value.replace(tzinfo=UTC)
