import re

import pyotp
import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_token(client, path="/login"):
    response = client.get(path)
    match = re.search(r'name="csrf-token" content="([^"]+)"', response.get_data(as_text=True))
    assert match, response.get_data(as_text=True)
    return match.group(1)


def register(client, email, first_name="Alex", password="password123"):
    token = csrf_token(client, "/sign-up")
    return client.post(
        "/sign-up",
        data={
            "csrf_token": token,
            "email": email,
            "firstName": first_name,
            "password1": password,
            "password2": password,
            "invite_code": "test-invite",
        },
        follow_redirects=True,
    )


def login(client, email, password="password123"):
    token = csrf_token(client, "/login")
    return client.post(
        "/login",
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=True,
    )


def enrol_mfa(client, email):
    """Complete TOTP enrolment for the signed-in user, as the UI would.

    Admin accounts are redirected to /mfa/setup until they enrol (blocker 8),
    so tests that exercise admin pages have to get through enrolment first.
    This drives the real two-step flow rather than setting the flag directly,
    which keeps it honest about what a user actually has to do.
    """
    from app.models.user import User

    token = csrf_token(client, "/mfa/setup")
    user = User.query.filter_by(email=email).one()
    code = pyotp.TOTP(user.totp_secret).now()

    return client.post(
        "/mfa/setup",
        data={"csrf_token": token, "code": code},
        follow_redirects=True,
    )


def login_admin(client, email="demo@quickcapture.local", password="demo-password-123"):
    """Sign in as an admin and clear the mandatory MFA enrolment gate."""
    login(client, email, password)
    enrol_mfa(client, email)
    return client.get("/dashboard", follow_redirects=True)


def current_totp(email):
    """The code an authenticator app would be showing for this user right now."""
    from app.models.user import User

    user = User.query.filter_by(email=email).one()
    return pyotp.TOTP(user.totp_secret).now()
