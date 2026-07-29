# ADR-004: Category-Based Contextual Fields

## Status

Accepted

## Date

2026-07-29

## Context

Cases progress through categories as the relationship between social worker and prospect deepens:

| Category | Description |
|----------|-------------|
| `non-caseload` | Default. First-time interaction with limited information |
| `caseload` | Ongoing engagement — worker is actively supporting this person |
| `client` | Full client relationship — verified identity, formal support plan |

Each category has different data requirements:

- **Caseload** cases need to track **actions** performed with the person (home visits, GP referrals, benefits applications, etc.)
- **Client** cases require a **National Insurance number** or equivalent personal identifier to formally register the relationship

## Decision

### Category Toggle

The category display on the case detail page is now an interactive `<select>` dropdown that allows immediate switching between categories. Changing the category:

1. Shows/hides the relevant contextual section (actions or NI number)
2. Sends a `POST /cases/<id>/category` request to persist the change
3. Logs the change in the audit trail

### Caseload: Actions Checklist

When a case is in the `caseload` category, an "Actions" panel appears with:

- **8 predefined action types** as checkboxes (home visit, referral to GP, benefits application, housing referral, mental health referral, substance misuse support, food bank referral, appointment booked)
- **Custom action input** — a text field + "Add" button for actions not covered by the predefined list
- **Save Actions button** — persists the current state of all checked actions

Actions are stored in the `case_actions` table with `action_type` (predefined key or "custom"), `label`, and `completed` boolean.

### Client: National Insurance Number

When a case is in the `client` category, an "NI Number" panel appears with:

- A text input for entering the National Insurance number
- A "Save" button to persist
- **Validation**: switching to `client` requires an NI number to be set (either already stored or provided in the same request)

The `ni_number` field is stored directly on the `cases` table.

## Consequences

- The category change is no longer just a simple field update — it may trigger validation (NI required for client) or UI changes (actions panel)
- Predefined actions are defined as constants in `PredefinedAction` class. Adding new predefined actions requires a code change but no migration.
- Custom actions are free-text — there's no deduplication or normalisation
- Actions are replaced wholesale on save (delete all + recreate) rather than diffed individually. This simplifies the logic at the cost of losing individual action timestamps on updates.
- The NI number is stored in plain text. A future consideration is encryption at rest for PII fields.

## Technical Details

### New Model: `CaseAction`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer PK | |
| `case_id` | FK → cases | Parent case |
| `action_type` | String(50) | Predefined key or "custom" |
| `label` | String(200) | Display label |
| `completed` | Boolean | Whether the action has been done |
| `created_at` | DateTime | |

### Modified Model: `Case`

- Added `ni_number` column (String(20), nullable)
- Added `actions` relationship (cascade delete-orphan)

### Files

- `app/models/case_action.py` — `CaseAction` model + `PredefinedAction` constants
- `app/models/case.py` — added `ni_number` column and `actions` relationship
- `app/repositories/case_action_repository.py` — CRUD + `delete_by_case_id()`
- `app/services/case_service.py` — `update_category()` extended, `get_actions_for_case()`, `update_actions()`
- `app/views/cases.py` — `GET/POST /cases/<id>/actions`
- `app/templates/cases/detail.html` — category dropdown, actions panel, NI panel
