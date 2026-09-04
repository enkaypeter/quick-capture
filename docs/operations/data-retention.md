# Data Retention and Erasure

## The problem this solves

Deleting a case used to set `archived_at` and nothing else. The record, its
notes, its voice recordings and its attachments stayed on disk indefinitely.

That has two consequences. An Article 17 erasure request could not be
satisfied — the data was still there. And special-category data about
vulnerable people had no end date, which fails the storage limitation
principle.

Archiving is still the right default: a worker who deletes a case by mistake at
2am must not destroy a safeguarding record. Permanent destruction is now a
separate, deliberate act.

## Two routes to destruction

### 1. An erasure request (immediate)

An **admin** opens the case and confirms permanent erasure by typing the case
identifier. There is no undo, so a stray click cannot destroy a record.

This destroys the case, its notes, interactions, tags, follow-ups, attachments,
audit log rows, access log rows and its files on disk.

Audit rows are destroyed too, and this is deliberate: `audit_logs` stores
`old_value` and `new_value`, so it is a second copy of the case data. Leaving
it behind would mean the erasure was not an erasure.

### 2. The retention policy (scheduled)

`scripts/retention.py` permanently erases archived cases whose retention period
has elapsed, and prunes access logs and login attempts past theirs.

```bash
python -m scripts.retention          # report only - the default
python -m scripts.retention --apply  # destroy
```

It defaults to a dry run. The alternative is a scheduled job that silently
destroys casework the first time someone mistimes a cron entry.

Schedule it daily or weekly:

```
30 3 * * 0 cd /srv/quick-capture && /srv/quick-capture/.venv/bin/python -m scripts.retention --apply >> /var/log/quick-capture-retention.log 2>&1
```

## Retention periods

| Data | Config | Default | Rationale |
|---|---|---|---|
| Archived cases | `RETENTION_ARCHIVED_CASE_DAYS` | 2190 (6 years) | Aligns with the common safeguarding record period. **Agree this with the charity — the default is a placeholder, not advice.** |
| Access logs | `RETENTION_ACCESS_LOG_DAYS` | 365 | Security monitoring data, not casework. Long enough to investigate an incident. |
| Login attempts | `RETENTION_LOGIN_ATTEMPT_DAYS` | 30 | Only needed for the throttling window. |

Agreeing these is blocker 2 in
[go-live-checklist.md](go-live-checklist.md). Set them deliberately. A retention period nobody chose is not a retention
policy, and the ICO will ask who decided and on what basis.

Note that the clock starts at `archived_at`, not `created_at`. An active case is
never destroyed by the retention job, however old it is.

## The erasure log

Every permanent erasure writes a row to `erasure_logs`, readable by admins at
`/erasure-log`.

The row holds the case identifier, the reason, who requested it, counts of
records and files destroyed, and the timestamp. It holds **no personal data** —
it is proof that destruction happened, not a copy of what was destroyed. It has
no foreign key to the case, because the case no longer exists.

## Handling an erasure request

1. Confirm the request is genuine and from the data subject or their
   representative.
2. Check whether an exemption applies. Safeguarding records may be subject to a
   legal obligation or a vital-interests basis that overrides erasure — take
   advice; this is a decision for the charity, not for whoever runs the script.
3. If erasure is agreed, an admin purges the case and records the decision.
4. Backups still contain the record. Note the erasure and confirm it is not
   restored; the data ages out of the backups as they rotate. Tell the data
   subject this — it is the honest answer, and it is what the ICO expects.
5. Keep the `erasure_logs` entry as evidence.

## What is not covered

- There is no bulk export for a subject access request. Producing one currently
  means a manual query.
- Erasing a *user* account (as opposed to a case) is not implemented. Cases
  reference their creating worker by foreign key.
