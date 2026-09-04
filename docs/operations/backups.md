# Backups and Restore

## Why this exists

Before this was added there were no backups at all. The database and every
voice note lived in one directory on one host — one accident, one failed disk
or one `docker volume rm` from losing every case record the charity holds.

## What is backed up

`scripts/backup.py` produces a single encrypted archive containing:

- `database.db` — every case, note, interaction, follow-up, audit and access log
- `uploads/` — attachments and voice recordings

Three things about how it does that matter:

**The database is snapshotted, not copied.** The app runs SQLite in WAL mode, so
a plain file copy of a live database can be internally inconsistent or miss
committed writes. The script uses SQLite's online backup API instead.

**The archive is encrypted before it is written.** A backup of this system is a
complete copy of special-category data about vulnerable people. Encrypting it
at creation is what makes it safe to ship off-site.

**The file is written mode `600`.** Only the backup user can read it.

## Running a backup

```bash
export BACKUP_ENCRYPTION_KEY='<Fernet key from python -m scripts.generate_keys>'
python -m scripts.backup --destination /var/backups/quick-capture
```

The script refuses to write an unencrypted archive unless you pass
`--allow-unencrypted`, which is for local testing only.

| Option | Default | Meaning |
|---|---|---|
| `--database` | `./instance/database.db` | Database file |
| `--uploads` | `./uploads` | Attachments and voice notes |
| `--destination` | `$BACKUP_DESTINATION` | Where to write (required) |
| `--keep` | 14 | Local archives to retain |

## Scheduling

Nightly, outside working hours. Any scheduler works — the point is that it runs
unattended and that failures are noticed.

```
15 2 * * * cd /srv/quick-capture && /srv/quick-capture/.venv/bin/python -m scripts.backup --destination /var/backups/quick-capture >> /var/log/quick-capture-backup.log 2>&1
```

Set up an alert if the job fails or if no new archive appears. A backup nobody
is watching is a backup that has already stopped working.

## Off-site copies

Local backups do not survive the failure of the host they sit on. Copy each
archive to storage that is not the application host, in the UK or EEA, with a
processor agreement in place.

The archive is already encrypted, so the off-site location never holds
plaintext case data. **Do not store `BACKUP_ENCRYPTION_KEY` in the same place
as the archives.**

## Restoring

```bash
export BACKUP_ENCRYPTION_KEY='<the key the archive was written with>'
python -m scripts.restore \
    --archive /var/backups/quick-capture/quick-capture-20260904T021500Z.tar.gz.enc \
    --target /srv/quick-capture-restored
```

The restore refuses to overwrite an existing `database.db` or `uploads/` unless
`--overwrite` is passed, so a mistimed restore cannot silently destroy the
running system. Move the live data aside deliberately.

To restore into production:

1. Stop the app.
2. Move the current `instance/` and `uploads/` aside — do not delete them until
   the restore is verified.
3. Restore into the application directory.
4. Check file ownership matches the service account.
5. Start the app and confirm you can sign in and open a case.

## The restore drill

**An untested backup is not a backup.** Running this once against the real
deployment is blocker 4 in
[go-live-checklist.md](go-live-checklist.md) — the app must not hold live data
until it has been done. Run this at least quarterly, and after
any change to hosting or storage:

1. Take a fresh backup.
2. Restore it into a scratch directory on a non-production machine.
3. Point a development app at the restored database.
4. Confirm you can sign in, open a case, read an encrypted field (a mental
   health note) and download an attachment.
5. Record the date, who ran it, and the outcome.

Step 4 is the one that catches the failure that matters: if
`FIELD_ENCRYPTION_KEYS` has been rotated and the old key discarded, the restore
will succeed and the case data will still be unreadable. See
[encryption.md](encryption.md).

## Recovery objectives

These are the defaults implied by the schedule above. Agree the real numbers
with the charity and record them here.

| Objective | Value | Meaning |
|---|---|---|
| RPO | 24 hours | Up to one day of captures could be lost |
| RTO | 4 hours | Time to restore service from a working backup |

If losing a day of frontline captures is not acceptable, increase the backup
frequency — the script is safe to run against a live database.
