> ## ⚠️ Not ready for live data
>
> Four things must happen before real case data is entered, and **none of them
> are code changes**:
>
> 1. A **Data Protection Impact Assessment** — legally required under Article 35
> 2. **Retention periods agreed by the charity** — the current values are
>    placeholders, not advice
> 3. **Trustee sign-off** that all workers can read all cases ([ADR-007](docs/adrs/007-team-wide-case-visibility.md))
> 4. **A restore drill actually run** — an untested backup is not a backup
>
> Until all four are done, use synthetic or demo data only.
> Full detail: **[docs/operations/go-live-checklist.md](docs/operations/go-live-checklist.md)**

Quick Capture [MVP] is a case management tool for Simon on the Streets social workers. It enables rapid recording of interactions with prospects — capturing names, locations, notes, quick tags, documents, follow-ups and voice recordings with minimal friction.

The system is composed of two services:

1. **Web Application** — Flask-based MVC app serving the UI and handling business logic
2. **Transcription Service** — whisper.cpp HTTP server that converts audio recordings to text

Voice notes are transcribed on infrastructure the charity controls. Recordings of vulnerable people are never sent to a third-party AI service.

Please refer to `docs/architecture.md` for the full system architecture.

> **Docker is for local development only.** The `Dockerfile` and `docker-compose.yml` exist so a developer can run both services with one command. They are not a production deployment and must not be used to host live data. Production requirements are in [docs/operations/deployment.md](docs/operations/deployment.md).

## Documentation

- [MVP status](docs/status.md)
- [Frontline worker guide](docs/user-guides/frontline-worker.md)
- [Admin guide](docs/user-guides/admin.md)
- [Architecture](docs/architecture.md)

### Operations

- **[Go-live checklist](docs/operations/go-live-checklist.md)** — what still blocks live data
- [Deployment](docs/operations/deployment.md) — what a production host must provide
- [Security controls](docs/operations/security-controls.md) — what protects the system, and how to verify it
- [Backups and restore](docs/operations/backups.md)
- [Field-level encryption](docs/operations/encryption.md) — including key rotation
- [Data retention and erasure](docs/operations/data-retention.md)

## Run locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Open `http://localhost:5001`.

The local app seeds a demo admin account by default:

- Email: `demo@quickcapture.local`
- Password: `demo-password-123`

The demo account is shared, so locally it is already enrolled in two-factor authentication and its code prompt accepts any 6 digits. Every other admin account still has to set up a real authenticator app on first sign-in. Set `DEMO_ACCOUNT_SHARED_MFA=false` to make the demo account enrol like any other admin.

The local demo account also creates 10 fictional demo cases with varied statuses, risk levels, notes, interaction tags, follow-ups and sample documents. Restarting the app will not create copies of these records.

Environment variables can override the local defaults:

```bash
DEMO_ACCOUNT_EMAIL=demo@example.org \
DEMO_ACCOUNT_PASSWORD='replace-with-local-password' \
.venv/bin/python main.py
```

To put the demo account back to just the demo cases — deleting anything it created — run:

```bash
.venv/bin/python -m scripts.reset_demo --apply
```

A demo deployment can do this automatically every night with `DEMO_RESET_TIME=03:00`. See [ADR-009](docs/adrs/009-shared-demo-account.md) and [docs/operations/deployment.md](docs/operations/deployment.md#demo-deployments).

To start with an empty local case list, run with:

```bash
DEMO_CASES_ENABLED=false .venv/bin/python main.py
```

## Run with Docker (local development)

```bash
cp .env.example .env
docker compose up --build
```

This starts the app and the transcription service together. It is a development convenience only — see the note above.

## Invite codes

New accounts require an invite code. For local development, the bootstrap invite code is `sots-dev-invite`.

> This code is published here, so it must never be accepted in production. The production configuration has no default invite code, and the app refuses to start if `BOOTSTRAP_INVITE_ENABLED` is on with this value.

Admins can create operational invite codes in the app:

1. Log in with an admin account.
2. Open `http://localhost:5001/invite-codes`.
3. Add a label, choose the allowed number of uses, and create the code.
4. Copy the generated code and send it through the agreed secure channel.
5. Deny any unused active code that should no longer grant access.

Database-backed invite codes are marked `Used` when their use limit is reached. `Denied` codes cannot be used for sign-up.

For production, keep `DEMO_ACCOUNT_ENABLED=false` and `BOOTSTRAP_INVITE_ENABLED=false` unless you are deliberately bootstrapping first access. Create named admin accounts and use `/invite-codes` for ongoing distribution.

## Security

Every signed-in worker can read every active case, including risk and mental health notes. This is a deliberate decision recorded in [ADR-007](docs/adrs/007-team-wide-case-visibility.md), and it needs trustee sign-off before live data is entered.

The controls protecting the system — login throttling, mandatory MFA for admins, field-level encryption, access logging, a Content Security Policy, retention and erasure — are described in [docs/operations/security-controls.md](docs/operations/security-controls.md) and were introduced by [ADR-008](docs/adrs/008-security-controls-for-production.md).

Generate production secrets with:

```bash
.venv/bin/python -m scripts.generate_keys
```

## Usage

- `Home` shows active cases, search, risk status, and upcoming follow-ups.
- `New Case` creates a prospect record from at least one identifying detail.
- Case records use `Case status` for the documented SOTS terms: `Non-caseload`, `Caseload`, and `Client`.
- Entering `Date of birth` automatically fills `Age`; age can still be entered manually if DOB is unknown. When DOB is present, the saved age is recalculated from DOB on create and edit.
- Case detail pages are one-page records with collapsible sections for quick capture, history, identity, status and consent, risk, follow-ups, documents, reporting fields, legacy notes, and activity.
- `Reports` summarises captured interaction tags and exports CSV.
- `Security` is where any user manages their own two-factor authentication.
- `Invite Codes`, `Accounts` and the erasure log are visible to admins for access management.

## Operational scripts

```bash
.venv/bin/python -m scripts.generate_keys                        # production secrets
.venv/bin/python -m scripts.backup --destination /var/backups    # encrypted backup
.venv/bin/python -m scripts.restore --archive <file> --target <dir>
.venv/bin/python -m scripts.retention                            # dry run
.venv/bin/python -m scripts.retention --apply                    # apply retention
```

## Test

```bash
.venv/bin/python -m pytest -q
```
