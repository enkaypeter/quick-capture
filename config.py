import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, "uploads", "cases")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    db_path = os.path.join(basedir, "instance", "database.db")
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    db_path = os.path.join(basedir, "instance", "database.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{db_path}"
    )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
