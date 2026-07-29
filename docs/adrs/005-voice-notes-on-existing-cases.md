# ADR-005: Voice Notes on Existing Cases

## Status

Accepted

## Date

2026-07-29

## Context

The original implementation only allowed voice recording during case creation. Social workers frequently need to add follow-up voice notes to existing cases — recording observations after a visit, capturing a quick update while on the go, or noting something a prospect said.

The existing transcription infrastructure (whisper.cpp via the `/transcribe` endpoint) is already in place and works well for the create flow. We need to extend the same capability to the "Add a note" section on the case detail page.

## Decision

We will add an **optional voice recorder** to the "Add a note" section on the case detail page, using the same pattern as the create case form:

### Flow

1. Worker clicks **Record** → browser requests microphone access → recording starts
2. Worker clicks **Stop** → recording ends, playback appears, audio blob is sent to `/transcribe`
3. Transcription service returns text → shown inline as a preview
4. Worker can **Copy to notes** to paste the transcript into the Quill editor for editing
5. On form submit:
   - The manual note (from Quill) is saved as a `manual` source note
   - The voice transcript (from hidden field) is saved as a separate `transcription` source note with `needs_review=True`

### Key design choices

- **Transcript stored as a separate note** — not merged into the manual note. This preserves the source distinction and the review workflow.
- **No audio file persistence on existing cases** — unlike case creation where the audio is saved to disk, follow-up recordings are transcribe-only. The raw audio is not saved. This keeps storage manageable and the transcript serves as the record.
- **Same `/transcribe` endpoint** — no new backend route needed. The existing endpoint accepts a blob and returns text.
- **Independent submission** — a worker can add just a text note (no recording), just a recording (transcript becomes the note), or both.

## Consequences

- The add-note form now uses `enctype="multipart/form-data"` (though we only submit the transcript text, not the raw file)
- A voice-only note submission (no manual text, only transcript) is valid and creates a transcription note
- The `add_note` route now checks for both `content` and `voice_transcript` form fields
- Follow-up voice transcripts are flagged `needs_review=True` and can be marked as reviewed by the worker
- Audio is not persisted — if the transcription service is down, the recording is lost. The worker sees an error and can try again.

## Technical Details

### Modified Files

- `app/templates/cases/detail.html` — voice recorder UI in the add-note section (record button, playback, transcription preview, copy-to-notes button)
- `app/views/cases.py` — `add_note()` route now accepts `voice_transcript` field and creates a transcription-source note

### UI Components

- Record/Stop/Re-record button with visual state (red pulse during recording)
- Audio playback element
- Transcription loading spinner
- Transcript text preview with "Copy to notes" button
- Error display for transcription failures

### Form Fields

- `content` — HTML from Quill editor (manual note)
- `voice_transcript` — plain text from transcription service (creates a separate note)
