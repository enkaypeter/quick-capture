import os

from flask import Flask

from config import config_by_name


def create_app(config_name: str = None) -> Flask:
    """Application factory.

    Args:
        config_name: One of 'development', 'production'. Defaults to
                     the FLASK_ENV environment variable or 'development'.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Ensure required directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["DB_DIR"], exist_ok=True)
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)

    # Initialize extensions
    from app.extensions import db, login_manager

    db.init_app(app)
    login_manager.init_app(app)

    # User loader
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.views import auth_bp, cases_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(cases_bp)

    # Create database tables and set SQLite WAL mode
    with app.app_context():
        from sqlalchemy import event

        @event.listens_for(db.engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        db.create_all()

    return app
