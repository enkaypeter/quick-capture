"""Blocker 4: encrypted backups, and a restore that has actually been run."""

import os
import sqlite3
import tarfile

import pytest
from cryptography.fernet import Fernet

from scripts.backup import (
    BACKUP_PREFIX,
    ENCRYPTED_SUFFIX,
    create_backup,
    prune_backups,
    snapshot_database,
)
from scripts.restore import restore_backup

KEY = Fernet.generate_key().decode()


@pytest.fixture()
def sample_data(tmp_path):
    """A database in WAL mode with an uncheckpointed write, plus an upload."""
    database = tmp_path / "database.db"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE cases (id INTEGER PRIMARY KEY, ni_number TEXT)")
    connection.execute("INSERT INTO cases VALUES (1, 'QQ123456C')")
    connection.commit()

    uploads = tmp_path / "uploads"
    (uploads / "1").mkdir(parents=True)
    (uploads / "1" / "plan.txt").write_text("sensitive support plan")

    yield {"database": str(database), "uploads": str(uploads), "root": tmp_path}
    connection.close()


def test_a_backup_archive_is_written(sample_data, tmp_path):
    destination = tmp_path / "backups"

    path = create_backup(
        sample_data["database"], sample_data["uploads"], str(destination), KEY
    )

    assert os.path.isfile(path)
    assert os.path.basename(path).startswith(BACKUP_PREFIX)


def test_the_archive_is_encrypted(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )

    contents = open(path, "rb").read()
    assert path.endswith(ENCRYPTED_SUFFIX)
    assert b"QQ123456C" not in contents
    assert b"sensitive support plan" not in contents
    with pytest.raises(tarfile.ReadError):
        tarfile.open(path, "r:gz")


def test_the_backup_file_is_not_world_readable(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )

    assert oct(os.stat(path).st_mode)[-3:] == "600"


def test_a_live_wal_database_is_captured_consistently(sample_data, tmp_path):
    """A plain file copy of a WAL database can miss committed rows."""
    connection = sqlite3.connect(sample_data["database"])
    connection.execute("INSERT INTO cases VALUES (2, 'AB987654Z')")
    connection.commit()

    snapshot = tmp_path / "snapshot.db"
    snapshot_database(sample_data["database"], str(snapshot))
    connection.close()

    rows = sqlite3.connect(snapshot).execute("SELECT COUNT(*) FROM cases").fetchone()
    assert rows[0] == 2


def test_a_backup_restores_to_the_same_data(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )
    target = tmp_path / "restored"

    restore_backup(path, str(target), encryption_key=KEY)

    restored_db = target / "database.db"
    rows = sqlite3.connect(restored_db).execute("SELECT ni_number FROM cases").fetchall()
    assert rows == [("QQ123456C",)]
    assert (target / "uploads" / "1" / "plan.txt").read_text() == (
        "sensitive support plan"
    )


def test_restoring_without_the_key_fails(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )

    with pytest.raises(ValueError, match="encrypted"):
        restore_backup(path, str(tmp_path / "restored"))


def test_restoring_with_the_wrong_key_fails(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )

    with pytest.raises(ValueError, match="does not decrypt"):
        restore_backup(
            path, str(tmp_path / "restored"), encryption_key=Fernet.generate_key().decode()
        )


def test_a_restore_refuses_to_overwrite_live_data(sample_data, tmp_path):
    """A mistimed restore must not silently destroy the running system."""
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )
    target = tmp_path / "live"
    target.mkdir()
    (target / "database.db").write_text("the live database")

    with pytest.raises(FileExistsError):
        restore_backup(path, str(target), encryption_key=KEY)

    assert (target / "database.db").read_text() == "the live database"


def test_an_overwrite_can_be_asked_for_explicitly(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"],
        sample_data["uploads"],
        str(tmp_path / "backups"),
        KEY,
    )
    target = tmp_path / "live"
    target.mkdir()
    (target / "database.db").write_text("the live database")

    restore_backup(path, str(target), encryption_key=KEY, overwrite=True)

    rows = sqlite3.connect(target / "database.db").execute(
        "SELECT ni_number FROM cases"
    ).fetchall()
    assert rows == [("QQ123456C",)]


def test_the_cli_refuses_to_write_an_unencrypted_backup(sample_data, tmp_path, monkeypatch, capsys):
    from scripts.backup import main

    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)

    exit_code = main([
        "--database", sample_data["database"],
        "--uploads", sample_data["uploads"],
        "--destination", str(tmp_path / "backups"),
    ])

    assert exit_code == 1
    assert "BACKUP_ENCRYPTION_KEY" in capsys.readouterr().err
    assert not os.path.isdir(tmp_path / "backups")


def test_pruning_keeps_only_the_newest_backups(sample_data, tmp_path):
    from datetime import UTC, datetime, timedelta

    destination = tmp_path / "backups"
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for day in range(5):
        create_backup(
            sample_data["database"],
            sample_data["uploads"],
            str(destination),
            KEY,
            timestamp=base + timedelta(days=day),
        )

    removed = prune_backups(str(destination), keep=2)

    assert len(removed) == 3
    assert len(os.listdir(destination)) == 2


def test_pruning_keeps_everything_when_keep_is_zero(sample_data, tmp_path):
    destination = tmp_path / "backups"
    create_backup(
        sample_data["database"], sample_data["uploads"], str(destination), KEY
    )

    assert prune_backups(str(destination), keep=0) == []
    assert len(os.listdir(destination)) == 1


def test_a_backup_works_when_there_are_no_uploads_yet(sample_data, tmp_path):
    path = create_backup(
        sample_data["database"], None, str(tmp_path / "backups"), KEY
    )
    target = tmp_path / "restored"

    restore_backup(path, str(target), encryption_key=KEY)

    assert (target / "database.db").is_file()
