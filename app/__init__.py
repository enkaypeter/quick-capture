import os

from flask import Flask, session
from flask_login import current_user

from config import config_by_name


def create_app(config_name: str = None) -> Flask:
    """Application factory.

    Args:
        config_name: One of 'development', 'production', 'testing'. Defaults
                     to the FLASK_ENV environment variable or 'development'.

    Raises:
        ConfigurationError: if the production configuration is unsafe. See
            app/security/config_guard.py - this is deliberate, so that a
            missing SECRET_KEY stops the app rather than silently defaulting.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    if config_name == "production":
        from app.security.config_guard import validate_production_config

        validate_production_config(app.config)

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

    from app import models  # noqa: F401

    # Register blueprints
    from app.views import auth_bp, cases_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(cases_bp)

    from app.services.csrf_service import init_csrf
    init_csrf(app)

    from app.security.headers import init_security_headers
    init_security_headers(app)

    _init_session_timeout(app)
    _init_mfa_enforcement(app)

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

        # Run migrations for existing databases (adds new columns/tables)
        from app.migrations import run_migrations
        run_migrations()

        from app.services.seed_service import seed_demo_account, seed_demo_cases
        demo_user = seed_demo_account()
        seed_demo_cases(demo_user)

    return app


def _init_session_timeout(app):
    """Make every session permanent so PERMANENT_SESSION_LIFETIME applies.

    Blocker 7. Flask only enforces an expiry on permanent sessions. Combined
    with SESSION_REFRESH_EACH_REQUEST this gives an idle timeout: the cookie
    is re-issued on activity and expires after a period of inactivity, which
    is the behaviour wanted for a phone left in a van.
    """

    @app.before_request
    def _make_session_permanent():
        session.permanent = True


def _init_mfa_enforcement(app):
    """Send users whose role requires MFA to enrolment before anything else.

    Blocker 8. Enforcing this in one place rather than per-route means a new
    admin page cannot accidentally be reachable without MFA.
    """
    from flask import redirect, request, url_for

    # Endpoints reachable while a required user has not yet enrolled.
    EXEMPT_ENDPOINTS = {
        "auth.logout",
        "auth.mfa_setup",
        "auth.mfa_confirm",
        "auth.mfa_verify",
        "cases.landing",
        "cases.service_worker",
        "static",
    }

    @app.before_request
    def _require_mfa_enrolment():
        if request.endpoint in EXEMPT_ENDPOINTS or request.endpoint is None:
            return None
        if not current_user.is_authenticated:
            return None

        from app.services.mfa_service import MfaService

        if MfaService().needs_enrolment(
            current_user, app.config["MFA_REQUIRED_ROLES"]
        ):
            return redirect(url_for("auth.mfa_setup"))

        return None
