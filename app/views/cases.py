from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user

from app.services.case_service import CaseService
from app.views import cases_bp

case_service = CaseService()


@cases_bp.route("/")
def landing():
    """Public landing page."""
    if current_user.is_authenticated:
        return redirect(url_for("cases.list_cases"))
    return render_template("landing.html")


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


@cases_bp.route("/cases/<int:case_id>/notes", methods=["POST"])
@login_required
def add_note(case_id):
    """Add a new manual note to a case."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    content = request.form.get("content", "").strip()
    if not content:
        flash("Note content cannot be empty.", category="error")
    else:
        case_service.add_note(case_id=case.id, content=content)
        flash("Note added.", category="success")

    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/cases/<int:case_id>/notes/<int:note_id>/delete", methods=["POST"])
@login_required
def delete_note(case_id, note_id):
    """Delete a note from a case."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    if case_service.delete_note(note_id):
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

    note = case_service.mark_note_reviewed(note_id)
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

    case_service.delete_case(case)
    flash("Case deleted.", category="success")
    return redirect(url_for("cases.list_cases"))


@cases_bp.route("/cases/<int:case_id>/category", methods=["POST"])
@login_required
def update_category(case_id):
    """Update case category via AJAX."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json()
    category = data.get("category", "")

    updated_case, error = case_service.update_category(case, category)
    if error:
        return jsonify({"error": error}), 400

    return jsonify({"success": True, "category": updated_case.category})


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



@cases_bp.route("/location/convert", methods=["POST"])
@login_required
def convert_location():
    """Convert GPS coordinates to a What3Words address.

    Called via AJAX from the create case form after geolocation is obtained.
    Proxies the request to the What3Words API to keep the API key server-side.
    """
    import requests as http_requests
    from flask import current_app

    data = request.get_json()
    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng are required"}), 400

    api_key = current_app.config.get("W3W_API_KEY", "")
    if not api_key:
        return jsonify({"error": "What3Words API key not configured"}), 503

    try:
        response = http_requests.get(
            "https://api.what3words.com/v3/convert-to-3wa",
            params={"coordinates": f"{lat},{lng}", "key": api_key},
            timeout=10,
        )

        if response.status_code != 200:
            return jsonify({"error": "What3Words API request failed"}), 502

        result = response.json()
        words = result.get("words")

        if words:
            return jsonify({"words": words})
        else:
            error_msg = result.get("error", {}).get("message", "Unknown error")
            return jsonify({"error": error_msg}), 502

    except http_requests.Timeout:
        return jsonify({"error": "What3Words API timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500
