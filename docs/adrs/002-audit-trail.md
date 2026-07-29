# ADR-002: Audit Trail

## Status

Accepted

## Date

2026-07-29

## Context

Case files contain sensitive information about vulnerable individuals. Social workers, team leads, and safeguarding officers need visibility into who changed what and when. This is critical for:

- Accountability — knowing who made a specific change
- Dispute resolution — understanding what information was present at a given time
- Compliance — demonstrating proper data handling for audits
- Debugging — tracing unexpected data changes

## Decision

We will implement an **event-sourced audit log** that records every mutation to a case and its related entities. The audit trail captures:

| Field | Purpose |
|-------|---------|
| `case_id` | Which case was affected |
| `user_id` | Who performed the action |
| `action` | Type: `created`, `updated`, `deleted` |
| `field_name` | What was changed (e.g. `full_name`, `note:42`, `category`, `actions`) |
| `old_value` | Previous value (null for creates) |
| `new_value` | New value (null for deletes) |
| `timestamp` | When it happened |

### Design choices:

1. **Dedicated table** (`audit_logs`) rather than soft-deletes or versioned rows — simpler, append-only, doesn't bloat main tables.

2. **Service-level logging** — the `AuditService` is called explicitly from `CaseService` methods rather than using SQLAlchemy event hooks. This gives us control over what constitutes a meaningful audit entry (e.g. we log "category changed from X to Y" rather than every column update).

3. **Lazy-loaded UI** — the audit timeline is hidden by default on the case detail page and only fetched via `GET /cases/<id>/audit` when the user clicks "Show history". This avoids slowing down page loads.

4. **No audit of audit** — audit log entries themselves are immutable. They cannot be edited or deleted through the application.

## Consequences

- Every mutation path in `CaseService` must call `AuditService`. New service methods must follow this pattern.
- The `user_id` parameter was added to all mutation methods (`add_note`, `delete_note`, `mark_note_reviewed`, `update_category`, `delete_case`). Views must pass `current_user.id`.
- Audit entries for note content changes store `"(content edited)"` / `"(content updated)"` rather than the full HTML, to avoid storing large blobs.
- The audit table will grow indefinitely. A future consideration is archiving entries older than N months.

## Technical Details

### Files

- `app/models/audit_log.py` — `AuditLog` model + `AuditAction` constants
- `app/repositories/audit_log_repository.py` — query by case, user, recent
- `app/services/audit_service.py` — `log_create()`, `log_update()`, `log_delete()`, `get_audit_trail()`
- `app/views/cases.py` — `GET /cases/<id>/audit` JSON endpoint
- `app/templates/cases/detail.html` — collapsible Activity section with icon-coded timeline
