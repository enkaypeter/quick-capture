# Field-Level Encryption

## What is encrypted

Three columns on `cases` are encrypted in the database:

| Column | Why |
|---|---|
| `ni_number` | National Insurance number — a direct government identifier |
| `mental_health_notes` | Article 9 health data |
| `risk_notes` | Safeguarding assessments, often about third parties too |

`users.totp_secret` is also encrypted: it is a credential, and anyone who reads
it can generate valid login codes indefinitely.

Volume encryption protects data when a disk is stolen. It does nothing once the
host is running — a database file copied off a live server is readable. These
are the fields an auditor or the ICO will ask about specifically, so they are
protected in the database as well.

## What is not encrypted, and why

`full_name`, `date_of_birth`, `phone_number`, `physical_description` and
location fields are **not** encrypted, because dashboard search queries them
directly in SQL. Encrypted values cannot be searched or sorted by the database.

This is a real limitation, not an oversight. Encrypting them would require
either a searchable-encryption scheme or moving search into application memory,
and both are larger changes than the MVP warrants. The compensating controls
are volume encryption, the access log, and the invite-only account model.

**Before adding `EncryptedText` to a column, check nothing filters, sorts or
searches on it.**

## How it works

`app/security/crypto.py` provides an `EncryptedText` SQLAlchemy type that
encrypts on write and decrypts on read. Ciphertext carries an `enc:v1:` prefix.

That prefix is what makes migration possible: a value without it is plaintext
written by an older version, and is returned unchanged rather than causing an
error. `_encrypt_sensitive_case_fields` in `app/migrations.py` rewrites those
rows as ciphertext on startup, and is safe to run repeatedly.

## Keys

`FIELD_ENCRYPTION_KEYS` is a comma-separated list of Fernet keys. The first key
encrypts; every key is tried when decrypting.

```bash
python -m scripts.generate_keys
```

**Losing every key that a value was encrypted with makes that value permanently
unreadable.** No support process recovers it. Therefore:

- Store the keys in a secret manager, not in the repository or the image.
- Back them up **separately from the database backups**. Storing the key
  alongside the encrypted archive defeats the encryption.
- Record who holds a copy, so that one person leaving does not take the only
  copy with them.

If no key is configured, the columns store plaintext. That keeps local
development zero-setup, and `config_guard` refuses to start production without
keys.

## Rotating a key

Rotation works by adding, then removing — never by replacing.

1. **Add the new key first**, ahead of the old one:

   ```bash
   FIELD_ENCRYPTION_KEYS=<new-key>,<old-key>
   ```

   New writes use the new key. Existing values still decrypt with the old one.

2. **Restart the app.** Both keys are now active.

3. **Re-encrypt existing rows.** Read and re-save each encrypted value so it is
   rewritten under the new key:

   ```python
   from app import create_app
   from app.extensions import db
   from app.models.case import Case

   app = create_app("production")
   with app.app_context():
       for case in Case.query.all():
           case.ni_number = case.ni_number
           case.risk_notes = case.risk_notes
           case.mental_health_notes = case.mental_health_notes
       db.session.commit()
   ```

4. **Take a backup and run a restore drill** before going further.

5. **Only then remove the old key.** Retain it offline for at least one full
   backup retention cycle: any backup taken before step 3 still needs it.

Removing the old key too early leaves values that decrypt to nothing. The
application logs an error and returns `None` rather than crashing, so the
failure shows up as blank risk notes — which is exactly why step 4 exists.
