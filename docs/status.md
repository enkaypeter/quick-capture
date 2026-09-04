# MVP Status

This page records what the current MVP can do and what is still missing.

## What Has Been Achieved

### Safer Notes

The app cleans note text before it is shown on screen. This helps block unsafe HTML from notes and interaction records.

### Better Case IDs

The app now checks for the next free case ID. It does not reuse an old ID after a case is archived.

### Team Case View

Cases are visible to the team by default. A case also stores the worker who created it and the worker it is assigned to.

### Search On The Dashboard

Users can search active cases from the dashboard.

Search includes:

- name
- case ID
- phone
- date of birth
- location
- physical description

### More Identity Fields

The case record now includes:

- date of birth
- age
- gender
- physical description
- other contact details

Date of birth fills age for the user. If date of birth is present, the saved age is worked out from it.

### Clearer Case Status

The app now calls the field `Case status`.

It still uses the SOTS terms:

- `Non-caseload`
- `Caseload`
- `Client`

Short notes on the page explain what each term means.

### Consent Record

Each case has:

- consent status
- consent date

The consent status is shown near the top of the case page.

### Risk At A Glance

Each case has:

- risk rating
- risk notes
- mental health notes

The risk rating is shown on the case list and on the case page.

### Welfare Checks And Interactions

Each case has a `Quick Capture` section.

Users can add:

- a welfare check
- food or drink support
- sleeping bag support
- taxi support
- GP support
- housing support
- benefits support
- signposting
- medication check
- other support

These tags feed the reports page.

### Follow-Ups

Users can add follow-up tasks to a case.

Each follow-up has:

- a title
- a due date
- an owner
- a status

Open follow-ups appear on the dashboard.

### Documents

Users can upload documents to a case. Demo cases include sample text files.

### Reports

The reports page shows simple counts from active cases and interaction tags. Users can export a CSV file.

### Soft Delete

Cases are archived, not destroyed. Archived cases are hidden from the active list.

### Demo Data

Local startup creates:

- one demo admin account
- 10 fictional demo cases

The demo cases cover different case statuses, risks, notes, follow-ups, reports and documents.

Starting the app again will not create copies of these records.

### Tests

The test suite covers the main MVP flows.

Current result:

```bash
160 passed
```

The suite now covers the production security controls as well as the MVP
flows — see the table in
[operations/security-controls.md](operations/security-controls.md).

### Security Controls

The app now enforces the controls needed before real data can be entered:

- Production refuses to start on unsafe configuration, such as a missing or
  default `SECRET_KEY`.
- Repeated failed logins lock an account; repeated failures from one address
  throttle it.
- Admins must set up two-factor authentication before they can use the app,
  and are given recovery codes in case they lose their phone.
- Sessions time out after 30 minutes of inactivity.
- National Insurance numbers, risk notes and mental health notes are encrypted
  in the database.
- The app records who *read* a case, not only who changed it. Any worker can
  see that history on a case.
- Admins can permanently erase a case for a data subject erasure request, and a
  scheduled job destroys archived cases past their retention period.
- Encrypted backups and a tested restore path exist.
- Pages no longer load any script from a third-party CDN.

## What Remains Outstanding

### Search Inside A Case

Dashboard search exists. Search inside one case profile does not exist yet.

### Full User Management

Admins can manage invite codes, see every account in one place at `Accounts`,
and unlock an account that has been locked by failed logins.

They still cannot:

- change a user role (this is a database change)
- disable or remove a user
- reset a password

### Case Assignment UI

The database stores an assigned worker. The page does not yet let an admin or worker change the assignee.

### More Reporting Setup

The reports page is a useful start. The final report fields still need to match SOTS contract, grant and board reporting needs.

### Configurable Tags And Fields

Quick tags and report fields are fixed in code. Admins cannot yet change them in the app.

### Offline Saving

The app keeps some draft note text in the browser. It does not yet queue saved records while offline.

### Production Readiness

The eleven pre-production security blockers identified in the hosting
assessment are now closed in code. See
[ADR-008](adrs/008-security-controls-for-production.md) and
[operations/security-controls.md](operations/security-controls.md).

**The app is not ready for live data.** Four things remain, and none of them
are code changes — see
[operations/go-live-checklist.md](operations/go-live-checklist.md) for the
detail, owner and evidence needed for each:

1. A **Data Protection Impact Assessment** (legally required, Article 35)
2. **Retention periods agreed by the charity**, not the placeholder defaults
3. **Trustee sign-off** on team-wide case visibility (ADR-007)
4. **A restore drill actually run**

Also outstanding:

- **Hosting is not chosen.** Docker is now explicitly local-only.
  [operations/deployment.md](operations/deployment.md) states what any
  production host must provide, so the decision can be made against a concrete
  list.
- **A DPIA has not been done.** This is legally required under Article 35 for
  special-category data about vulnerable people.
- **Retention periods are placeholders.** The defaults in
  [operations/data-retention.md](operations/data-retention.md) need agreeing
  with the charity.
- **ADR-007 needs trustee sign-off.** All workers can read all cases; that is
  a decision someone has to own.
- **No restore has been run yet.** An untested backup is not a backup.
- **Password reset does not exist.** A worker who forgets their password needs
  an admin with database access.

### Tailwind Build Step

Tailwind is now served from this app rather than a CDN, but it still compiles
styles in the browser. That forces one relaxation in the Content Security
Policy (`style-src 'unsafe-inline'`). A build-time Tailwind step would close it
and make pages faster.

### Password Reset

A worker who forgets their password still needs an admin with database access.
Self-service reset needs an email sending route, which the app does not have.

### Client Review

Claire and Tracey still need to test the MVP and confirm:

- field names
- required report data
- risk wording
- consent wording
- daily workflow fit
