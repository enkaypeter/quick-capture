Quick Capture [MVP] is a case management tool for Simon on the Streets social workers. It enables rapid recording of interactions with prospects — capturing names, locations, notes, quick tags, documents, follow-ups and voice recordings with minimal friction.

The system is composed of two services running in Docker containers on the same network:

1. **Web Application** — Flask-based MVC app serving the UI and handling business logic
2. **Transcription Service** — whisper.cpp HTTP server that converts audio recordings to text

Please refer to `docs/architecture.md` for the full system architecture.

## Documentation

- [MVP status](docs/status.md)
- [Frontline worker guide](docs/user-guides/frontline-worker.md)
- [Admin guide](docs/user-guides/admin.md)
- [Architecture](docs/architecture.md)

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

The local demo account also creates 10 fictional demo cases with varied statuses, risk levels, notes, interaction tags, follow-ups and sample documents. Restarting the app will not create copies of these records.

Environment variables can override the local defaults:

```bash
DEMO_ACCOUNT_EMAIL=demo@example.org \
DEMO_ACCOUNT_PASSWORD='replace-with-local-password' \
.venv/bin/python main.py
```

To start with an empty local case list, run with:

```bash
DEMO_CASES_ENABLED=false .venv/bin/python main.py
```

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

## Invite codes

New accounts require an invite code. For local development, the bootstrap invite code is `sots-dev-invite`.

Admins can create operational invite codes in the app:

1. Log in with an admin account.
2. Open `http://localhost:5001/invite-codes`.
3. Add a label, choose the allowed number of uses, and create the code.
4. Copy the generated code and send it through the agreed secure channel.
5. Deny any unused active code that should no longer grant access.

Database-backed invite codes are marked `Used` when their use limit is reached. `Denied` codes cannot be used for sign-up.

For production, keep `DEMO_ACCOUNT_ENABLED=false` and `BOOTSTRAP_INVITE_ENABLED=false` unless you are deliberately bootstrapping first access. Create named admin accounts and use `/invite-codes` for ongoing distribution.

## Usage

- `Home` shows active cases, search, risk status, and upcoming follow-ups.
- `New Case` creates a prospect record from at least one identifying detail.
- Case records use `Case status` for the documented SOTS terms: `Non-caseload`, `Caseload`, and `Client`.
- Entering `Date of birth` automatically fills `Age`; age can still be entered manually if DOB is unknown. When DOB is present, the saved age is recalculated from DOB on create and edit.
- Case detail pages are one-page records with collapsible sections for quick capture, history, identity, status and consent, risk, follow-ups, documents, reporting fields, legacy notes, and activity.
- `Reports` summarises captured interaction tags and exports CSV.
- `Invite Codes` is visible to admins for access management.

## Test

```bash
.venv/bin/python -m pytest -q
```
