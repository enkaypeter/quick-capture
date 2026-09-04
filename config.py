import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, "uploads", "cases")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    TRANSCRIPTION_URL = os.environ.get("TRANSCRIPTION_URL", "http://localhost:8080")
    W3W_API_KEY = os.environ.get("W3W_API_KEY", "")
    SIGNUP_INVITE_CODE = os.environ.get("SIGNUP_INVITE_CODE", "sots-dev-invite")
    BOOTSTRAP_INVITE_ENABLED = (
        os.environ.get("BOOTSTRAP_INVITE_ENABLED", "true").lower() == "true"
    )
    DEMO_ACCOUNT_ENABLED = os.environ.get("DEMO_ACCOUNT_ENABLED", "true").lower() == "true"
    DEMO_ACCOUNT_EMAIL = os.environ.get("DEMO_ACCOUNT_EMAIL", "demo@quickcapture.local")
    DEMO_ACCOUNT_PASSWORD = os.environ.get("DEMO_ACCOUNT_PASSWORD", "demo-password-123")
    DEMO_ACCOUNT_FIRST_NAME = os.environ.get("DEMO_ACCOUNT_FIRST_NAME", "Demo")
    DEMO_CASES_ENABLED = os.environ.get("DEMO_CASES_ENABLED", "true").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

    # Database - use absolute path to ensure it works in containers
    DB_DIR = os.path.join(basedir, "instance")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(DB_DIR, 'database.db')}"
    )


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True
    BOOTSTRAP_INVITE_ENABLED = (
        os.environ.get("BOOTSTRAP_INVITE_ENABLED", "false").lower() == "true"
    )
    DEMO_ACCOUNT_ENABLED = os.environ.get("DEMO_ACCOUNT_ENABLED", "false").lower() == "true"
    DEMO_CASES_ENABLED = os.environ.get("DEMO_CASES_ENABLED", "false").lower() == "true"


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    WTF_CSRF_ENABLED = True
    SIGNUP_INVITE_CODE = "test-invite"
    BOOTSTRAP_INVITE_ENABLED = True
    DEMO_ACCOUNT_EMAIL = "demo@quickcapture.local"
    DEMO_ACCOUNT_PASSWORD = "demo-password-123"
    DEMO_CASES_ENABLED = False
    DB_DIR = os.path.join(basedir, "instance", "test")
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_by_name = {
    "development": DevelopmentConfig,
    "local": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
