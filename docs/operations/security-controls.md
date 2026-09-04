# Security Controls

A reference for what protects this system, where it lives and how to verify it.
The reasoning behind these choices is in
[ADR-008](../adrs/008-security-controls-for-production.md).

## Authentication

| Control | Behaviour |
|---|---|
| Passwords | `pbkdf2:sha256`, minimum 8 characters |
| Account lockout | 5 failed attempts locks the account for 15 minutes |
| IP throttle | 20 failures from one address blocks it for 15 minutes |
| MFA | TOTP, mandatory for admins, with 8 single-use recovery codes |
| Session timeout | 30 minutes idle, refreshed on activity |
| Registration | Invite code only; no open sign-up |

Throttle state is in the `login_attempts` table, not process memory, because
production runs several gunicorn workers and an in-memory counter would give an
attacker one full allowance per worker.

Failed MFA codes count towards the same lockout as failed passwords, so a
stolen password does not buy unlimited guesses at the second factor.

An admin can clear a lockout at `/users`.

### MFA enrolment

An admin who has not enrolled is redirected to `/mfa/setup` before they can
reach any other page. Enrolment is two steps — a secret is generated, then
activated only once the user proves they can generate a code from it — so it is
not possible to lock yourself out with a secret your app never received.

Recovery codes are shown exactly once. If they are lost and the phone is lost,
the account can only be recovered by clearing `mfa_enabled` and `totp_secret`
directly in the database.

## Authorisation

Two roles: `worker` and `admin`.

Every authenticated worker can read every active case. This is a deliberate,
recorded decision — see
[ADR-007](../adrs/007-team-wide-case-visibility.md) — and it needs trustee
sign-off before live data is entered.

Admin-only: `/invite-codes`, `/users`, `/erasure-log`, permanent case erasure.

## Data protection

| Control | Scope |
|---|---|
| Field encryption | `ni_number`, `risk_notes`, `mental_health_notes`, `totp_secret` |
| Transport | TLS required; `SESSION_COOKIE_SECURE` forced in production |
| At rest | Volume encryption required of the host |
| Backups | Encrypted at creation, mode `600` |
| Transcription | Self-hosted whisper.cpp; audio never leaves the infrastructure |

See [encryption.md](encryption.md) for what is deliberately *not* encrypted.

## Web hardening

| Header | Value |
|---|---|
| `Content-Security-Policy` | `script-src 'self' 'nonce-...'`, `frame-ancestors 'none'`, `object-src 'none'` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | camera off; microphone and geolocation same-origin only |
| `Cache-Control` | `no-store` |
| `Strict-Transport-Security` | one year, HTTPS requests only |

Tailwind is served from `app/static/vendor/`, not `cdn.tailwindcss.com`. Every
page in this app renders NI numbers and mental health notes into the DOM; a
third-party script tag on those pages has full read access to them.

CSRF protection covers every `POST`, `PUT`, `PATCH` and `DELETE`
(`app/services/csrf_service.py`). Note text is sanitised with `bleach`.

### Known limitation

`style-src` still allows `'unsafe-inline'`, because the vendored Tailwind build
compiles classes in the browser and injects `<style>` elements. Closing this
requires a build-time Tailwind step that produces a static stylesheet. Tracked
in `docs/status.md`.

## Logging and monitoring

| Log | Contents | Retention |
|---|---|---|
| `audit_logs` | Who changed what, with old and new values | With the case |
| `access_logs` | Who read what, with IP and user agent | 365 days |
| `login_attempts` | Authentication attempts | 30 days |
| `erasure_logs` | What was permanently destroyed | Indefinite (no personal data) |

Search terms are **not** stored — a search term is usually a person's name, and
the access log must not become a second copy of case data.

Access logging never blocks a request: if it fails, the failure is logged and
the page still renders. A dropped log line is bad; a frontline worker blocked
from a risk assessment at 11pm is worse.

## Verifying the controls

```bash
.venv/bin/python -m pytest -q
```

| Suite | Covers |
|---|---|
| `tests/test_config_guard.py` | Production refuses unsafe configuration |
| `tests/test_authentication.py` | Throttling, lockout, MFA, session timeout |
| `tests/test_encryption.py` | Encryption at rest, key rotation, migration |
| `tests/test_security_headers.py` | CSP, no third-party scripts, headers |
| `tests/test_access_logging.py` | Read logging and deduplication |
| `tests/test_retention_and_erasure.py` | Purge, erasure log, retention job |
| `tests/test_backups.py` | Encrypted backup and restore round trip |
| `tests/test_authorisation_model.py` | The flat access model, as decided |

## Still outstanding

The four organisational items that block live data are in
[go-live-checklist.md](go-live-checklist.md). Beyond those, these are **not**
closed:

- A Data Protection Impact Assessment (legally required, Article 35)
- Password reset and self-service recovery
- MFA for workers (supported by config, not mandated)
- Single sign-on
- Rate limiting on routes other than login
- Offline write queue for field workers
