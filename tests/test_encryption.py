"""Blocker 5: special-category fields are encrypted at rest."""

import pytest
from cryptography.fernet import Fernet

from app.extensions import db
from app.models.case import Case
from app.security.crypto import (
    CIPHER_PREFIX,
    EncryptedText,
    decrypt_value,
    encrypt_value,
    generate_key,
    parse_keys,
)
from conftest import register

ENCRYPTED_COLUMNS = ("ni_number", "risk_notes", "mental_health_notes")


def create_case(**fields):
    case = Case(identifier=fields.pop("identifier", "SOTS-TEST"), user_id=1, **fields)
    db.session.add(case)
    db.session.commit()
    return case


def raw_column(case_id, column):
    """Read a column with SQL, bypassing the decrypting type decorator."""
    return db.session.execute(
        db.text(f"SELECT {column} FROM cases WHERE id = :id"), {"id": case_id}
    ).scalar()


def test_sensitive_columns_are_ciphertext_in_the_database(client, app):
    register(client, "worker@example.org")
    case = create_case(
        ni_number="QQ123456C",
        risk_notes="History of violence towards staff.",
        mental_health_notes="Diagnosed with schizophrenia.",
    )

    for column in ENCRYPTED_COLUMNS:
        stored = raw_column(case.id, column)
        assert stored.startswith(CIPHER_PREFIX), column


def test_the_plaintext_never_appears_in_the_stored_value(client, app):
    register(client, "worker@example.org")
    case = create_case(ni_number="QQ123456C")

    assert "QQ123456C" not in raw_column(case.id, "ni_number")


def test_values_round_trip_through_the_orm(client, app):
    register(client, "worker@example.org")
    case = create_case(
        ni_number="QQ123456C",
        risk_notes="Approach with a colleague.",
        mental_health_notes="Under the care of the crisis team.",
    )
    db.session.expire_all()

    reloaded = db.session.get(Case, case.id)
    assert reloaded.ni_number == "QQ123456C"
    assert reloaded.risk_notes == "Approach with a colleague."
    assert reloaded.mental_health_notes == "Under the care of the crisis team."


def test_empty_and_missing_values_are_left_alone(client, app):
    register(client, "worker@example.org")
    case = create_case(ni_number=None, risk_notes="")

    assert raw_column(case.id, "ni_number") is None
    assert raw_column(case.id, "risk_notes") == ""


def test_encrypting_an_already_encrypted_value_is_a_no_op(app):
    once = encrypt_value("QQ123456C")
    twice = encrypt_value(once)

    assert twice == once
    assert decrypt_value(twice) == "QQ123456C"


def test_plaintext_written_before_encryption_is_still_readable(app):
    """An existing database must keep working while the migration runs."""
    assert decrypt_value("legacy plaintext value") == "legacy plaintext value"


def test_a_rotated_in_key_still_decrypts_old_values(app):
    """Rotation works by prepending a key, not by replacing it."""
    original_key = app.config["FIELD_ENCRYPTION_KEYS"]
    ciphertext = encrypt_value("QQ123456C")

    new_key = generate_key()
    app.config["FIELD_ENCRYPTION_KEYS"] = f"{new_key},{original_key}"

    assert decrypt_value(ciphertext) == "QQ123456C"
    # New writes use the new key, and are still readable.
    assert decrypt_value(encrypt_value("AB987654Z")) == "AB987654Z"


def test_dropping_a_key_too_early_makes_values_unreadable(app):
    """The failure mode is loud in the log and null in the app, not a crash."""
    ciphertext = encrypt_value("QQ123456C")
    app.config["FIELD_ENCRYPTION_KEYS"] = generate_key()

    assert decrypt_value(ciphertext) is None


def test_no_configured_key_means_plaintext_storage(app):
    """Local development stays zero-setup; config_guard blocks this in production."""
    app.config["FIELD_ENCRYPTION_KEYS"] = ""

    assert encrypt_value("QQ123456C") == "QQ123456C"


def test_an_invalid_key_is_reported_rather_than_silently_ignored(app):
    from app.security.crypto import ConfigurationKeyError

    app.config["FIELD_ENCRYPTION_KEYS"] = "not-a-fernet-key"

    with pytest.raises(ConfigurationKeyError):
        encrypt_value("QQ123456C")


def test_parse_keys_ignores_blanks_and_whitespace():
    assert parse_keys(" a , ,b ") == ["a", "b"]
    assert parse_keys("") == []
    assert parse_keys(None) == []


def test_generated_keys_are_usable_fernet_keys():
    key = generate_key()

    assert Fernet(key.encode()).decrypt(Fernet(key.encode()).encrypt(b"x")) == b"x"


def test_the_migration_encrypts_rows_written_before_the_change(client, app):
    """Existing production data must end up encrypted, not just new rows."""
    from app.migrations import _encrypt_sensitive_case_fields

    register(client, "worker@example.org")
    case = create_case()
    # Simulate a row written by the previous version of the app.
    db.session.execute(
        db.text(
            "UPDATE cases SET ni_number = :ni, risk_notes = :risk, "
            "mental_health_notes = :mh WHERE id = :id"
        ),
        {
            "ni": "QQ123456C",
            "risk": "Legacy risk note.",
            "mh": "Legacy mental health note.",
            "id": case.id,
        },
    )
    db.session.commit()

    _encrypt_sensitive_case_fields()

    for column in ENCRYPTED_COLUMNS:
        assert raw_column(case.id, column).startswith(CIPHER_PREFIX), column

    db.session.expire_all()
    assert db.session.get(Case, case.id).ni_number == "QQ123456C"


def test_the_migration_is_safe_to_run_twice(client, app):
    from app.migrations import _encrypt_sensitive_case_fields

    register(client, "worker@example.org")
    case = create_case(ni_number="QQ123456C")

    _encrypt_sensitive_case_fields()
    first = raw_column(case.id, "ni_number")
    _encrypt_sensitive_case_fields()

    assert raw_column(case.id, "ni_number") == first
    db.session.expire_all()
    assert db.session.get(Case, case.id).ni_number == "QQ123456C"


def test_encrypted_type_is_applied_to_the_expected_columns():
    """A regression guard: dropping the type would silently store plaintext."""
    for column in ENCRYPTED_COLUMNS:
        assert isinstance(Case.__table__.columns[column].type, EncryptedText), column
