import re

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
