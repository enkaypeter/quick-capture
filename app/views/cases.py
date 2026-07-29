from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user

from app.services.case_service import CaseService
from app.views import cases_bp

case_service = CaseService()


@cases_bp.route("/")
def landing():
    """Public landing page."""
    return render_template("landing.html", is_authenticated=current_user.is_authenticated)


@cases_bp.route("/dashboard")
@login_required
def list_cases():
    """Dashboard view - list all cases for the current user."""
    cases = case_service.get_cases_for_user(current_user.id)
    return render_template("cases/list.html", cases=cases)


@cases_bp.route("/cases/new", methods=["GET", "POST"])
@login_required
def create_case():
    """Create a new case/interaction."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        location_w3w = request.form.get("location_w3w", "").strip()
        notes_content = request.form.get("notes", "").strip()
        category = request.form.get("category", "").strip()
        voice_transcript = request.form.get("voice_transcript", "").strip()

        # Parse location coordinates if provided
        location_lat = None
        location_lng = None
        lat_str = request.form.get("location_lat", "").strip()
        lng_str = request.form.get("location_lng", "").strip()
        if lat_str and lng_str:
            try:
                location_lat = float(lat_str)
                location_lng = float(lng_str)
            except ValueError:
                pass

        # Voice note file
        voice_note_file = request.files.get("voice_note")

        case, error = case_service.create_case(
            user_id=current_user.id,
            full_name=full_name or None,
            phone_number=phone_number or None,
            location_w3w=location_w3w or None,
            location_lat=location_lat,
            location_lng=location_lng,
            notes_content=notes_content or None,
            category=category or None,
            voice_note_file=voice_note_file,
            voice_transcript=voice_transcript or None,
        )

        if error:
            flash(error, category="error")
        else:
            flash("Case created successfully!", category="success")
            return redirect(url_for("cases.view_case", case_id=case.id))

    return render_template("cases/create.html")


@cases_bp.route("/cases/<int:case_id>")
@login_required
def view_case(case_id):
    """View a single case with all its notes."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    notes = case_service.get_notes_for_case(case_id)
    return render_template("cases/detail.html", case=case, notes=notes)


@cases_bp.route("/cases/<int:case_id>/edit", methods=["POST"])
@login_required
def edit_case(case_id):
    """Update editable case fields (full_name, phone_number) via AJAX."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()

    updated_case, error = case_service.update_case_fields(
        case=case,
        user_id=current_user.id,
        full_name=data.get("full_name"),
        phone_number=data.get("phone_number"),
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "full_name": updated_case.full_name or "",
        "phone_number": updated_case.phone_number or "",
    })


@cases_bp.route("/cases/<int:case_id>/notes/<int:note_id>/edit", methods=["POST"])
@login_required
def edit_note(case_id, note_id):
    """Update note content via AJAX."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()
    content = data.get("content", "").strip()

    note, error = case_service.update_note_content(
        note_id=note_id,
        content=content,
        user_id=current_user.id,
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({"success": True, "content": note.content})


@cases_bp.route("/cases/<int:case_id>/notes", methods=["POST"])
@login_required
def add_note(case_id):
    """Add a new note to a case — either manual or voice-transcribed, not both."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    content = request.form.get("content", "").strip()
    voice_transcript = request.form.get("voice_transcript", "").strip()

    if voice_transcript:
        # Voice transcript takes precedence — save as transcription note only
        from app.models.case_note import NoteSource
        case_service.add_note(
            case_id=case.id,
            content=f"<p>{voice_transcript}</p>",
            source=NoteSource.TRANSCRIPTION,
            user_id=current_user.id,
        )
        flash("Transcribed note added.", category="success")
    elif content and case_service._has_meaningful_content(content):
        # Manual note only when no transcript and content is meaningful
        case_service.add_note(case_id=case.id, content=content, user_id=current_user.id)
        flash("Note added.", category="success")
    else:
        flash("Note content cannot be empty.", category="error")

    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/cases/<int:case_id>/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(case_id, note_id):
    """Delete a note from a case."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    if case_service.delete_note(note_id, user_id=current_user.id):
        flash("Note deleted.", category="success")
    else:
        flash("Note not found.", category="error")

    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/cases/<int:case_id>/notes/<int:note_id>/review", methods=["POST"])
@login_required
def mark_reviewed(case_id, note_id):
    """Mark a transcribed note as reviewed."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    note = case_service.mark_note_reviewed(note_id, user_id=current_user.id)
    if note:
        return jsonify({"success": True})
    return jsonify({"error": "Note not found"}), 404


@cases_bp.route("/cases/<int:case_id>/delete", methods=["POST"])
@login_required
def delete_case(case_id):
    """Delete a case."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    case_service.delete_case(case, user_id=current_user.id)
    flash("Case deleted.", category="success")
    return redirect(url_for("cases.list_cases"))


@cases_bp.route("/cases/<int:case_id>/category", methods=["POST"])
@login_required
def update_category(case_id):
    """Update case category via AJAX.

    When switching to 'client', expects ni_number in the payload.
    """
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()
    category = data.get("category", "")
    ni_number = data.get("ni_number")

    updated_case, error = case_service.update_category(
        case, category, user_id=current_user.id, ni_number=ni_number
    )
    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "category": updated_case.category,
        "ni_number": updated_case.ni_number or "",
    })


@cases_bp.route("/cases/<int:case_id>/actions", methods=["GET"])
@login_required
def get_actions(case_id):
    """Get actions for a case (JSON API)."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    actions = case_service.get_actions_for_case(case_id)
    return jsonify({
        "actions": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "label": a.label,
                "completed": a.completed,
            }
            for a in actions
        ]
    })


@cases_bp.route("/cases/<int:case_id>/actions", methods=["POST"])
@login_required
def update_actions(case_id):
    """Update actions for a case (JSON API)."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()
    actions_data = data.get("actions", [])

    actions = case_service.update_actions(
        case_id=case.id,
        user_id=current_user.id,
        actions=actions_data,
    )

    return jsonify({
        "success": True,
        "actions": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "label": a.label,
                "completed": a.completed,
            }
            for a in actions
        ]
    })


@cases_bp.route("/cases/<int:case_id>/ni-number", methods=["POST"])
@login_required
def update_ni_number(case_id):
    """Update National Insurance number for a client case (JSON API)."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()
    ni_number = data.get("ni_number", "").strip()

    if not ni_number:
        return jsonify({"error": "NI number is required"}), 400

    updated_case, error = case_service.update_ni_number(
        case=case,
        ni_number=ni_number,
        user_id=current_user.id,
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({"success": True, "ni_number": updated_case.ni_number})


@cases_bp.route("/cases/<int:case_id>/audit", methods=["GET"])
@login_required
def audit_trail(case_id):
    """Get the audit trail for a case (JSON API)."""
    from app.services.audit_service import AuditService

    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    audit_service = AuditService()
    entries = audit_service.get_audit_trail(case_id)

    return jsonify({
        "entries": [
            {
                "id": entry.id,
                "action": entry.action,
                "field_name": entry.field_name,
                "old_value": entry.old_value,
                "new_value": entry.new_value,
                "timestamp": (entry.timestamp.isoformat() + "Z") if entry.timestamp else None,
                "user": entry.user.first_name if entry.user else "Unknown",
            }
            for entry in entries
        ]
    })


@cases_bp.route("/transcribe", methods=["POST"])
@login_required
def transcribe_audio():
    """Transcribe an uploaded audio file and return the text.

    Called via AJAX from the create case form after recording stops.
    Does not persist anything — just returns the transcript for preview.
    """
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return jsonify({"error": "No audio file provided"}), 400

    import tempfile
    import os
    from app.services.transcription_client import TranscriptionClient

    # Save to a temp file for the transcription client
    ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else "webm"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    try:
        audio_file.save(tmp.name)
        tmp.close()

        client = TranscriptionClient()
        transcript = client.transcribe(tmp.name)

        if transcript:
            return jsonify({"text": transcript})
        else:
            return jsonify({"error": "Transcription failed or returned empty"}), 502
    finally:
        os.unlink(tmp.name)



@cases_bp.route("/location/autosuggest", methods=["POST"])
@login_required
def autosuggest_location():
    """Return What3Words autosuggest results for a partial address.

    Called via AJAX as the user types a what3words address.
    Requires at least the first two words and first character of the third.
    """
    from app.services.w3w_service import W3WService

    data = request.get_json()
    input_text = data.get("input", "").strip()

    if not input_text:
        return jsonify({"error": "Input required"}), 400

    focus_lat = data.get("focus_lat")
    focus_lng = data.get("focus_lng")
    clip_to_country = data.get("clip_to_country")

    w3w = W3WService()
    suggestions, error = w3w.autosuggest(
        input_text=input_text,
        focus_lat=focus_lat,
        focus_lng=focus_lng,
        clip_to_country=clip_to_country,
    )

    if error:
        return jsonify({"error": error}), 502

    return jsonify({"suggestions": suggestions})
