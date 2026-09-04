"""Blockers 3, 7 and 8: login throttling, session timeout and MFA."""

from datetime import UTC, datetime, timedelta

import pyotp
import pytest

from app.extensions import db
from app.models.login_attempt import LoginAttempt
from app.models.user import MfaRecoveryCode, User
from app.services.login_throttle_service import LoginThrottleService
from app.services.mfa_service import MfaService
from conftest import csrf_token, enrol_mfa, login, login_admin, register


def attempt_login(client, email, password):
    token = csrf_token(client, "/login")
    return client.post(
        "/login",
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=True,
    )


# --- Blocker 3: login throttling and lockout ----------------------------


def test_repeated_failures_lock_the_account(client, app):
    register(client, "worker@example.org")
    client.get("/logout")

    limit = app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"]
    for _ in range(limit):
        response = attempt_login(client, "worker@example.org", "wrong-password")
        assert b"Incorrect email or password" in response.data

    response = attempt_login(client, "worker@example.org", "wrong-password")

    assert response.status_code == 429
    assert b"Too many failed attempts" in response.data


def test_a_locked_account_rejects_even_the_correct_password(client, app):
    register(client, "worker@example.org")
    client.get("/logout")

    for _ in range(app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"]):
        attempt_login(client, "worker@example.org", "wrong-password")

    response = attempt_login(client, "worker@example.org", "password123")

    assert response.status_code == 429
    assert b"Too many failed attempts" in response.data


def test_lockout_message_does_not_reveal_whether_the_account_exists(client, app):
    """Both a real and an unknown address must give the same throttled reply."""
    limit = app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"]
    for _ in range(limit + 1):
        real = attempt_login(client, "nobody@example.org", "wrong-password")

    assert real.status_code == 429
    assert b"Too many failed attempts" in real.data


def test_a_successful_login_clears_earlier_failures(client, app):
    register(client, "worker@example.org")
    client.get("/logout")

    for _ in range(app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"] - 1):
        attempt_login(client, "worker@example.org", "wrong-password")

    attempt_login(client, "worker@example.org", "password123")
    client.get("/logout")

    # Without the reset, this run of failures would trip the lock immediately.
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"] - 1):
        response = attempt_login(client, "worker@example.org", "wrong-password")

    assert response.status_code == 200


def test_failures_outside_the_window_do_not_count(app):
    throttle = LoginThrottleService(
        max_attempts_per_account=3, window_minutes=15, lockout_minutes=15
    )

    stale = datetime.now(UTC) - timedelta(minutes=30)
    for _ in range(5):
        db.session.add(
            LoginAttempt(email="old@example.org", successful=False, created_at=stale)
        )
    db.session.commit()

    assert throttle.check("old@example.org", "127.0.0.1").allowed


def test_ip_throttle_protects_the_whole_staff_list(app):
    """One address spraying many accounts is stopped by the per-IP limit."""
    throttle = LoginThrottleService(
        max_attempts_per_account=5, max_attempts_per_ip=6, window_minutes=15
    )

    for index in range(6):
        throttle.record_failure(f"person{index}@example.org", "203.0.113.9")

    decision = throttle.check("someone-else@example.org", "203.0.113.9")

    assert not decision.allowed
    assert decision.reason == "ip_throttled"


def test_throttling_is_case_insensitive_on_email(app):
    throttle = LoginThrottleService(max_attempts_per_account=2)

    throttle.record_failure("Worker@Example.org", "127.0.0.1")
    throttle.record_failure("worker@example.org", "127.0.0.1")

    assert not throttle.check("WORKER@EXAMPLE.ORG", "127.0.0.1").allowed


def test_an_admin_can_unlock_an_account(client, app):
    register(client, "worker@example.org")
    client.get("/logout")
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"]):
        attempt_login(client, "worker@example.org", "wrong-password")

    login_admin(client)
    user = User.query.filter_by(email="worker@example.org").one()
    token = csrf_token(client, "/users")
    response = client.post(
        f"/users/{user.id}/unlock",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    client.get("/logout")
    assert attempt_login(client, "worker@example.org", "password123").status_code == 200


def test_pruning_removes_attempts_past_their_retention_period(app):
    throttle = LoginThrottleService()
    old = datetime.now(UTC) - timedelta(days=60)
    db.session.add(LoginAttempt(email="a@example.org", successful=False, created_at=old))
    db.session.add(LoginAttempt(email="b@example.org", successful=False))
    db.session.commit()

    assert throttle.prune(older_than_days=30) == 1
    assert LoginAttempt.query.count() == 1


# --- Blocker 7: session timeout -----------------------------------------


def test_sessions_are_permanent_so_the_idle_timeout_applies(client, app):
    register(client, "worker@example.org")

    with client.session_transaction() as session:
        assert session.permanent is True


def test_the_idle_timeout_is_configured_and_short(app):
    assert app.config["PERMANENT_SESSION_LIFETIME"] <= timedelta(hours=1)
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is True


# --- Blocker 8: multi-factor authentication -----------------------------


def test_an_admin_is_forced_to_enrol_before_using_the_app(client):
    login(client, "demo@quickcapture.local", "demo-password-123")

    response = client.get("/dashboard")

    assert response.status_code == 302
    assert "/mfa/setup" in response.headers["Location"]


def test_a_worker_is_not_forced_to_enrol(client):
    register(client, "worker@example.org")

    assert client.get("/dashboard").status_code == 200


def test_enrolment_requires_a_valid_code_before_mfa_turns_on(client):
    login(client, "demo@quickcapture.local", "demo-password-123")
    token = csrf_token(client, "/mfa/setup")

    client.post(
        "/mfa/setup",
        data={"csrf_token": token, "code": "000000"},
        follow_redirects=True,
    )

    user = User.query.filter_by(email="demo@quickcapture.local").one()
    assert user.mfa_enabled is False


def test_successful_enrolment_turns_mfa_on_and_issues_recovery_codes(client):
    login(client, "demo@quickcapture.local", "demo-password-123")
    response = enrol_mfa(client, "demo@quickcapture.local")

    user = User.query.filter_by(email="demo@quickcapture.local").one()
    assert user.mfa_enabled is True
    assert user.mfa_confirmed_at is not None
    assert MfaRecoveryCode.query.filter_by(user_id=user.id).count() == 8
    assert b"recovery codes" in response.data.lower()


def test_login_stops_at_the_code_prompt_once_mfa_is_on(client):
    login_admin(client)
    client.get("/logout")

    login(client, "demo@quickcapture.local", "demo-password-123")

    # The password alone must not grant access.
    assert client.get("/dashboard").status_code == 302
    with client.session_transaction() as session:
        assert "_pending_mfa_user_id" in session


def test_a_valid_code_completes_login(client):
    login_admin(client)
    client.get("/logout")
    login(client, "demo@quickcapture.local", "demo-password-123")

    user = User.query.filter_by(email="demo@quickcapture.local").one()
    token = csrf_token(client, "/mfa/verify")
    response = client.post(
        "/mfa/verify",
        data={"csrf_token": token, "code": pyotp.TOTP(user.totp_secret).now()},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert client.get("/dashboard").status_code == 200


def test_an_invalid_code_does_not_complete_login(client):
    login_admin(client)
    client.get("/logout")
    login(client, "demo@quickcapture.local", "demo-password-123")

    token = csrf_token(client, "/mfa/verify")
    client.post(
        "/mfa/verify",
        data={"csrf_token": token, "code": "111111"},
        follow_redirects=True,
    )

    assert client.get("/dashboard").status_code == 302


def test_a_recovery_code_works_once_and_only_once(client, app):
    login(client, "demo@quickcapture.local", "demo-password-123")
    token = csrf_token(client, "/mfa/setup")
    user = User.query.filter_by(email="demo@quickcapture.local").one()
    client.post(
        "/mfa/setup",
        data={"csrf_token": token, "code": pyotp.TOTP(user.totp_secret).now()},
        follow_redirects=True,
    )

    service = MfaService()
    codes = service.regenerate_recovery_codes(user)
    code = codes[0]

    assert service.verify(user, code) == (True, None)
    used_again, error = service.verify(user, code)
    assert used_again is False
    assert error is not None


def test_mfa_code_failures_count_towards_the_lockout(client, app):
    """A stolen password must not buy unlimited guesses at the second factor."""
    login_admin(client)
    client.get("/logout")
    login(client, "demo@quickcapture.local", "demo-password-123")

    for _ in range(app.config["LOGIN_MAX_ATTEMPTS_PER_ACCOUNT"]):
        token = csrf_token(client, "/mfa/verify")
        client.post("/mfa/verify", data={"csrf_token": token, "code": "111111"})

    token = csrf_token(client, "/mfa/verify")
    response = client.post("/mfa/verify", data={"csrf_token": token, "code": "111111"})

    assert response.status_code == 429


def test_the_totp_secret_is_encrypted_in_the_database(client, app):
    """The secret is a credential; reading the raw row must not reveal it."""
    login_admin(client)
    user = User.query.filter_by(email="demo@quickcapture.local").one()
    plaintext_secret = user.totp_secret

    raw = db.session.execute(
        db.text("SELECT totp_secret FROM users WHERE id = :id"), {"id": user.id}
    ).scalar()

    assert plaintext_secret
    assert raw != plaintext_secret
    assert raw.startswith("enc:v1:")


def test_disabling_mfa_destroys_the_secret_and_recovery_codes(client):
    login_admin(client)
    user = User.query.filter_by(email="demo@quickcapture.local").one()

    MfaService().disable(user)

    assert user.totp_secret is None
    assert user.mfa_enabled is False
    assert MfaRecoveryCode.query.filter_by(user_id=user.id).count() == 0
