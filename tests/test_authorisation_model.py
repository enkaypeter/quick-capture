"""Blocker 9: the access model is flat, and that is a recorded decision.

Every signed-in worker can read every active case, including risk and mental
health notes. That is deliberate for a small outreach team where any worker
may meet any client — see docs/adrs/007-team-wide-case-visibility.md.

These tests exist so the decision cannot change by accident in either
direction: if someone narrows visibility, they will have to update the ADR;
if someone widens an admin-only page to all workers, that will fail here.
"""

from app.extensions import db
from app.models.case import Case
from app.models.user import User
from conftest import login_admin, register

ADMIN_ONLY_PATHS = ["/invite-codes", "/users", "/erasure-log"]


def create_case_as(email, identifier="SOTS-0001", **fields):
    user = User.query.filter_by(email=email).one()
    case = Case(identifier=identifier, user_id=user.id, **fields)
    db.session.add(case)
    db.session.commit()
    return case


def test_a_worker_can_read_a_case_another_worker_created(client, app):
    register(client, "one@example.org")
    case = create_case_as("one@example.org", full_name="Jane Doe")
    client.get("/logout")

    other = app.test_client()
    register(other, "two@example.org")

    assert other.get(f"/cases/{case.id}").status_code == 200


def test_a_worker_can_read_another_worker_s_risk_and_health_notes(client, app):
    """Stated plainly because this is the part that needs a signed-off decision."""
    register(client, "one@example.org")
    case = create_case_as(
        "one@example.org",
        risk_notes="Approach with a colleague.",
        mental_health_notes="Under the care of the crisis team.",
    )
    client.get("/logout")

    other = app.test_client()
    register(other, "two@example.org")
    response = other.get(f"/cases/{case.id}")

    assert b"Approach with a colleague." in response.data


def test_every_case_appears_on_every_worker_s_dashboard(client, app):
    register(client, "one@example.org")
    create_case_as("one@example.org", identifier="SOTS-0001", full_name="Jane Doe")
    client.get("/logout")

    other = app.test_client()
    register(other, "two@example.org")

    assert b"SOTS-0001" in other.get("/cases").data


def test_an_anonymous_visitor_can_read_nothing(client):
    register(client, "one@example.org")
    case = create_case_as("one@example.org")
    client.get("/logout")

    response = client.get(f"/cases/{case.id}")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_new_accounts_are_workers_not_admins(client):
    register(client, "worker@example.org")

    assert User.query.filter_by(email="worker@example.org").one().role == "worker"


def test_admin_only_pages_are_closed_to_workers(client):
    register(client, "worker@example.org")

    for path in ADMIN_ONLY_PATHS:
        assert client.get(path).status_code == 403, path


def test_admin_only_pages_are_open_to_admins(client):
    login_admin(client)

    for path in ADMIN_ONLY_PATHS:
        assert client.get(path).status_code == 200, path


def test_registration_still_requires_an_invite_code(client):
    """The invite code is the only gate on this flat model, so it must hold."""
    from conftest import csrf_token

    token = csrf_token(client, "/sign-up")
    client.post(
        "/sign-up",
        data={
            "csrf_token": token,
            "email": "uninvited@example.org",
            "firstName": "Uninvited",
            "password1": "password123",
            "password2": "password123",
            "invite_code": "not-a-real-code",
        },
        follow_redirects=True,
    )

    assert User.query.filter_by(email="uninvited@example.org").first() is None


def test_the_decision_is_recorded_in_an_adr():
    """The control for a flat model is documentation, so the ADR must exist."""
    import pathlib

    adr = pathlib.Path("docs/adrs/007-team-wide-case-visibility.md")
    assert adr.is_file()
    assert "team-wide" in adr.read_text().lower()
