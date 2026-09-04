"""Production configuration validation.

Blockers 1 and 2. The original configuration fell back to a development
SECRET_KEY and a development invite code that is published in the README.
Both failures are silent: the app starts, looks healthy, and is trivially
compromised. This module turns them into a refusal to boot.

The guard runs only for the production config. Development and test runs are
deliberately untouched so that `python main.py` still works with no setup.
"""

from typing import List

from config import DEV_DEMO_PASSWORD, DEV_INVITE_CODE, DEV_SECRET_KEY
from app.security.crypto import parse_keys

MIN_SECRET_KEY_LENGTH = 32


class ConfigurationError(RuntimeError):
    """Raised when production configuration is unsafe.

    Deliberately fatal. A misconfigured production app must not serve
    requests.
    """


def collect_production_config_errors(config) -> List[str]:
    """Return every reason this configuration is unsafe for production.

    All problems are collected rather than raising on the first, so an
    operator fixes their environment file in one pass instead of one restart
    per mistake.
    """
    errors: List[str] = []

    secret_key = config.get("SECRET_KEY") or ""
    if not secret_key:
        errors.append(
            "SECRET_KEY is not set. Session cookies would be unsignable. "
            "Generate one with: python -m scripts.generate_keys"
        )
    elif secret_key == DEV_SECRET_KEY:
        errors.append(
            "SECRET_KEY is still the development default. Anyone reading this "
            "repository could forge a session cookie for any user."
        )
    elif len(secret_key) < MIN_SECRET_KEY_LENGTH:
        errors.append(
            f"SECRET_KEY is shorter than {MIN_SECRET_KEY_LENGTH} characters."
        )

    if not parse_keys(config.get("FIELD_ENCRYPTION_KEYS")):
        errors.append(
            "FIELD_ENCRYPTION_KEYS is not set. National Insurance numbers, "
            "risk notes and mental health notes would be stored in plaintext. "
            "Generate a key with: python -m scripts.generate_keys"
        )

    if not config.get("SESSION_COOKIE_SECURE"):
        errors.append(
            "SESSION_COOKIE_SECURE is disabled. Session cookies would be sent "
            "over plain HTTP."
        )

    if config.get("BOOTSTRAP_INVITE_ENABLED"):
        invite_code = config.get("SIGNUP_INVITE_CODE") or ""
        if not invite_code:
            errors.append(
                "BOOTSTRAP_INVITE_ENABLED is on but SIGNUP_INVITE_CODE is empty."
            )
        elif invite_code == DEV_INVITE_CODE:
            errors.append(
                "BOOTSTRAP_INVITE_ENABLED is on with the development invite "
                f"code '{DEV_INVITE_CODE}', which is published in the README. "
                "Anyone could register and read every case."
            )

    if config.get("DEMO_ACCOUNT_ENABLED"):
        demo_password = config.get("DEMO_ACCOUNT_PASSWORD") or ""
        if not demo_password or demo_password == DEV_DEMO_PASSWORD:
            errors.append(
                "DEMO_ACCOUNT_ENABLED is on with a missing or default demo "
                "password. Set DEMO_ACCOUNT_PASSWORD or turn the demo account "
                "off."
            )

    if config.get("DEMO_CASES_ENABLED"):
        errors.append(
            "DEMO_CASES_ENABLED is on. Fictional demo cases would be seeded "
            "into the live database alongside real people."
        )

    if config.get("DEBUG"):
        errors.append(
            "DEBUG is on. The interactive debugger allows arbitrary code "
            "execution."
        )

    return errors


def validate_production_config(config) -> None:
    """Raise ConfigurationError if the production configuration is unsafe."""
    errors = collect_production_config_errors(config)
    if not errors:
        return

    formatted = "\n".join(f"  - {error}" for error in errors)
    raise ConfigurationError(
        "Refusing to start: unsafe production configuration.\n"
        f"{formatted}\n"
        "See docs/operations/deployment.md for the required environment."
    )
