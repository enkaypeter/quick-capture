"""The shared demo account: any-code MFA and resetting its data."""

import os

import pytest

from app.models.case import Case
from app.models.erasure_log import ErasureLog
from app.models.user import User
from app.services import demo_service
from app.services.demo_service import reset_demo_data
from app.services.mfa_service import MfaService
from app.services.seed_service import DEMO_CASE_DEFINITIONS, seed_demo_account

from conftest import csrf_token, login, register
from test_config_guard import safe_production_config
from app.security.config_guard import collect_production_config_errors
from test_viable_mvp import create_case

DEMO_EMAIL = "demo@quickcapture.local"
DEMO_PASSWORD = "demo-password-123"


@pytest.fixture()
def shared_demo(app):
    app.config["DEMO_ACCOUNT_SHARED_MFA"] = True
    return seed_demo_account()


def submit_code(client, code):
    token = csrf_token(client, "/mfa/verify")
    return client.post(
        "/mfa/verify", data={"csrf_token": token, "code": code}, follow_redirects=True
    )


# --- Any-code MFA -------------------------------------------------------


def test_shared_demo_account_is_seeded_already_enrolled(shared_demo):
    assert shared_demo.mfa_enabled is True
    assert shared_demo.totp_secret


def test_shared_demo_account_is_not_sent_to_enrolment(client, shared_demo):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)

    response = client.get("/mfa/verify")

    assert b"any 6-digit code will work" in response.data
    assert "/mfa/setup" not in client.get("/dashboard").headers.get("Location", "")


def test_shared_demo_account_accepts_any_six_digits(client, shared_demo):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)

    submit_code(client, "123456")

    assert client.get("/dashboard").status_code == 200


def test_shared_demo_account_still_needs_six_digits(client, shared_demo):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)

    submit_code(client, "12345")
    submit_code(client, "abcdef")

    assert client.get("/dashboard").status_code == 302


def test_any_code_is_only_for_the_demo_account(client, app, shared_demo):
    register(client, "admin@example.org")
    user = User.query.filter_by(email="admin@example.org").one()
    MfaService().begin_enrolment(user, "Quick Capture")
    user.mfa_enabled = True

    assert MfaService().verify(user, "123456")[0] is False
    assert demo_service.is_shared_demo_account(user, app.config) is False


def test_without_shared_mfa_the_demo_account_uses_real_totp(client, app):
    # TestingConfig has DEMO_ACCOUNT_SHARED_MFA off.
    user = User.query.filter_by(email=DEMO_EMAIL).one()

    assert user.mfa_enabled is False
    assert demo_service.is_shared_demo_account(user, app.config) is False


def test_production_refuses_shared_mfa_without_opt_in():
    errors = collect_production_config_errors(
        safe_production_config(
            DEMO_ACCOUNT_ENABLED=True,
            DEMO_ACCOUNT_PASSWORD="a-strong-demo-password",
            DEMO_ACCOUNT_SHARED_MFA=True,
        )
    )

    assert any("DEMO_ACCOUNT_SHARED_MFA" in error for error in errors)


def test_production_allows_shared_mfa_with_opt_in():
    errors = collect_production_config_errors(
        safe_production_config(
            DEMO_ACCOUNT_ENABLED=True,
            DEMO_ACCOUNT_PASSWORD="a-strong-demo-password",
            DEMO_ACCOUNT_SHARED_MFA=True,
            ALLOW_DEMO_IN_PRODUCTION=True,
        )
    )

    assert errors == []


# --- Resetting demo data ------------------------------------------------


@pytest.fixture()
def demo_with_cases(app, shared_demo):
    app.config["DEMO_CASES_ENABLED"] = True
    reset_demo_data(app.config)
    return shared_demo


def signed_in_demo(client):
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    submit_code(client, "000000")


def test_reset_removes_cases_the_demo_account_created(client, app, demo_with_cases):
    signed_in_demo(client)
    create_case(client, full_name="Someone Typed In A Demo")
    assert Case.query.filter_by(full_name="Someone Typed In A Demo").count() == 1

    reset_demo_data(app.config)

    assert Case.query.filter_by(full_name="Someone Typed In A Demo").count() == 0
    assert Case.query.count() == len(DEMO_CASE_DEFINITIONS)


def test_reset_undoes_edits_to_seeded_cases(app, demo_with_cases):
    case = Case.query.filter_by(identifier="DEMO-OUTREACH-001").one()
    case.full_name = "Edited During Demo"
    from app.extensions import db

    db.session.commit()

    reset_demo_data(app.config)

    case = Case.query.filter_by(identifier="DEMO-OUTREACH-001").one()
    assert case.full_name == "Demo Alex Reed"


def test_reset_leaves_other_users_cases_alone(client, app, demo_with_cases):
    register(client, "worker@example.org")
    create_case(client, full_name="A Real Person")

    reset_demo_data(app.config)

    assert Case.query.filter_by(full_name="A Real Person").count() == 1


def test_reset_does_not_write_erasure_log_rows(app, demo_with_cases):
    reset_demo_data(app.config)

    assert ErasureLog.query.count() == 0


def test_automatic_reset_runs_when_the_interval_has_elapsed(app, tmp_path, demo_with_cases):
    app.config["DEMO_RESET_INTERVAL_MINUTES"] = 60
    app.config["DB_DIR"] = str(tmp_path)
    demo_service.init_demo_reset(app)
    client = app.test_client()

    signed_in_demo(client)  # first request resets and writes the marker
    marker = tmp_path / demo_service.RESET_MARKER_FILENAME
    assert marker.exists()

    create_case(client, full_name="Made After Reset")
    assert Case.query.filter_by(full_name="Made After Reset").count() == 1

    # Not due yet: the record survives.
    client.get("/dashboard")
    assert Case.query.filter_by(full_name="Made After Reset").count() == 1

    # Backdate the marker past the interval: the next request resets.
    old = marker.stat().st_mtime - 61 * 60
    os.utime(marker, (old, old))
    client.get("/dashboard")

    assert Case.query.filter_by(full_name="Made After Reset").count() == 0
