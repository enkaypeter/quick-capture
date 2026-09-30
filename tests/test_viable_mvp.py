from datetime import date

from app.extensions import db
from app.models.case import Case
from app.models.case_attachment import CaseAttachment
from app.models.case_interaction import CaseInteraction, InteractionTag
from app.models.follow_up_task import FollowUpTask
from app.models.invite_code import InviteCode, InviteCodeStatus
from app.models.user import User
from app.services.seed_service import seed_demo_cases

from conftest import csrf_token, login, login_admin, register


def create_case(client, **overrides):
    token = csrf_token(client, "/cases/new")
    data = {
        "csrf_token": token,
        "full_name": "Known Person",
        "phone_number": "07123 456789",
        "location_w3w": "filled.count.soap",
        "notes": "Initial contact",
        "category": "non-caseload",
        "risk_rating": "amber",
        "current_situation": "rough_sleeping",
    }
    data.update(overrides)
    return client.post("/cases/new", data=data, follow_redirects=False)


def dob_for_age(age):
    today = date.today()
    return today.replace(year=today.year - age).isoformat()


def test_signup_requires_invite_code(client):
    token = csrf_token(client, "/sign-up")
    response = client.post(
        "/sign-up",
        data={
            "csrf_token": token,
            "email": "worker@example.org",
            "firstName": "Worker",
            "password1": "password123",
            "password2": "password123",
            "invite_code": "wrong",
        },
        follow_redirects=True,
    )

    assert b"Invalid invite code" in response.data


def test_demo_admin_account_is_seeded(client):
    response = login_admin(client)

    assert response.status_code == 200
    assert b"Cases" in response.data
    assert b"Invite Codes" in response.data


def test_demo_cases_are_seeded_for_local_demo_account(app, client):
    app.config["DEMO_CASES_ENABLED"] = True
    demo_user = User.query.filter_by(email="demo@quickcapture.local").one()

    seed_demo_cases(demo_user)
    seed_demo_cases(demo_user)

    demo_cases = Case.query.filter(Case.identifier.like("DEMO-%")).all()
    assert len(demo_cases) == 10
    assert {case.category for case in demo_cases} == {"non-caseload", "caseload", "client"}
    assert {case.risk_rating for case in demo_cases} >= {"green", "amber", "red"}
    assert CaseInteraction.query.count() >= 10
    assert InteractionTag.query.count() >= 10
    assert FollowUpTask.query.count() >= 8
    assert CaseAttachment.query.count() >= 4

    login_admin(client)
    response = client.get("/cases")
    assert b"DEMO-OUTREACH-001" in response.data
    assert b"Demo Alex Reed" in response.data


def test_admin_can_create_invite_code_and_signup_consumes_it(client):
    login_admin(client)
    token = csrf_token(client, "/invite-codes")

    response = client.post(
        "/invite-codes",
        data={"csrf_token": token, "label": "New worker", "max_uses": "1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    invite = InviteCode.query.one()
    assert invite.label == "New worker"
    assert invite.status == InviteCodeStatus.ACTIVE
    assert invite.code.encode() in response.data

    client.get("/logout")
    token = csrf_token(client, "/sign-up")
    response = client.post(
        "/sign-up",
        data={
            "csrf_token": token,
            "email": "invited@example.org",
            "firstName": "Invited",
            "password1": "password123",
            "password2": "password123",
            "invite_code": invite.code,
        },
        follow_redirects=True,
    )

    db.session.refresh(invite)
    assert response.status_code == 200
    assert invite.uses == 1
    assert invite.status == InviteCodeStatus.USED


def test_invite_code_max_uses_defaults_when_input_is_invalid(client):
    login_admin(client)
    token = csrf_token(client, "/invite-codes")

    response = client.post(
        "/invite-codes",
        data={"csrf_token": token, "label": "Invalid uses", "max_uses": "many"},
        follow_redirects=True,
    )

    invite = InviteCode.query.one()
    assert response.status_code == 200
    assert invite.max_uses == 1


def test_admin_can_deny_unused_invite_code(client):
    login_admin(client)
    token = csrf_token(client, "/invite-codes")
    client.post(
        "/invite-codes",
        data={"csrf_token": token, "label": "Do not approve", "max_uses": "1"},
    )
    invite = InviteCode.query.one()

    token = csrf_token(client, "/invite-codes")
    response = client.post(
        f"/invite-codes/{invite.id}/deny",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    db.session.refresh(invite)

    assert response.status_code == 200
    assert invite.status == InviteCodeStatus.DENIED

    client.get("/logout")
    token = csrf_token(client, "/sign-up")
    response = client.post(
        "/sign-up",
        data={
            "csrf_token": token,
            "email": "denied@example.org",
            "firstName": "Denied",
            "password1": "password123",
            "password2": "password123",
            "invite_code": invite.code,
        },
        follow_redirects=True,
    )

    assert b"Invalid invite code" in response.data


def test_invite_code_admin_page_is_admin_only(client):
    register(client, "worker@example.org")

    response = client.get("/invite-codes")

    assert response.status_code == 403


def test_csrf_required_for_state_change(client):
    response = client.post(
        "/sign-up",
        data={
            "email": "worker@example.org",
            "firstName": "Worker",
            "password1": "password123",
            "password2": "password123",
            "invite_code": "test-invite",
        },
    )

    assert response.status_code == 400


def test_service_worker_is_available_for_offline_shell(client):
    response = client.get("/service-worker.js")

    assert response.status_code == 200
    assert "quick-capture-v1" in response.get_data(as_text=True)


def test_empty_case_is_rejected(client):
    register(client, "worker@example.org")
    token = csrf_token(client, "/cases/new")

    response = client.post(
        "/cases/new",
        data={"csrf_token": token, "category": "non-caseload"},
        follow_redirects=True,
    )

    assert b"Add at least one identifying detail" in response.data
    assert Case.query.count() == 0


def test_case_status_is_replaced_by_project_everywhere(client):
    register(client, "worker@example.org")

    create_page = client.get("/cases/new")
    assert b"Case status" not in create_page.data
    assert b"Project" in create_page.data

    create_case(client)
    case = Case.query.one()
    detail_page = client.get(f"/cases/{case.id}")
    assert b"Case status" not in detail_page.data
    assert b"Project" in detail_page.data


def test_date_of_birth_autofills_age_on_create(client):
    register(client, "worker@example.org")

    response = create_case(client, age="", date_of_birth=dob_for_age(42))
    case = Case.query.one()

    assert response.status_code == 302
    assert case.age == 42


def test_date_of_birth_overrides_stale_age_on_edit(client):
    register(client, "worker@example.org")
    create_case(client, age="55", date_of_birth=dob_for_age(55))
    case = Case.query.one()

    token = csrf_token(client, f"/cases/{case.id}")
    response = client.post(
        f"/cases/{case.id}/edit",
        json={"date_of_birth": dob_for_age(31), "age": "55"},
        headers={"X-CSRFToken": token},
    )
    db.session.refresh(case)

    assert response.status_code == 200
    assert case.age == 31


def test_cases_are_team_visible_and_searchable(client):
    register(client, "one@example.org", first_name="One")
    response = create_case(client, full_name="Blue Hat", physical_description="Blue coat")
    assert response.status_code == 302
    client.get("/logout")

    register(client, "two@example.org", first_name="Two")

    dashboard = client.get("/dashboard?q=Blue")
    assert b"Blue Hat" in dashboard.data

    case = Case.query.filter_by(full_name="Blue Hat").one()
    detail = client.get(f"/cases/{case.id}")
    assert detail.status_code == 200
    assert b"Support Provided" in detail.data


def test_identifier_generation_does_not_reuse_archived_identifiers(client):
    register(client, "worker@example.org")
    create_case(client, full_name="One", notes="Alpha", location_w3w="zed.zed.zed")
    create_case(client, full_name="Two", notes="Alpha", location_w3w="zed.zed.zed")

    first = Case.query.filter_by(full_name="One").one()
    token = csrf_token(client, f"/cases/{first.id}")
    client.post(f"/cases/{first.id}/delete", data={"csrf_token": token})

    response = create_case(client, full_name="Three", notes="Alpha", location_w3w="zed.zed.zed")
    assert response.status_code == 302
    identifiers = [case.identifier for case in Case.query.order_by(Case.id).all()]
    assert identifiers == ["ZED-ALPHA-001", "ZED-ALPHA-002", "ZED-ALPHA-003"]


def test_notes_are_sanitized_before_rendering(client):
    register(client, "worker@example.org")
    create_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    client.post(
        f"/cases/{case.id}/notes",
        data={"csrf_token": token, "content": "<p>Safe</p><script>alert(1)</script>"},
        follow_redirects=True,
    )

    detail = client.get(f"/cases/{case.id}")
    assert b"alert(1)" not in detail.data
    assert b"Safe" in detail.data


def test_quick_interaction_tags_drive_reports(client):
    register(client, "worker@example.org")
    create_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    response = client.post(
        f"/cases/{case.id}/interactions",
        data={
            "csrf_token": token,
            "tags": ["welfare_check", "food_drink"],
            "interaction_note": "Bought coffee and checked welfare",
            "outcome": "Settled",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert CaseInteraction.query.count() == 1
    assert InteractionTag.query.count() == 2

    report = client.get("/reports")
    assert b"Welfare check" in report.data
    assert b"Food/drink provided" in report.data

    export = client.get("/reports/export.csv")
    assert export.status_code == 200
    assert "Welfare check; Food/drink provided" in export.get_data(as_text=True)


def test_follow_up_tasks_can_be_added_and_completed(client):
    register(client, "worker@example.org")
    create_case(client)
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    client.post(
        f"/cases/{case.id}/follow-ups",
        data={"csrf_token": token, "title": "Check GP appointment", "due_date": "2026-09-10"},
    )

    task = FollowUpTask.query.one()
    assert task.status == "open"

    token = csrf_token(client, f"/cases/{case.id}")
    client.post(
        f"/cases/{case.id}/follow-ups/{task.id}/complete",
        data={"csrf_token": token},
    )
    db.session.refresh(task)
    assert task.status == "done"


def test_archive_hides_case_without_deleting_record(client):
    register(client, "worker@example.org")
    create_case(client, full_name="Archive Me")
    case = Case.query.one()
    token = csrf_token(client, f"/cases/{case.id}")

    client.post(f"/cases/{case.id}/delete", data={"csrf_token": token})
    db.session.refresh(case)

    assert case.archived_at is not None
    assert Case.query.count() == 1
    assert b"Archive Me" not in client.get("/dashboard").data
