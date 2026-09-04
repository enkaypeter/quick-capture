# ADR-008: Security Controls for Production

## Status

Accepted

## Date

2026-09-04

## Context

A pre-production assessment of the MVP identified eleven blockers that had to
be closed before real data about vulnerable people could be entered. The
findings shared a root cause: the app was built to be easy to run locally, and
the conveniences that make that true — a default `SECRET_KEY`, a published
invite code, seeded demo data, unlimited login attempts, plaintext storage —
are exactly the properties that make it unsafe in production.

The data involved is UK GDPR Article 9 special-category data: names, dates of
birth, National Insurance numbers, mental health notes, risk assessments, GPS
locations and voice recordings of homeless and vulnerable people, frequently
captured with `consent_status` set to `unknown`.

## Decision

Close all eleven blockers, and prefer controls that fail loudly over controls
that depend on an operator remembering something.

| # | Blocker | Control | Where |
|---|---------|---------|-------|
| 1 | Default `SECRET_KEY` | Production refuses to boot without real secrets | `app/security/config_guard.py` |
| 2 | Published invite code usable in production | No production default; guard rejects the dev code | `config.py`, `config_guard.py` |
| 3 | Unlimited login attempts | Per-account lockout and per-IP throttle, in the database | `app/services/login_throttle_service.py` |
| 4 | No backups | Encrypted backup and restore scripts, plus a restore drill | `scripts/backup.py`, `scripts/restore.py` |
| 5 | No encryption at rest | Fernet field encryption on NI number, risk and mental health notes | `app/security/crypto.py` |
| 6 | Third-party CDN script on every page | Tailwind vendored locally; CSP with per-request nonces | `app/security/headers.py` |
| 7 | No session timeout | 30-minute idle timeout on a permanent, refreshing session | `config.py`, `app/__init__.py` |
| 8 | No MFA | Mandatory TOTP for admins, with recovery codes | `app/services/mfa_service.py` |
| 9 | Undocumented flat authorisation | Recorded decision plus regression tests | ADR-007 |
| 10 | No read logging | `access_logs` records who read what | `app/services/access_log_service.py` |
| 11 | No hard delete or retention | Purge with an erasure log, plus a retention job | `app/services/retention_service.py` |

### Principles applied

**Fail loudly, not safely-by-convention.** `validate_production_config` reports
every problem at once and refuses to start. A misconfiguration that only
produces a log line will reach production.

**Development stays zero-setup.** None of the guards apply to the development
or testing configurations. A control that makes local work painful gets
disabled, and then it is not a control.

**Security controls must not block frontline work.** Access logging swallows
its own failures: a dropped log line is bad, a worker blocked from reading a
risk assessment at 11pm is worse.

**Encryption is applied only to fields nothing queries.** `ni_number`,
`risk_notes` and `mental_health_notes` are encrypted; `full_name`,
`date_of_birth` and `physical_description` are not, because dashboard search
depends on them. This is a real limitation, recorded in
`docs/operations/encryption.md`.

## Consequences

- Production now requires a managed secret: `SECRET_KEY`,
  `FIELD_ENCRYPTION_KEYS` and `BACKUP_ENCRYPTION_KEY` must exist and be backed
  up separately from the database. **Losing `FIELD_ENCRYPTION_KEYS` makes
  encrypted case data permanently unreadable.**
- Three new dependencies: `cryptography`, `pyotp`, `qrcode`.
- Admins cannot use the app until they enrol in MFA. Recovery codes exist so
  that a lost phone does not lock the charity out of its own records.
- Encrypted fields cannot be searched or sorted in SQL.
- `style-src` still requires `'unsafe-inline'`, because the vendored Tailwind
  build compiles classes in the browser. Removing that needs a build-time
  Tailwind step, tracked in `docs/status.md`.
- Docker is now explicitly a local development tool only. See
  `docs/operations/deployment.md`.

## Not Covered

These remain outstanding and are **not** closed by this ADR. Closing eleven
code blockers does not make the system lawful to use; the remaining work is
organisational, and is tracked in
[operations/go-live-checklist.md](../operations/go-live-checklist.md).

- A Data Protection Impact Assessment. Legally required here (Article 35), and
  a document, not a code change.
- Retention periods agreed by the charity rather than the placeholder defaults.
- Trustee sign-off on ADR-007.
- A restore drill run against a real deployment.
- Password reset and self-service account recovery.
- MFA for non-admin workers (supported by config, not yet mandated).
- Single sign-on, which would remove password handling entirely.
