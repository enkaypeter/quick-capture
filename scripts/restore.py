"""Restore a backup produced by scripts.backup.

    python -m scripts.restore --archive /var/backups/quick-capture/....enc \
        --target /srv/quick-capture

Restores into a target directory as `database.db` and `uploads/`. The target
must not already contain those, so a restore cannot silently overwrite a live
system - move the current data aside first, deliberately.

An untested backup is not a backup. docs/operations/backups.md describes the
quarterly restore drill this script exists for.
"""

import argparse
import os
import sys
import tarfile
import tempfile
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from scripts.backup import ENCRYPTED_SUFFIX


def restore_backup(
    archive_path: str,
    target_dir: str,
    encryption_key: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """Unpack a backup archive into `target_dir`. Returns the target path."""
    if not os.path.isfile(archive_path):
        raise FileNotFoundError(f"No such archive: {archive_path}")

    os.makedirs(target_dir, exist_ok=True)

    if not overwrite:
        for name in ("database.db", "uploads"):
            if os.path.exists(os.path.join(target_dir, name)):
                raise FileExistsError(
                    f"{name} already exists in {target_dir}. Move the current "
                    "data aside before restoring, or pass overwrite=True."
                )

    with tempfile.TemporaryDirectory() as staging:
        if archive_path.endswith(ENCRYPTED_SUFFIX):
            if not encryption_key:
                raise ValueError(
                    "This archive is encrypted but no BACKUP_ENCRYPTION_KEY was "
                    "supplied."
                )
            with open(archive_path, "rb") as handle:
                try:
                    plaintext = Fernet(encryption_key.encode()).decrypt(handle.read())
                except InvalidToken as exc:
                    raise ValueError(
                        "BACKUP_ENCRYPTION_KEY does not decrypt this archive."
                    ) from exc

            tar_path = os.path.join(staging, "backup.tar.gz")
            with open(tar_path, "wb") as handle:
                handle.write(plaintext)
        else:
            tar_path = archive_path

        with tarfile.open(tar_path, "r:gz") as archive:
            # filter="data" refuses absolute paths and traversal entries. A
            # backup archive should never contain either, and a tampered one
            # must not be able to write outside the target.
            archive.extractall(target_dir, filter="data")

    return target_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="Backup archive to restore.")
    parser.add_argument(
        "--target", required=True, help="Directory to restore into."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing data in the target directory.",
    )
    args = parser.parse_args(argv)

    try:
        restore_backup(
            archive_path=args.archive,
            target_dir=args.target,
            encryption_key=os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip() or None,
            overwrite=args.overwrite,
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Restored {args.archive} into {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
