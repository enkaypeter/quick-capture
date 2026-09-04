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
19 passed
```

## What Remains Outstanding

### Search Inside A Case

Dashboard search exists. Search inside one case profile does not exist yet.

### Full User Management

Admins can manage invite codes. They cannot yet:

- change a user role
- disable a user
- reset a password
- see all users in one place

### Case Assignment UI

The database stores an assigned worker. The page does not yet let an admin or worker change the assignee.

### More Reporting Setup

The reports page is a useful start. The final report fields still need to match SOTS contract, grant and board reporting needs.

### Configurable Tags And Fields

Quick tags and report fields are fixed in code. Admins cannot yet change them in the app.

### Offline Saving

The app keeps some draft note text in the browser. It does not yet queue saved records while offline.

### Production Readiness

Before real data is used, the team still needs decisions on:

- hosting
- backups
- account setup
- access rules
- data retention
- encryption for sensitive fields

### Client Review

Claire and Tracey still need to test the MVP and confirm:

- field names
- required report data
- risk wording
- consent wording
- daily workflow fit
