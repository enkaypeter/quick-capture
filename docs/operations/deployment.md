# Deployment

## Docker is for local development only

The `Dockerfile` and `docker-compose.yml` in this repository exist so a
developer can run the whole stack — web app plus transcription service — with
one command. **They are not a production deployment.**

Do not use them to host live data. They are not the deployment target, they
receive no security patching workflow, and the compose file bind-mounts data
into named volumes with no backup, no TLS and no process supervision beyond
`restart: unless-stopped`.

`docker-compose.staging.yml` has been removed for this reason. It described a
container attached to an external reverse-proxy network and was the closest
thing the project had to a production deployment. Keeping it invited someone to
use it as one.

The hosting platform has not yet been chosen. This document therefore states
what any production host must provide, so the decision can be made against a
concrete list rather than in the abstract. Once a platform is chosen, add a
`docs/operations/deployment-<platform>.md` with the concrete configuration and
link it here.

## What production must provide

### 1. A supervised long-running process

The app is a WSGI application served by gunicorn:

```bash
gunicorn --bind 127.0.0.1:5001 --workers 2 --timeout 120 --preload main:app
```

The host must restart it on failure and on reboot — a systemd unit, a platform
process manager, or an equivalent. Bind to localhost and put a reverse proxy in
front; never expose gunicorn directly.

`--preload` is important: it loads the app once before forking, so the
configuration guard runs once and a misconfiguration stops the whole service
rather than crash-looping one worker at a time.

### 2. TLS on every request

- A valid certificate, automatically renewed.
- Plain HTTP redirected to HTTPS.
- The proxy must set `X-Forwarded-Proto`, and the app must run behind
  `werkzeug.middleware.proxy_fix.ProxyFix` so that `request.is_secure` is
  correct and HSTS is emitted.
- The proxy must set `X-Forwarded-For`, otherwise the per-IP login throttle
  will count every request as coming from the proxy. The per-account lockout
  does not depend on this and always holds.

Without TLS, `SESSION_COOKIE_SECURE=true` (which production requires) means no
session cookie is ever sent and nobody can log in. This is intentional.

### 3. The transcription service, reachable privately

Voice notes are transcribed by a whisper.cpp HTTP server that must run
somewhere the app can reach at `TRANSCRIPTION_URL`. Requirements:

- Roughly 1 GB RAM and 2 CPU threads for the `base.en` model.
- **Not reachable from the internet.** It accepts audio uploads with no
  authentication.
- Keeping it self-hosted is a deliberate privacy decision: recordings of
  vulnerable people never reach a third-party AI service. Do not replace it
  with a hosted transcription API without a new DPIA.

### 4. Encrypted storage and managed secrets

- Full-disk or volume encryption for the database and the uploads directory.
- Secrets supplied through the platform's secret store or a root-owned
  environment file with mode `600` — never committed, never in the image.
- `FIELD_ENCRYPTION_KEYS` backed up **separately from the database**. Losing it
  makes encrypted case data permanently unreadable; storing it next to the
  backup defeats the encryption.

### 5. Backups, off-site and tested

See [backups.md](backups.md). Nightly encrypted backups, stored off the
application host, with a restore drill at least quarterly.

### 6. A scheduled retention job

See [data-retention.md](data-retention.md). `python -m scripts.retention --apply`
on a daily or weekly schedule.

### 7. Log handling

Application logs must not be world-readable and must be retained no longer than
necessary. The app does not log case content, but it does log case identifiers
and email addresses.

## Required environment

Generate the secrets first:

```bash
python -m scripts.generate_keys
```

```bash
FLASK_ENV=production

# Fatal if missing - see app/security/config_guard.py
SECRET_KEY=<48+ random characters>
FIELD_ENCRYPTION_KEYS=<Fernet key>
SESSION_COOKIE_SECURE=true

# Backups
BACKUP_ENCRYPTION_KEY=<Fernet key>
BACKUP_DESTINATION=/var/backups/quick-capture

# Access
BOOTSTRAP_INVITE_ENABLED=false
DEMO_ACCOUNT_ENABLED=false
DEMO_CASES_ENABLED=false
MFA_REQUIRED_ROLES=admin

# Services
TRANSCRIPTION_URL=http://127.0.0.1:8080
W3W_API_KEY=<key>

# Storage
DATABASE_URL=sqlite:////srv/quick-capture/instance/database.db
```

Optional tuning, with defaults from `config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `SESSION_IDLE_MINUTES` | 30 | Idle timeout |
| `LOGIN_MAX_ATTEMPTS_PER_ACCOUNT` | 5 | Failures before lockout |
| `LOGIN_MAX_ATTEMPTS_PER_IP` | 20 | Failures before an IP is throttled |
| `LOGIN_LOCKOUT_MINUTES` | 15 | Lockout duration |
| `ACCESS_LOG_DEDUPE_MINUTES` | 5 | Collapse repeat views |
| `RETENTION_ARCHIVED_CASE_DAYS` | 2190 | Retention for archived cases |
| `HSTS_ENABLED` | true in production | Strict-Transport-Security |

## The configuration guard

Starting with `FLASK_ENV=production` runs
`app/security/config_guard.py`, which **refuses to start** on any of:

- `SECRET_KEY` missing, shorter than 32 characters, or the development default
- `FIELD_ENCRYPTION_KEYS` missing
- `SESSION_COOKIE_SECURE` off
- `BOOTSTRAP_INVITE_ENABLED` on with a missing or development invite code
- `DEMO_ACCOUNT_ENABLED` on with a missing or default password
- `DEMO_CASES_ENABLED` on
- `DEBUG` on

Every problem is reported at once. This is a hard failure by design: an app
running on a publicly known secret key looks perfectly healthy.

## First run

1. Deploy the code and set the environment above.
2. Start the app. It creates the schema and runs migrations automatically.
3. Create the first admin. There is no self-service admin creation:

   ```bash
   BOOTSTRAP_INVITE_ENABLED=true SIGNUP_INVITE_CODE='<a private one-off code>' \
     gunicorn ... main:app
   ```

   Register through `/sign-up`, then promote the account:

   ```sql
   UPDATE users SET role = 'admin' WHERE email = '<address>';
   ```

   Restart **without** `BOOTSTRAP_INVITE_ENABLED`.
4. Sign in as that admin. You will be required to enrol in MFA before you can
   go anywhere else. Save the recovery codes somewhere separate from the phone.
5. Issue invite codes to workers from `/invite-codes`.
6. Run a backup and a restore drill before anyone enters real data.

## Before real data is entered

Deploying this correctly does not make it lawful to use. Four things remain,
and none of them are code changes:

1. A **Data Protection Impact Assessment** — legally required under Article 35
2. **Retention periods agreed by the charity**, not left at the defaults
3. **Trustee sign-off** on team-wide case visibility (ADR-007)
4. **A restore drill actually run** against this deployment

The full list, including the processor agreement and ICO registration, is in
**[go-live-checklist.md](go-live-checklist.md)**. Work through it before
anyone enters a real person's details.
