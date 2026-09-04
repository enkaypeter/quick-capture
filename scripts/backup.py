"""Encrypted backup of the database and uploaded files.

    python -m scripts.backup --destination /var/backups/quick-capture

Blocker 4. There was no backup at all: the database and every voice note lived
in one directory, one accident away from total loss.

Three things matter here and none are optional:

* The database is copied with SQLite's online backup API, not `cp`. The app
  runs in WAL mode, so a file copy of a live database can be inconsistent.
* The archive is encrypted before it is written, so a backup can be shipped
  off-site without the off-site location becoming a place special-category
  data sits in the clear.
* A restore is only a backup if it has been tested. See
  docs/operations/backups.md.
"""

import argparse
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from typing import List, Optional

from cryptography.fernet import Fernet

BACKUP_PREFIX = "quick-capture-"
ENCRYPTED_SUFFIX = ".tar.gz.enc"
PLAIN_SUFFIX = ".tar.gz"


def snapshot_database(source_path: str, target_path: str) -> None:
    """Copy a live SQLite database consistently using the online backup API."""
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(target_path)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def create_backup(
    database_path: str,
    uploads_dir: Optional[str],
    destination_dir: str,
    encryption_key: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> str:
    """Write one backup archive and return its path."""
    timestamp = timestamp or datetime.now(UTC)
    stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(destination_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as staging:
        archive_path = os.path.join(staging, "backup.tar.gz")

        with tarfile.open(archive_path, "w:gz") as archive:
            if os.path.exists(database_path):
                db_copy = os.path.join(staging, "database.db")
                snapshot_database(database_path, db_copy)
                archive.add(db_copy, arcname="database.db")

            if uploads_dir and os.path.isdir(uploads_dir):
                archive.add(uploads_dir, arcname="uploads")

        if encryption_key:
            output_path = os.path.join(
                destination_dir, f"{BACKUP_PREFIX}{stamp}{ENCRYPTED_SUFFIX}"
            )
            with open(archive_path, "rb") as handle:
                ciphertext = Fernet(encryption_key.encode()).encrypt(handle.read())
            with open(output_path, "wb") as handle:
                handle.write(ciphertext)
        else:
            output_path = os.path.join(
                destination_dir, f"{BACKUP_PREFIX}{stamp}{PLAIN_SUFFIX}"
            )
            shutil.copy2(archive_path, output_path)

    # Backups contain every case record. Nobody but the backup user should be
    # able to read one.
    os.chmod(output_path, 0o600)
    return output_path


def prune_backups(destination_dir: str, keep: int) -> List[str]:
    """Delete all but the newest `keep` backups. Returns what was removed."""
    if keep <= 0 or not os.path.isdir(destination_dir):
        return []

    backups = sorted(
        name
        for name in os.listdir(destination_dir)
        if name.startswith(BACKUP_PREFIX)
        and (name.endswith(ENCRYPTED_SUFFIX) or name.endswith(PLAIN_SUFFIX))
    )

    removed = []
    for name in backups[:-keep] if len(backups) > keep else []:
        path = os.path.join(destination_dir, name)
        os.remove(path)
        removed.append(path)
    return removed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.environ.get(
            "BACKUP_DATABASE_PATH",
            os.path.join(os.getcwd(), "instance", "database.db"),
        ),
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--uploads",
        default=os.environ.get(
            "BACKUP_UPLOADS_DIR", os.path.join(os.getcwd(), "uploads")
        ),
        help="Directory holding case attachments and voice notes.",
    )
    parser.add_argument(
        "--destination",
        default=os.environ.get("BACKUP_DESTINATION"),
        required=os.environ.get("BACKUP_DESTINATION") is None,
        help="Directory to write the backup archive into.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=int(os.environ.get("BACKUP_KEEP", "14")),
        help="How many backups to retain locally.",
    )
    parser.add_argument(
        "--allow-unencrypted",
        action="store_true",
        help="Write a plaintext archive. Only for local testing.",
    )
    args = parser.parse_args(argv)

    key = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
    if not key and not args.allow_unencrypted:
        print(
            "BACKUP_ENCRYPTION_KEY is not set. Refusing to write an unencrypted "
            "backup of special-category data. Generate a key with "
            "'python -m scripts.generate_keys', or pass --allow-unencrypted for "
            "local testing only.",
            file=sys.stderr,
        )
        return 1

    path = create_backup(
        database_path=args.database,
        uploads_dir=args.uploads,
        destination_dir=args.destination,
        encryption_key=key or None,
    )
    print(f"Backup written: {path}")

    for removed in prune_backups(args.destination, args.keep):
        print(f"Pruned old backup: {removed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
