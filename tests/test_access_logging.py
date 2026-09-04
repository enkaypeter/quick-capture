"""Blocker 10: recording who read case data, not just who changed it."""

from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models.access_log import AccessAction, AccessLog
from app.models.case import Case
from app.models.user import User
from app.services.access_log_service import AccessLogService
from conftest import csrf_token, login_admin, register


def create_case(identifier="SOTS-0001", **fields):
    user = User.query.first()
    case = Case(identifier=identifier, user_id=user.id, **fields)
    db.session.add(case)
    db.session.commit()
    return case


def test_viewing_a_case_is_recorded(client):
    register(client, "worker@example.org")
    case = create_case()

    client.get(f"/cases/{case.id}")

    entry = AccessLog.query.filter_by(action=AccessAction.VIEWED_CASE).one()
    assert entry.case_id == case.id
    assert entry.user.email == "worker@example.org"


def test_the_entry_records_who_when_and_from_where(client):
    register(client, "worker@example.org")
    case = create_case()

    client.get(f"/cases/{case.id}", headers={"User-Agent": "TestBrowser/1.0"})

    entry = AccessLog.query.filter_by(action=AccessAction.VIEWED_CASE).one()
    assert entry.user_id is not None
    assert entry.created_at is not None
    assert entry.ip_address
    assert entry.user_agent == "TestBrowser/1.0"


def test_repeat_views_inside_the_window_collapse_into_one_entry(client):
    """A worker scrolling one case must not bury the log in noise."""
    register(client, "worker@example.org")
    case = create_case()

    for _ in range(5):
        client.get(f"/cases/{case.id}")

    assert AccessLog.query.filter_by(action=AccessAction.VIEWED_CASE).count() == 1


def test_a_view_after_the_window_is_recorded_again(client, app):
    register(client, "worker@example.org")
    case = create_case()
    client.get(f"/cases/{case.id}")

    stale = datetime.now(UTC) - timedelta(
        minutes=app.config["ACCESS_LOG_DEDUPE_MINUTES"] + 1
    )
    AccessLog.query.update({AccessLog.created_at: stale})
    db.session.commit()

    client.get(f"/cases/{case.id}")

    assert AccessLog.query.filter_by(action=AccessAction.VIEWED_CASE).count() == 2


def test_two_workers_viewing_the_same_case_are_logged_separately(client, app):
    register(client, "one@example.org")
    case = create_case()
    client.get(f"/cases/{case.id}")
    client.get("/logout")

    other = app.test_client()
    register(other, "two@example.org")
    other.get(f"/cases/{case.id}")

    emails = {
        entry.user.email
        for entry in AccessLog.query.filter_by(action=AccessAction.VIEWED_CASE).all()
    }
    assert emails == {"one@example.org", "two@example.org"}


def test_downloading_an_attachment_is_recorded(client):
    register(client, "worker@example.org")
    case = create_case()
    token = csrf_token(client, f"/cases/{case.id}")
    client.post(
        f"/cases/{case.id}/attachments",
        data={
            "csrf_token": token,
            "attachment": (__import__("io").BytesIO(b"support plan"), "plan.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    from app.models.case_attachment import CaseAttachment

    attachment = CaseAttachment.query.one()

    client.get(f"/attachments/{attachment.id}")

    entry = AccessLog.query.filter_by(
        action=AccessAction.DOWNLOADED_ATTACHMENT
    ).one()
    assert entry.resource == f"attachment:{attachment.id}"


def test_exporting_the_csv_is_recorded(client):
    register(client, "worker@example.org")

    client.get("/reports/export.csv")

    assert AccessLog.query.filter_by(action=AccessAction.EXPORTED_REPORT).count() == 1


def test_searching_is_recorded_without_storing_the_search_term(client):
    """The term is usually a person's name; the log must not become case data."""
    register(client, "worker@example.org")

    client.get("/dashboard?q=Jane%20Doe")

    entry = AccessLog.query.filter_by(action=AccessAction.SEARCHED).one()
    assert entry.resource is None
    assert "Jane" not in (entry.resource or "")


def test_viewing_the_audit_trail_is_itself_recorded(client):
    register(client, "worker@example.org")
    case = create_case()

    client.get(f"/cases/{case.id}/audit")

    assert AccessLog.query.filter_by(
        action=AccessAction.VIEWED_AUDIT_TRAIL
    ).count() == 1


def test_the_access_history_for_a_case_is_readable_in_the_app(client):
    register(client, "worker@example.org")
    case = create_case()
    client.get(f"/cases/{case.id}")

    response = client.get(f"/cases/{case.id}/access-log")

    assert response.status_code == 200
    entries = response.get_json()["entries"]
    assert entries[0]["action"] == AccessAction.VIEWED_CASE
    assert entries[0]["user"] == "Alex"


def test_access_logging_never_blocks_a_worker_reading_a_case(client, monkeypatch):
    """A dropped log line is bad; a blocked risk assessment is worse."""
    register(client, "worker@example.org")
    case = create_case()

    def explode(*args, **kwargs):
        raise RuntimeError("logging backend is down")

    monkeypatch.setattr(AccessLogService, "record", explode)

    assert client.get(f"/cases/{case.id}").status_code == 200


def test_pruning_removes_entries_past_their_retention_period(client, app):
    register(client, "worker@example.org")
    case = create_case()
    client.get(f"/cases/{case.id}")
    AccessLog.query.update({
        AccessLog.created_at: datetime.now(UTC) - timedelta(days=400)
    })
    db.session.commit()

    pruned = AccessLogService.from_config(app.config).prune(older_than_days=365)

    assert pruned == 1
    assert AccessLog.query.count() == 0


def test_anonymous_visitors_are_not_logged_and_cannot_read_the_log(client):
    case_view = client.get("/cases/1")
    log_view = client.get("/cases/1/access-log")

    assert case_view.status_code == 302
    assert log_view.status_code == 302
    assert AccessLog.query.count() == 0
