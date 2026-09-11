import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

# Sentinel values that are safe for local development but must never reach
# production. `app.security.config_guard` refuses to start if it sees one.
DEV_SECRET_KEY = "dev-secret-change-in-production"
DEV_INVITE_CODE = "sots-dev-invite"
DEV_DEMO_PASSWORD = "demo-password-123"


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, "uploads", "cases")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    TRANSCRIPTION_URL = os.environ.get("TRANSCRIPTION_URL", "http://localhost:8080")
    W3W_API_KEY = os.environ.get("W3W_API_KEY", "")
    SIGNUP_INVITE_CODE = os.environ.get("SIGNUP_INVITE_CODE", DEV_INVITE_CODE)
    BOOTSTRAP_INVITE_ENABLED = _env_bool("BOOTSTRAP_INVITE_ENABLED", True)
    DEMO_ACCOUNT_ENABLED = _env_bool("DEMO_ACCOUNT_ENABLED", True)
    DEMO_ACCOUNT_EMAIL = os.environ.get("DEMO_ACCOUNT_EMAIL", "demo@quickcapture.local")
    DEMO_ACCOUNT_PASSWORD = os.environ.get("DEMO_ACCOUNT_PASSWORD", DEV_DEMO_PASSWORD)
    DEMO_ACCOUNT_FIRST_NAME = os.environ.get("DEMO_ACCOUNT_FIRST_NAME", "Demo")
    DEMO_CASES_ENABLED = _env_bool("DEMO_CASES_ENABLED", True)
    # Opt-in to run production with demo account/cases enabled (demo/PoC only).
    ALLOW_DEMO_IN_PRODUCTION = _env_bool("ALLOW_DEMO_IN_PRODUCTION", False)
    # The demo account is shared, so no one person can hold its authenticator.
    # When on, it is kept enrolled and its code prompt accepts any 6 digits.
    DEMO_ACCOUNT_SHARED_MFA = _env_bool("DEMO_ACCOUNT_SHARED_MFA", True)
    # Wipe everything the demo account created and restore the seeded demo
    # cases this often. 0 turns the automatic reset off.
    DEMO_RESET_INTERVAL_MINUTES = _env_int("DEMO_RESET_INTERVAL_MINUTES", 0)

    # --- Session security (blocker 7: session timeout) -------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    # Idle timeout. The cookie is refreshed on every request, so this is time
    # since last activity, not time since login. Short by default because
    # workers carry these sessions on phones in the field.
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=_env_int("SESSION_IDLE_MINUTES", 30)
    )
    SESSION_REFRESH_EACH_REQUEST = True

    # --- Login throttling (blocker 3) ------------------------------------
    LOGIN_MAX_ATTEMPTS_PER_ACCOUNT = _env_int("LOGIN_MAX_ATTEMPTS_PER_ACCOUNT", 5)
    LOGIN_MAX_ATTEMPTS_PER_IP = _env_int("LOGIN_MAX_ATTEMPTS_PER_IP", 20)
    LOGIN_ATTEMPT_WINDOW_MINUTES = _env_int("LOGIN_ATTEMPT_WINDOW_MINUTES", 15)
    LOGIN_LOCKOUT_MINUTES = _env_int("LOGIN_LOCKOUT_MINUTES", 15)

    # --- Field-level encryption (blocker 5) -------------------------------
    # Comma-separated Fernet keys. The first key encrypts; every key is tried
    # when decrypting, which is what makes key rotation possible.
    # Generate with: python -m scripts.generate_keys
    FIELD_ENCRYPTION_KEYS = os.environ.get("FIELD_ENCRYPTION_KEYS", "")

    # --- Multi-factor authentication (blocker 8) --------------------------
    MFA_ISSUER = os.environ.get("MFA_ISSUER", "Quick Capture")
    # Roles that must complete TOTP enrolment before they can use the app.
    MFA_REQUIRED_ROLES = [
        role.strip()
        for role in os.environ.get("MFA_REQUIRED_ROLES", "admin").split(",")
        if role.strip()
    ]

    # --- Access logging (blocker 10) --------------------------------------
    # Repeat views of the same record by the same user inside this window
    # collapse into one entry, so the log stays readable.
    ACCESS_LOG_DEDUPE_MINUTES = _env_int("ACCESS_LOG_DEDUPE_MINUTES", 5)

    # --- Retention and erasure (blocker 11) -------------------------------
    # How long an archived (soft-deleted) case is kept before the retention
    # job purges it permanently. See docs/operations/data-retention.md.
    RETENTION_ARCHIVED_CASE_DAYS = _env_int("RETENTION_ARCHIVED_CASE_DAYS", 2190)
    # Access log rows are operational security data, not casework, and are
    # kept for a shorter period.
    RETENTION_ACCESS_LOG_DAYS = _env_int("RETENTION_ACCESS_LOG_DAYS", 365)
    RETENTION_LOGIN_ATTEMPT_DAYS = _env_int("RETENTION_LOGIN_ATTEMPT_DAYS", 30)

    # --- Security headers (blocker 6) -------------------------------------
    SECURITY_HEADERS_ENABLED = _env_bool("SECURITY_HEADERS_ENABLED", True)
    HSTS_ENABLED = _env_bool("HSTS_ENABLED", False)
    HSTS_MAX_AGE = _env_int("HSTS_MAX_AGE", 31536000)

    # Database - use absolute path to ensure it works in containers
    DB_DIR = os.path.join(basedir, "instance")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(DB_DIR, 'database.db')}"
    )


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration.

    Every value that has a convenient development default is blanked here so
    that `app.security.config_guard.validate_production_config` fails loudly
    rather than the app silently running on a known-public secret.
    """

    DEBUG = False
    SESSION_COOKIE_SECURE = True
    HSTS_ENABLED = _env_bool("HSTS_ENABLED", True)

    # No fallback: an unset SECRET_KEY must stop the app, not be guessed.
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    # The development invite code is published in the README. It must never be
    # the accepted bootstrap code in production.
    SIGNUP_INVITE_CODE = os.environ.get("SIGNUP_INVITE_CODE", "")
    BOOTSTRAP_INVITE_ENABLED = _env_bool("BOOTSTRAP_INVITE_ENABLED", False)
    DEMO_ACCOUNT_ENABLED = _env_bool("DEMO_ACCOUNT_ENABLED", False)
    DEMO_ACCOUNT_PASSWORD = os.environ.get("DEMO_ACCOUNT_PASSWORD", "")
    DEMO_CASES_ENABLED = _env_bool("DEMO_CASES_ENABLED", False)
    ALLOW_DEMO_IN_PRODUCTION = _env_bool("ALLOW_DEMO_IN_PRODUCTION", False)
    DEMO_ACCOUNT_SHARED_MFA = _env_bool("DEMO_ACCOUNT_SHARED_MFA", False)


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    WTF_CSRF_ENABLED = True
    SIGNUP_INVITE_CODE = "test-invite"
    BOOTSTRAP_INVITE_ENABLED = True
    DEMO_ACCOUNT_EMAIL = "demo@quickcapture.local"
    DEMO_ACCOUNT_PASSWORD = DEV_DEMO_PASSWORD
    DEMO_CASES_ENABLED = False
    # Tests use the demo account as an ordinary admin to drive real enrolment.
    DEMO_ACCOUNT_SHARED_MFA = False
    DEMO_RESET_INTERVAL_MINUTES = 0
    DB_DIR = os.path.join(basedir, "instance", "test")
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # A fixed key so encrypted-column tests are deterministic.
    FIELD_ENCRYPTION_KEYS = "kkPU7yhBGhcs3iZzGKmYWDEuOfMSZbn0uhoBOsZTOgU="


config_by_name = {
    "development": DevelopmentConfig,
    "local": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
