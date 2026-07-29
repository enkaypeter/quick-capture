# ADR-001: What3Words Integration (Free Plan AutoSuggest)

## Status

Accepted

## Date

2026-07-29

## Context

Social workers need to record the location of interactions with prospects. What3Words provides a human-friendly addressing system that divides the world into 3m squares, each identified by three words (e.g. `///filled.count.soap`). This is easier to communicate verbally than GPS coordinates, which is important for field workers.

We evaluated the What3Words API and found that the **Free plan** only provides access to:

- **AutoSuggest** — typeahead/autocomplete for partial what3words addresses
- **Available Languages** — list of supported languages

The paid Business plan (from ~£3.50/month) would additionally unlock:

- `convert-to-3wa` — GPS coordinates → what3words address
- `convert-to-coordinates` — what3words address → GPS coordinates

## Decision

We will use the **What3Words Free plan** with AutoSuggest only. The integration provides:

1. **Manual w3w address entry with autocomplete** — as the user types a what3words address (minimum `word.word.c`), the backend proxies requests to the AutoSuggest API and returns suggestions with nearest place information.

2. **GPS capture via browser Geolocation API** — the "Share my location" button captures raw lat/lng coordinates directly without converting to a what3words address.

3. **Backend proxy pattern** — all API calls go through `POST /location/autosuggest` to keep the API key server-side. The client never sees the key.

4. **UK-focused suggestions** — results are clipped to `GB` by default since Simon on the Streets operates in the UK. GPS focus is passed when available for relevance weighting.

## Consequences

- Users **cannot** tap "Share my location" and automatically get a what3words address. They get GPS coordinates stored separately.
- Users **can** type a what3words address if they know one (e.g. told verbally by a prospect or read from the what3words app).
- The identifier generation system uses the first word of the what3words address when available, falling back to `UNK` when only GPS coordinates exist.
- If the project later upgrades to a Business plan, the `W3WService` can be extended with `convert_to_3wa` and `convert_to_coordinates` methods to enable the full GPS → w3w flow.

## Technical Details

### Files

- `app/services/w3w_service.py` — W3WService class with `autosuggest()` method
- `app/views/cases.py` — `POST /location/autosuggest` route
- `app/static/js/app.js` — debounced input handler, dropdown rendering, keyboard nav
- `app/templates/cases/create.html` — editable location input with `///` prefix and dropdown

### Configuration

- `W3W_API_KEY` environment variable (loaded via `.env` in Docker Compose)
- `config.py` reads it as `Config.W3W_API_KEY`

### API Rate Limits (Free Plan)

- AutoSuggest: 10 requests/second
- No access to convert endpoints
