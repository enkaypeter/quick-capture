"""Generate the secrets a production deployment needs.

    python -m scripts.generate_keys

Prints values for SECRET_KEY, FIELD_ENCRYPTION_KEYS and BACKUP_ENCRYPTION_KEY.
Nothing is written to disk - paste them into the secret store or environment
file described in docs/operations/deployment.md.
"""

import secrets

from app.security.crypto import generate_key


def main() -> None:
    print("# Generated secrets - store these in your secret manager.")
    print("# Losing FIELD_ENCRYPTION_KEYS makes encrypted case data")
    print("# permanently unreadable. Back it up separately from the database.")
    print()
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"FIELD_ENCRYPTION_KEYS={generate_key()}")
    print(f"BACKUP_ENCRYPTION_KEY={generate_key()}")


if __name__ == "__main__":
    main()
