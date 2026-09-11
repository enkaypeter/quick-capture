# Go-Live Checklist

**Status: NOT READY FOR LIVE DATA.**

The eleven pre-production security blockers are closed in code
([ADR-008](../adrs/008-security-controls-for-production.md)). Four items
remain, and **none of them are code changes**. No amount of further
development will close them — each needs a decision or an action by the
charity.

Until all four are done, Quick Capture must only be used with synthetic or
demo data.

---

## The four blockers

### 1. Data Protection Impact Assessment

**Not done. Legally required.**

A DPIA is mandatory under UK GDPR Article 35, not merely advisable. This
system meets several of the ICO's criteria for mandatory assessment at once:

- Special-category data (Article 9): mental health notes, health information
- Criminal-adjacent data: risk assessments and safeguarding concerns
- Vulnerable data subjects: homeless people, frequently with `consent_status`
  recorded as `unknown`
- Location tracking: GPS coordinates and What3Words addresses
- Biometric-adjacent processing: voice recordings

Processing without one is a breach in its own right, separate from anything
that might go wrong with the data.

The DPIA must cover, at minimum:

- The lawful basis for processing, and the Article 9 condition relied upon
  (substantial public interest and safeguarding are the likely candidates —
  take advice)
- How consent is handled when it cannot be obtained, and what `consent_status`
  of `unknown` means in practice
- The team-wide visibility decision in
  [ADR-007](../adrs/007-team-wide-case-visibility.md), and why it is
  proportionate
- Retention periods and the erasure process
- The transfer to the hosting provider, and where the data physically sits

**Owner:** charity's data protection lead or trustee with that portfolio.
**Evidence:** a signed, dated DPIA document.

### 2. Retention periods agreed by the charity

**Not done. The current values are placeholders I chose, not advice.**

| Data | Current default | Needs |
|---|---|---|
| Archived cases | 2190 days (6 years) | A decision, with a recorded rationale |
| Access logs | 365 days | Confirmation |
| Login attempts | 30 days | Confirmation |

The retention job will permanently destroy casework once a period elapses. A
period nobody chose is not a retention policy, and the first question asked
about it will be who decided and on what basis.

Six years is a common safeguarding record period, but the right answer depends
on the charity's commissioning obligations and any statutory duty that applies
to its records. Do not accept my default by silence.

Set the agreed values in the environment
(`RETENTION_ARCHIVED_CASE_DAYS`, `RETENTION_ACCESS_LOG_DAYS`,
`RETENTION_LOGIN_ATTEMPT_DAYS`) and record the decision in
[data-retention.md](data-retention.md).

**Owner:** charity, with data protection advice.
**Evidence:** agreed values recorded in this repository and set in production.

### 3. Sign-off on team-wide case visibility

**Not done.**

Every worker with an account can read every active case, including risk notes
and mental health notes. There is no per-case ownership check and no team
boundary.

[ADR-007](../adrs/007-team-wide-case-visibility.md) sets out the reasoning:
in a small outreach team any worker may meet any client, and a risk assessment
that is invisible to the worker standing in front of that person is a
safeguarding hazard rather than a safeguarding control. That argument is
sound, but it is a decision someone has to own — it cannot rest on a developer
having written it down.

Sign-off must also confirm the two things that follow from it:

- The privacy notice states plainly that all workers can see all records, and
  that reads are logged.
- Staff data protection training covers the same.

**Owner:** trustees, or the Senior Information Risk Owner if one is appointed.
**Evidence:** a minuted decision, referenced in the DPIA.

### 4. A restore that has actually been run

**Not done.**

Backup scripts exist and are covered by tests, but no backup taken from a real
deployment has ever been restored. An untested backup is not a backup — it is
an assumption.

The drill is in [backups.md](backups.md#the-restore-drill). Run it end to end
on the chosen host once it exists:

1. Take a backup from the production host.
2. Restore it onto a different machine.
3. Sign in against the restored database.
4. **Open a case and read a mental health note.** This is the step that
   matters: if `FIELD_ENCRYPTION_KEYS` is wrong or missing, the restore will
   appear to succeed and the case data will still be unreadable.
5. Download an attachment.
6. Record the date, who ran it, and the outcome.

**Owner:** whoever operates the host.
**Evidence:** a dated drill record, repeated at least quarterly thereafter.

---

## Also required before go-live

These follow from choosing a host and are not blocked on anything else:

- [ ] **Hosting platform chosen.** Docker is local-only. See
      [deployment.md](deployment.md) for what any host must provide.
- [ ] **Processor agreement** signed with the hosting provider, with data
      resident in the UK or EEA.
- [ ] **ICO registration** current, and the privacy notice updated to cover
      this processing.
- [ ] **Production secrets generated and stored** in a secret manager
      (`python -m scripts.generate_keys`), with `FIELD_ENCRYPTION_KEYS` backed
      up **separately from the database**. Losing it makes encrypted case data
      permanently unreadable.
- [ ] **Backups scheduled** and their failures alerted on.
- [ ] **Retention job scheduled** with the agreed periods.
- [ ] **Named admin accounts created**, MFA enrolled, recovery codes stored
      away from the phone. Demo account, any-code demo MFA
      (`DEMO_ACCOUNT_SHARED_MFA`), demo reset and bootstrap invite off.
- [ ] **Claire and Tracey have tested the MVP** and confirmed field names,
      report data, risk wording, consent wording and daily workflow fit — see
      [status.md](../status.md).

## Known gaps to accept or fix

These are not blockers, but the charity should know about them before go-live
rather than after:

- **No password reset.** A worker who forgets their password needs an admin
  with database access.
- **No offline write queue.** A capture made with no signal is lost. For street
  outreach this is a real operational risk.
- **MFA is mandatory for admins only.** Workers can enable it but are not
  required to.
- **No bulk export for a subject access request.** Producing one means a manual
  query.
- **Erasing a user account** (as opposed to a case) is not implemented.
