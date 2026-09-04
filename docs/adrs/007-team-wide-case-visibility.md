# ADR-007: Team-Wide Case Visibility

## Status

Accepted — requires trustee sign-off before live data is entered

## Date

2026-09-04

## Context

Every signed-in worker can read every active case, including risk notes and
mental health notes. There is no per-case ownership check, no team boundary and
no field-level restriction. A case records the worker who created it and the
worker it is assigned to, but neither value limits who can read it.

This was not an explicit decision. It emerged from the MVP being built for a
single small team. Because the data involved is UK GDPR Article 9
special-category data about vulnerable people, an implicit access model is not
acceptable: it has to be a decision someone made on purpose and is accountable
for.

The operational reality argues for the flat model. Simon on the Streets runs a
small outreach team where any worker may encounter any client on any shift. A
worker who meets someone at 11pm needs their risk assessment immediately.
Access rules that make a risk note invisible to the worker standing in front of
that person are a safeguarding hazard, not a safeguarding control.

The countervailing principle is data minimisation: a worker who will never meet
a particular client has no need to read their mental health history, and one
compromised worker account currently exposes the entire caseload.

## Decision

Keep team-wide read access for all authenticated workers, and make it a
deliberate, recorded decision rather than an accident of implementation.

The controls that make it proportionate are:

1. **Access is gated at the door.** Registration requires an invite code issued
   by an admin. There is no open sign-up.
2. **Reads are logged.** Every case view, attachment download, audit trail read
   and CSV export is recorded in `access_logs` with the user, time and IP
   address (ADR-008, blocker 10). Team-wide visibility is acceptable only when
   it is visible who used it.
3. **Access history is open to the team, not just admins.** Any worker can see
   who has read a case, at `/cases/<id>/access-log`.
4. **The most sensitive fields are encrypted at rest**, so the flat model
   applies to authenticated application access only — not to anyone who obtains
   the database file.
5. **Admin functions are not flat.** Invite codes, account management and
   permanent erasure are restricted to the `admin` role.

## Consequences

**Accepted risks**

- One compromised worker account exposes every active case. Login throttling,
  account lockout and mandatory MFA for admins reduce the likelihood; the access
  log limits how long a compromise goes unnoticed.
- The app cannot currently demonstrate need-to-know restriction to a
  commissioner or the ICO. The compensating argument is the safeguarding one
  above, and it must be recorded in the DPIA.

**Required before live data**

- Trustee or SIRO sign-off on this model, recorded in the DPIA.
- The privacy notice and staff data protection training must state plainly that
  all workers can see all records, and that reads are logged.

**Revisit when**

- Headcount grows past roughly 15 workers, or
- Volunteers or students need access, or
- A second team or partner organisation is onboarded.

At that point the natural next step is a team boundary on `Case`, with an
explicit, logged "break glass" override rather than a hard block — so the
safeguarding argument above still holds.

## Alternatives Considered

**Owner-only access.** Rejected: an outreach worker on a night shift would be
unable to read the risk assessment of someone another worker knows well.

**Restricting only mental health and risk notes.** Rejected for now: these are
precisely the fields most needed at the point of contact. Reconsider alongside
a break-glass mechanism.

**Doing nothing and leaving it implicit.** Rejected: the model is defensible,
but only if someone has actually decided it.
