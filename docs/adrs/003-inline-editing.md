# ADR-003: Inline Editing of Case Fields and Notes

## Status

Accepted

## Date

2026-07-29

## Context

Social workers often need to correct or update case information after initial creation — typos in names, updated phone numbers, or refining transcribed notes. Previously, there was no way to edit existing data without deleting and recreating.

The requirement specifies that most fields should be editable, with two exceptions:

- **Location** — immutable because it represents where the interaction physically happened
- **Created at** — immutable system metadata

## Decision

We will implement **click-to-edit inline editing** on the case detail page for:

### Case fields (via `POST /cases/<id>/edit`)

- `full_name` — text input
- `phone_number` — tel input

### Note content (via `POST /cases/<id>/notes/<id>/edit`)

- `content` — Quill WYSIWYG editor (same as the add-note editor)

### UX Pattern

1. **Display mode** — field shows current value with a subtle pencil icon on hover
2. **Edit mode** — clicking the field reveals an input/editor with Save and Cancel buttons
3. **Save** — sends AJAX request, updates display in-place on success
4. **Cancel** — reverts to display mode without saving
5. **Keyboard shortcuts** — Enter saves, Escape cancels (for text inputs)

### Not editable

- `location_w3w`, `location_lat`, `location_lng` — represents physical location of the interaction
- `created_at` — system-generated timestamp
- `identifier` — auto-generated, used as a stable reference
- `category` — handled separately via the category toggle feature (ADR-004)

## Consequences

- All edits are audited via `AuditService` (see ADR-002)
- The Quill CDN script is loaded on the detail page (already present for add-note)
- Multiple Quill instances may exist simultaneously (one per note being edited + the add-note editor)
- Note content is stored as HTML; the edit saves the full HTML from Quill
- There is no confirmation dialog for saves — the action is immediately committed

## Technical Details

### Files

- `app/services/case_service.py` — `update_case_fields()`, `update_note_content()`
- `app/views/cases.py` — `POST /cases/<id>/edit`, `POST /cases/<id>/notes/<id>/edit`
- `app/templates/cases/detail.html` — `.editable-field` pattern for case fields, per-note editor divs

### API Contracts

**Edit case fields:**
```json
POST /cases/<id>/edit
Body: { "full_name": "New Name", "phone_number": "07123456789" }
Response: { "success": true, "full_name": "New Name", "phone_number": "07123456789" }
```

**Edit note content:**
```json
POST /cases/<id>/notes/<id>/edit
Body: { "content": "<p>Updated note content</p>" }
Response: { "success": true, "content": "<p>Updated note content</p>" }
```
