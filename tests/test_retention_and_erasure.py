"""Blocker 11: permanent erasure and the retention policy."""

import io
import os
from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models.access_log import AccessLog
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.case_attachment import CaseAttachment
from app.models.case_note import CaseNote
from app.models.erasure_log import ErasureLog
from app.models.user import User
from app.services.retention_service import (
    REASON_ERASURE_REQUEST,
    REASON_RETENTION_POLICY,
    RetentionService,
)
from conftest import csrf_token, login_admin, register


def create_case(identifier="SOTS-0001", **fields):
    user = User.query.first()
    case = Case(identifier=identifier, user_id=user.id, **fields)
    db.session.add(case)
    db.session.commit()
    return case


def attach_file(client, case_id, name="support-plan.txt"):
    token = csrf_token(client, f"/cases/{case_id}")
    client.post(
        f"/cases/{case_id}/attachments",
        data={
            "csrf_token": token,
            "attachment": (io.BytesIO(b"sensitive support plan"), name),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    return CaseAttachment.query.filter_by(case_id=case_id).one()


# --- Purging a single case ----------------------------------------------


def test_purging_destroys_the_case_row(client, app):
    register(client, "worker@example.org")
    case = create_case()

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST
    )

    assert Case.query.count() == 0


def test_purging_destroys_child_records(client, app):
    register(client, "worker@example.org")
    case = create_case()
    db.session.add(CaseNote(case_id=case.id, content="<p>A note.</p>"))
    db.session.add(
        AuditLog(case_id=case.id, user_id=1, action="created", field_name="case")
    )
    db.session.add(AccessLog(user_id=1, case_id=case.id, action="viewed_case"))
    db.session.commit()

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST
    )

    assert CaseNote.query.count() == 0
    assert AuditLog.query.count() == 0
    assert AccessLog.query.count() == 0


def test_audit_log_values_are_erased_too(client, app):
    """Audit rows hold old and new field values, so they are case data."""
    register(client, "worker@example.org")
    case = create_case()
    db.session.add(
        AuditLog(
            case_id=case.id,
            user_id=1,
            action="updated",
            field_name="mental_health_notes",
            old_value="Diagnosed with schizophrenia.",
            new_value="Under the crisis team.",
        )
    )
    db.session.commit()

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST
    )

    remaining = db.session.execute(db.text("SELECT old_value FROM audit_logs")).all()
    assert remaining == []


def test_purging_deletes_files_from_disk(client, app):
    register(client, "worker@example.org")
    case = create_case()
    attachment = attach_file(client, case.id)
    path = os.path.join(app.config["UPLOAD_FOLDER"], attachment.stored_path)
    assert os.path.isfile(path)

    result = RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST
    )

    assert not os.path.exists(path)
    assert result.files_deleted == 1


def test_purging_writes_an_erasure_log_entry(client, app):
    register(client, "worker@example.org")
    case = create_case(identifier="SOTS-0042")

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST, requested_by_user_id=1
    )

    entry = ErasureLog.query.one()
    assert entry.case_identifier == "SOTS-0042"
    assert entry.reason == REASON_ERASURE_REQUEST
    assert entry.requested_by_user_id == 1
    assert entry.records_deleted >= 1


def test_the_erasure_log_survives_the_case_it_describes(client, app):
    register(client, "worker@example.org")
    case = create_case(identifier="SOTS-0042")

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST
    )

    assert Case.query.count() == 0
    assert ErasureLog.query.count() == 1


def test_the_erasure_log_holds_no_personal_data(client, app):
    """It is proof of destruction, not a copy of what was destroyed."""
    register(client, "worker@example.org")
    case = create_case(
        identifier="SOTS-0042",
        full_name="Jane Doe",
        ni_number="QQ123456C",
        mental_health_notes="Diagnosed with schizophrenia.",
    )

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=REASON_ERASURE_REQUEST
    )

    columns = {column.name for column in ErasureLog.__table__.columns}
    assert columns == {
        "id",
        "case_identifier",
        "requested_by_user_id",
        "reason",
        "records_deleted",
        "files_deleted",
        "purged_at",
    }


def test_purging_one_case_leaves_others_untouched(client, app):
    register(client, "worker@example.org")
    keep = create_case(identifier="SOTS-0001")
    remove = create_case(identifier="SOTS-0002")
    db.session.add(CaseNote(case_id=keep.id, content="<p>Keep me.</p>"))
    db.session.commit()

    RetentionService(app.config["UPLOAD_FOLDER"]).purge_case(
        remove, reason=REASON_ERASURE_REQUEST
    )

    assert [case.identifier for case in Case.query.all()] == ["SOTS-0001"]
    assert CaseNote.query.count() == 1


# --- The scheduled retention job -----------------------------------------


def test_only_archived_cases_past_the_period_expire(client, app):
    register(client, "worker@example.org")
    create_case(identifier="SOTS-ACTIVE")
    create_case(
        identifier="SOTS-RECENT", archived_at=datetime.now(UTC) - timedelta(days=10)
    )
    create_case(
        identifier="SOTS-OLD", archived_at=datetime.now(UTC) - timedelta(days=400)
    )

    expired = RetentionService(app.config["UPLOAD_FOLDER"]).find_expired_cases(365)

    assert [case.identifier for case in expired] == ["SOTS-OLD"]


def test_an_active_case_is_never_expired_by_the_job(client, app):
    register(client, "worker@example.org")
    create_case(identifier="SOTS-ACTIVE")

    assert RetentionService(app.config["UPLOAD_FOLDER"]).find_expired_cases(0) == []


def test_the_retention_job_purges_expired_cases(client, app):
    register(client, "worker@example.org")
    create_case(
        identifier="SOTS-OLD", archived_at=datetime.now(UTC) - timedelta(days=400)
    )
    create_case(identifier="SOTS-ACTIVE")

    results = RetentionService(app.config["UPLOAD_FOLDER"]).purge_expired_cases(365)

    assert len(results) == 1
    assert ErasureLog.query.one().reason == REASON_RETENTION_POLICY
    assert [case.identifier for case in Case.query.all()] == ["SOTS-ACTIVE"]


def test_a_retention_period_is_configured(app):
    assert app.config["RETENTION_ARCHIVED_CASE_DAYS"] > 0
    assert app.config["RETENTION_ACCESS_LOG_DAYS"] > 0
    assert app.config["RETENTION_LOGIN_ATTEMPT_DAYS"] > 0


# --- The admin route ------------------------------------------------------


def test_a_worker_cannot_purge_a_case(client):
    register(client, "worker@example.org")
    case = create_case()
    token = csrf_token(client, f"/cases/{case.id}")

    response = client.post(
        f"/cases/{case.id}/purge",
        data={"csrf_token": token, "confirm_identifier": case.identifier},
    )

    assert response.status_code == 403
    assert Case.query.count() == 1


def test_an_admin_can_purge_a_case(client):
    login_admin(client)
    case = create_case(identifier="SOTS-0042")
    token = csrf_token(client, f"/cases/{case.id}")

    response = client.post(
        f"/cases/{case.id}/purge",
        data={"csrf_token": token, "confirm_identifier": "SOTS-0042"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert Case.query.count() == 0
    assert ErasureLog.query.one().case_identifier == "SOTS-0042"


def test_purging_requires_typing_the_case_identifier(client):
    """There is no undo, so a stray click must not destroy a record."""
    login_admin(client)
    case = create_case(identifier="SOTS-0042")
    token = csrf_token(client, f"/cases/{case.id}")

    client.post(
        f"/cases/{case.id}/purge",
        data={"csrf_token": token, "confirm_identifier": "wrong"},
        follow_redirects=True,
    )

    assert Case.query.count() == 1
    assert ErasureLog.query.count() == 0


def test_purging_requires_a_csrf_token(client):
    login_admin(client)
    case = create_case(identifier="SOTS-0042")

    response = client.post(
        f"/cases/{case.id}/purge", data={"confirm_identifier": "SOTS-0042"}
    )

    assert response.status_code == 400
    assert Case.query.count() == 1


def test_an_archived_case_can_still_be_purged(client):
    """Erasure requests usually arrive after a case has been archived."""
    login_admin(client)
    case = create_case(identifier="SOTS-0042", archived_at=datetime.now(UTC))
    token = csrf_token(client, "/dashboard")

    client.post(
        f"/cases/{case.id}/purge",
        data={"csrf_token": token, "confirm_identifier": "SOTS-0042"},
        follow_redirects=True,
    )

    assert Case.query.count() == 0


def test_only_an_admin_can_read_the_erasure_log(client):
    register(client, "worker@example.org")

    assert client.get("/erasure-log").status_code == 403


def test_an_admin_can_read_the_erasure_log(client):
    login_admin(client)

    assert client.get("/erasure-log").status_code == 200


def test_the_normal_delete_still_only_archives(client):
    """Soft delete stays the default; erasure is a separate, deliberate act."""
    register(client, "worker@example.org")
    case = create_case()
    token = csrf_token(client, f"/cases/{case.id}")

    client.post(
        f"/cases/{case.id}/delete",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert Case.query.count() == 1
    assert Case.query.one().archived_at is not None
