"""Blockers 1 and 2: production must refuse to start on unsafe configuration."""

import pytest

from config import DEV_DEMO_PASSWORD, DEV_INVITE_CODE, DEV_SECRET_KEY
from app.security.config_guard import (
    ConfigurationError,
    collect_production_config_errors,
    validate_production_config,
)


def safe_production_config(**overrides):
    """A configuration that should pass every check, before overrides."""
    config = {
        "SECRET_KEY": "b" * 64,
        "FIELD_ENCRYPTION_KEYS": "kkPU7yhBGhcs3iZzGKmYWDEuOfMSZbn0uhoBOsZTOgU=",
        "SESSION_COOKIE_SECURE": True,
        "BOOTSTRAP_INVITE_ENABLED": False,
        "SIGNUP_INVITE_CODE": "",
        "DEMO_ACCOUNT_ENABLED": False,
        "DEMO_ACCOUNT_PASSWORD": "",
        "DEMO_CASES_ENABLED": False,
        "DEBUG": False,
    }
    config.update(overrides)
    return config


def test_safe_configuration_passes():
    assert collect_production_config_errors(safe_production_config()) == []
    validate_production_config(safe_production_config())


def test_missing_secret_key_is_rejected():
    errors = collect_production_config_errors(safe_production_config(SECRET_KEY=""))

    assert any("SECRET_KEY is not set" in error for error in errors)


def test_development_secret_key_is_rejected():
    errors = collect_production_config_errors(
        safe_production_config(SECRET_KEY=DEV_SECRET_KEY)
    )

    assert any("development default" in error for error in errors)


def test_short_secret_key_is_rejected():
    errors = collect_production_config_errors(safe_production_config(SECRET_KEY="short"))

    assert any("shorter than" in error for error in errors)


def test_missing_encryption_keys_are_rejected():
    errors = collect_production_config_errors(
        safe_production_config(FIELD_ENCRYPTION_KEYS="")
    )

    assert any("FIELD_ENCRYPTION_KEYS" in error for error in errors)


def test_insecure_session_cookie_is_rejected():
    errors = collect_production_config_errors(
        safe_production_config(SESSION_COOKIE_SECURE=False)
    )

    assert any("SESSION_COOKIE_SECURE" in error for error in errors)


def test_published_dev_invite_code_is_rejected_when_bootstrap_is_on():
    """The README publishes this code, so it must never be live."""
    errors = collect_production_config_errors(
        safe_production_config(
            BOOTSTRAP_INVITE_ENABLED=True,
            SIGNUP_INVITE_CODE=DEV_INVITE_CODE,
        )
    )

    assert any("published in the README" in error for error in errors)


def test_empty_invite_code_is_rejected_when_bootstrap_is_on():
    errors = collect_production_config_errors(
        safe_production_config(BOOTSTRAP_INVITE_ENABLED=True, SIGNUP_INVITE_CODE="")
    )

    assert any("SIGNUP_INVITE_CODE is empty" in error for error in errors)


def test_a_custom_bootstrap_invite_code_is_allowed():
    errors = collect_production_config_errors(
        safe_production_config(
            BOOTSTRAP_INVITE_ENABLED=True,
            SIGNUP_INVITE_CODE="a-genuinely-private-code",
        )
    )

    assert errors == []


def test_default_demo_password_is_rejected():
    errors = collect_production_config_errors(
        safe_production_config(
            DEMO_ACCOUNT_ENABLED=True,
            DEMO_ACCOUNT_PASSWORD=DEV_DEMO_PASSWORD,
        )
    )

    assert any("demo" in error.lower() for error in errors)


def test_demo_cases_are_rejected_in_production():
    errors = collect_production_config_errors(
        safe_production_config(DEMO_CASES_ENABLED=True)
    )

    assert any("DEMO_CASES_ENABLED" in error for error in errors)


def test_demo_cases_are_allowed_when_explicitly_opted_in():
    """A demo/PoC deployment can opt in with ALLOW_DEMO_IN_PRODUCTION."""
    errors = collect_production_config_errors(
        safe_production_config(
            DEMO_CASES_ENABLED=True,
            ALLOW_DEMO_IN_PRODUCTION=True,
        )
    )

    assert errors == []


def test_demo_account_still_needs_a_strong_password_when_opted_in():
    """The opt-in permits demo data, but not a guessable admin password."""
    errors = collect_production_config_errors(
        safe_production_config(
            DEMO_CASES_ENABLED=True,
            ALLOW_DEMO_IN_PRODUCTION=True,
            DEMO_ACCOUNT_ENABLED=True,
            DEMO_ACCOUNT_PASSWORD=DEV_DEMO_PASSWORD,
        )
    )

    assert any("demo" in error.lower() for error in errors)


def test_debug_mode_is_rejected():
    errors = collect_production_config_errors(safe_production_config(DEBUG=True))

    assert any("DEBUG" in error for error in errors)


def test_every_problem_is_reported_at_once():
    """One restart per mistake is how misconfigurations survive to production."""
    errors = collect_production_config_errors(
        safe_production_config(
            SECRET_KEY="",
            FIELD_ENCRYPTION_KEYS="",
            SESSION_COOKIE_SECURE=False,
        )
    )

    assert len(errors) == 3


def test_validate_raises_with_all_reasons_listed():
    with pytest.raises(ConfigurationError) as excinfo:
        validate_production_config(
            safe_production_config(SECRET_KEY="", FIELD_ENCRYPTION_KEYS="")
        )

    message = str(excinfo.value)
    assert "Refusing to start" in message
    assert "SECRET_KEY" in message
    assert "FIELD_ENCRYPTION_KEYS" in message


def test_production_app_refuses_to_start_without_secrets(monkeypatch):
    """The guard is wired into the application factory, not just importable."""
    from app import create_app

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("FIELD_ENCRYPTION_KEYS", raising=False)

    with pytest.raises(ConfigurationError):
        create_app("production")


def test_development_app_still_starts_with_no_configuration():
    """Local development must stay zero-setup."""
    from app import create_app

    assert create_app("development") is not None
