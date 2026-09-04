import secrets

from flask import abort, request, session


CSRF_SESSION_KEY = "_csrf_token"


def get_csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def init_csrf(app):
    @app.before_request
    def protect_state_changes():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return

        expected = session.get(CSRF_SESSION_KEY)
        supplied = (
            request.form.get("csrf_token")
            or request.headers.get("X-CSRFToken")
            or request.headers.get("X-CSRF-Token")
        )

        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(400, description="Invalid CSRF token")

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": get_csrf_token}
