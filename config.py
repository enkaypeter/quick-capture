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


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
