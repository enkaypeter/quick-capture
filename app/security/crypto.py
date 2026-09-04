"""Field-level encryption for special-category case data.

Blocker 5. Volume encryption protects data when a disk is stolen; it does
nothing once the host is running. National Insurance numbers and mental
health notes are the fields an auditor will ask about specifically, so they
are encrypted in the database as well.

Keys are Fernet keys supplied through the `FIELD_ENCRYPTION_KEYS` config
value as a comma-separated list. The first key encrypts; every key is tried
when decrypting. That ordering is what makes rotation possible: prepend a new
key, re-save the rows, then drop the old key.

If no key is configured the columns store plaintext. That is deliberate — it
keeps local development frictionless — and `config_guard` refuses to start a
production app without keys.
"""

import logging
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from flask import current_app
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

# Marks a value as ciphertext produced by this module. Without it we cannot
# tell an encrypted column apart from a row written before encryption was
# switched on, and migrating an existing database would be guesswork.
CIPHER_PREFIX = "enc:v1:"


def generate_key() -> str:
    """Generate a new Fernet key suitable for FIELD_ENCRYPTION_KEYS."""
    return Fernet.generate_key().decode()


def parse_keys(raw: Optional[str]) -> List[str]:
    """Split a comma-separated key list, ignoring blanks and whitespace."""
    if not raw:
        return []
    return [key.strip() for key in raw.split(",") if key.strip()]


def _cipher() -> Optional[MultiFernet]:
    """Build a MultiFernet from the configured keys, or None if unconfigured."""
    try:
        raw = current_app.config.get("FIELD_ENCRYPTION_KEYS", "")
    except RuntimeError:
        # No application context (e.g. a bare model import). Treat as
        # unconfigured rather than exploding.
        return None

    keys = parse_keys(raw)
    if not keys:
        return None

    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (ValueError, TypeError) as exc:
        raise ConfigurationKeyError(
            "FIELD_ENCRYPTION_KEYS contains a value that is not a valid Fernet "
            "key. Generate one with: python -m scripts.generate_keys"
        ) from exc


class ConfigurationKeyError(RuntimeError):
    """Raised when the configured encryption keys cannot be used."""


def encrypt_value(value: Optional[str]) -> Optional[str]:
    """Encrypt a string for storage. Returns plaintext if no keys are set."""
    if value is None or value == "":
        return value
    if value.startswith(CIPHER_PREFIX):
        return value  # already encrypted; do not double-wrap

    cipher = _cipher()
    if cipher is None:
        return value

    return CIPHER_PREFIX + cipher.encrypt(value.encode()).decode()


def decrypt_value(value: Optional[str]) -> Optional[str]:
    """Decrypt a stored string.

    Values without the cipher prefix are returned unchanged, which is what
    lets a database written before this change keep working while the
    migration re-encrypts it.
    """
    if value is None or value == "":
        return value
    if not value.startswith(CIPHER_PREFIX):
        return value

    cipher = _cipher()
    if cipher is None:
        logger.error(
            "Encrypted value found but FIELD_ENCRYPTION_KEYS is not set. "
            "The correct key is required to read this record."
        )
        return None

    try:
        return cipher.decrypt(value[len(CIPHER_PREFIX):].encode()).decode()
    except InvalidToken:
        logger.error(
            "Could not decrypt a stored value with any configured key. If a "
            "key was rotated out too early, restore it to FIELD_ENCRYPTION_KEYS."
        )
        return None


class EncryptedText(TypeDecorator):
    """A Text column that is encrypted at rest and decrypted on read.

    Encrypted columns cannot be searched or sorted in SQL. Only apply this to
    fields that no query filters on — see docs/operations/encryption.md.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        return decrypt_value(value)
