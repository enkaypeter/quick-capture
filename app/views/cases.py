import csv
from io import StringIO

from flask import Response, render_template, request, flash, redirect, url_for, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user

from app.models.case_interaction import InteractionTagType
from app.services.access_log_service import AccessAction, AccessLogService
from app.services.case_service import CaseService
from app.services.retention_service import REASON_ERASURE_REQUEST, RetentionService
from app.views import cases_bp
from app.views.auth import admin_required

case_service = CaseService()


def _record_access(action, case_id=None, resource=None):
    """Record that the signed-in user read something (blocker 10).

    Access logging must never stop a worker from reading a case, so failures
    here are swallowed rather than surfaced. A dropped log line is bad; a
    frontline worker blocked from a risk assessment is worse.
    """
    try:
        AccessLogService.from_config(current_app.config).record(
            user_id=current_user.id,
            action=action,
            case_id=case_id,
            resource=resource,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )
    except Exception:  # pragma: no cover - defensive
        current_app.logger.exception("Failed to record access log entry")


@cases_bp.route("/")
def landing():
    """Public landing page."""
    return render_template("landing.html", is_authenticated=current_user.is_authenticated)


@cases_bp.route("/service-worker.js")
def service_worker():
    return send_from_directory(
        current_app.static_folder,
        "js/service-worker.js",
        mimetype="application/javascript",
    )


@cases_bp.route("/dashboard")
@login_required
def list_cases():
    """Dashboard view - list all active team-visible cases."""
    query = request.args.get("q", "").strip()
    if query:
        # The search term itself is not stored: it is often a person's name,
        # and the access log should not become a second copy of case data.
        _record_access(AccessAction.SEARCHED)
    cases = case_service.search_cases(query) if query else case_service.get_cases_for_user(current_user.id)
    follow_ups = case_service.get_upcoming_follow_ups()
    return render_template("cases/list.html", cases=cases, query=query, follow_ups=follow_ups)


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
        date_of_birth = request.form.get("date_of_birth", "").strip()
        age_str = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        physical_description = request.form.get("physical_description", "").strip()
        other_contact = request.form.get("other_contact", "").strip()
        consent_status = request.form.get("consent_status", "unknown").strip()
        consent_date = request.form.get("consent_date", "").strip()
        risk_rating = request.form.get("risk_rating", "unknown").strip()
        risk_notes = request.form.get("risk_notes", "").strip()
        mental_health_notes = request.form.get("mental_health_notes", "").strip()
        current_situation = request.form.get("current_situation", "").strip()

        age = None
        if age_str:
            try:
                age = int(age_str)
            except ValueError:
                flash("Age must be a number.", category="error")
                return render_template("cases/create.html")

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
            date_of_birth=date_of_birth or None,
            age=age,
            gender=gender or None,
            physical_description=physical_description or None,
            other_contact=other_contact or None,
            consent_status=consent_status or None,
            consent_date=consent_date or None,
            risk_rating=risk_rating or None,
            risk_notes=risk_notes or None,
            mental_health_notes=mental_health_notes or None,
            current_situation=current_situation or None,
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
    if not case or case.archived_at:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    _record_access(AccessAction.VIEWED_CASE, case_id=case.id)

    notes = case_service.get_notes_for_case(case_id)
    interactions = case_service.get_interactions_for_case(case_id)
    follow_ups = case_service.get_follow_ups_for_case(case_id)
    attachments = case_service.get_attachments_for_case(case_id)
    return render_template(
        "cases/detail.html",
        case=case,
        notes=notes,
        interactions=interactions,
        follow_ups=follow_ups,
        attachments=attachments,
        tag_labels=InteractionTagType.LABELS,
    )


@cases_bp.route("/cases/<int:case_id>/edit", methods=["POST"])
@login_required
def edit_case(case_id):
    """Update editable case fields via AJAX."""
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json() or {}

    updated_case, error = case_service.update_case_fields(
        case=case,
        user_id=current_user.id,
        full_name=data.get("full_name"),
        phone_number=data.get("phone_number"),
        ni_number=data.get("ni_number"),
        date_of_birth=data.get("date_of_birth"),
        age=data.get("age"),
        gender=data.get("gender"),
        physical_description=data.get("physical_description"),
        other_contact=data.get("other_contact"),
        consent_status=data.get("consent_status"),
        consent_date=data.get("consent_date"),
        risk_rating=data.get("risk_rating"),
        risk_notes=data.get("risk_notes"),
        mental_health_notes=data.get("mental_health_notes"),
        current_situation=data.get("current_situation"),
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "full_name": updated_case.full_name or "",
        "phone_number": updated_case.phone_number or "",
        "ni_number": updated_case.ni_number or "",
        "date_of_birth": updated_case.date_of_birth or "",
        "age": updated_case.age or "",
        "gender": updated_case.gender or "",
        "physical_description": updated_case.physical_description or "",
        "other_contact": updated_case.other_contact or "",
        "consent_status": updated_case.consent_status or "unknown",
        "consent_date": updated_case.consent_date or "",
        "risk_rating": updated_case.risk_rating or "unknown",
        "risk_notes": updated_case.risk_notes or "",
        "mental_health_notes": updated_case.mental_health_notes or "",
        "current_situation": updated_case.current_situation or "",
    })


@cases_bp.route("/cases/<int:case_id>/notes/<int:note_id>/edit", methods=["POST"])
@login_required
def edit_note(case_id, note_id):
    """Update note content via AJAX."""
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json() or {}
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
    if not case or case.archived_at:
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
    if not case or case.archived_at:
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
    if not case or case.archived_at:
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
    if not case or case.archived_at:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    case_service.delete_case(case, user_id=current_user.id)
    flash("Case archived.", category="success")
    return redirect(url_for("cases.list_cases"))


@cases_bp.route("/cases/<int:case_id>/category", methods=["POST"])
@login_required
def update_category(case_id):
    """Update case category via AJAX.

    When switching to 'client', expects ni_number in the payload.
    """
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json() or {}
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
    if not case or case.archived_at:
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
    if not case or case.archived_at:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json() or {}
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
    if not case or case.archived_at:
        return jsonify({"error": "Case not found"}), 404

    data = request.get_json() or {}
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
    if not case or case.archived_at:
        return jsonify({"error": "Case not found"}), 404

    _record_access(AccessAction.VIEWED_AUDIT_TRAIL, case_id=case.id)

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


@cases_bp.route("/cases/<int:case_id>/interactions", methods=["POST"])
@login_required
def add_interaction(case_id):
    """Add a timestamped, reportable interaction to a case."""
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    tag_types = request.form.getlist("tags")
    note_content = request.form.get("interaction_note", "").strip()
    outcome = request.form.get("outcome", "").strip()
    location_w3w = request.form.get("interaction_location_w3w", "").strip()
    lat_str = request.form.get("interaction_location_lat", "").strip()
    lng_str = request.form.get("interaction_location_lng", "").strip()

    location_lat = None
    location_lng = None
    if lat_str and lng_str:
        try:
            location_lat = float(lat_str)
            location_lng = float(lng_str)
        except ValueError:
            flash("Location coordinates were ignored because they were invalid.", category="error")

    interaction, error = case_service.add_interaction(
        case_id=case.id,
        user_id=current_user.id,
        note_content=note_content,
        tag_types=tag_types,
        outcome=outcome or None,
        location_w3w=location_w3w or None,
        location_lat=location_lat,
        location_lng=location_lng,
    )

    attachment = request.files.get("interaction_attachment")
    if interaction and attachment and attachment.filename:
        _, attachment_error = case_service.add_attachment(
            case_id=case.id,
            user_id=current_user.id,
            file=attachment,
            interaction_id=interaction.id,
        )
        if attachment_error:
            flash(attachment_error, category="error")

    if error:
        flash(error, category="error")
    else:
        flash("Interaction saved.", category="success")
    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/cases/<int:case_id>/follow-ups", methods=["POST"])
@login_required
def add_follow_up(case_id):
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    _, error = case_service.add_follow_up_task(
        case_id=case.id,
        user_id=current_user.id,
        title=request.form.get("title", ""),
        due_date=request.form.get("due_date", ""),
    )
    flash(error or "Follow-up added.", category="error" if error else "success")
    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/cases/<int:case_id>/follow-ups/<int:task_id>/complete", methods=["POST"])
@login_required
def complete_follow_up(case_id, task_id):
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    _, error = case_service.complete_follow_up_task(task_id=task_id, user_id=current_user.id)
    flash(error or "Follow-up completed.", category="error" if error else "success")
    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/cases/<int:case_id>/attachments", methods=["POST"])
@login_required
def add_attachment(case_id):
    case = case_service.get_case(case_id)
    if not case or case.archived_at:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    _, error = case_service.add_attachment(
        case_id=case.id,
        user_id=current_user.id,
        file=request.files.get("attachment"),
    )
    flash(error or "Attachment uploaded.", category="error" if error else "success")
    return redirect(url_for("cases.view_case", case_id=case_id))


@cases_bp.route("/attachments/<int:attachment_id>")
@login_required
def download_attachment(attachment_id):
    from app.models.case_attachment import CaseAttachment

    attachment = CaseAttachment.query.get_or_404(attachment_id)
    case = case_service.get_case(attachment.case_id)
    if not case or case.archived_at:
        flash("Attachment not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    _record_access(
        AccessAction.DOWNLOADED_ATTACHMENT,
        case_id=case.id,
        resource=f"attachment:{attachment.id}",
    )

    directory = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(
        directory,
        attachment.stored_path,
        as_attachment=True,
        download_name=attachment.original_filename,
    )


@cases_bp.route("/reports")
@login_required
def reports():
    return render_template("cases/reports.html", summary=case_service.reporting_summary())


@cases_bp.route("/reports/export.csv")
@login_required
def reports_export():
    # An export lifts every active case out of the system in one file, which
    # makes it the single most sensitive read in the app.
    _record_access(AccessAction.EXPORTED_REPORT)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["case_identifier", "case_name", "interaction_date", "worker", "tags", "outcome", "risk_rating", "current_situation"])

    from app.models.case_interaction import CaseInteraction

    interactions = CaseInteraction.query.order_by(CaseInteraction.occurred_at.desc()).all()
    for interaction in interactions:
        case = interaction.case
        if case.archived_at:
            continue
        writer.writerow([
            case.identifier,
            case.full_name or "",
            interaction.occurred_at.isoformat() if interaction.occurred_at else "",
            interaction.worker.first_name if interaction.worker else "",
            "; ".join(tag.label for tag in interaction.tags),
            interaction.outcome or "",
            case.risk_rating or "unknown",
            case.current_situation or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sots-report.csv"},
    )


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

    data = request.get_json() or {}
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


# --- Permanent erasure and access history (blockers 10 and 11) ----------


@cases_bp.route("/cases/<int:case_id>/access-log", methods=["GET"])
@login_required
def case_access_log(case_id):
    """Who has read this case (JSON API).

    Visible to every signed-in worker, not just admins: openness about who is
    reading a record is part of what makes team-wide visibility acceptable.
    """
    case = case_service.get_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    entries = AccessLogService.from_config(current_app.config).get_for_case(case_id)

    return jsonify({
        "entries": [
            {
                "id": entry.id,
                "action": entry.action,
                "resource": entry.resource,
                "user": entry.user.first_name if entry.user else "Unknown",
                "timestamp": (
                    entry.created_at.isoformat() + "Z" if entry.created_at else None
                ),
            }
            for entry in entries
        ]
    })


@cases_bp.route("/cases/<int:case_id>/purge", methods=["POST"])
@admin_required
def purge_case(case_id):
    """Permanently erase a case, its files and its logs.

    Admin-only and irreversible. Archiving (the normal delete) remains the
    default; this exists so an Article 17 erasure request can actually be
    satisfied. The confirmation requires typing the case identifier, because
    an accidental click here destroys a record with no undo.
    """
    case = case_service.get_case(case_id)
    if not case:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))

    confirmation = request.form.get("confirm_identifier", "").strip()
    if confirmation != case.identifier:
        flash(
            f"Type the case identifier ({case.identifier}) to confirm permanent "
            "erasure.",
            category="error",
        )
        return redirect(url_for("cases.view_case", case_id=case_id))

    reason = request.form.get("reason", "").strip() or REASON_ERASURE_REQUEST
    result = RetentionService(current_app.config["UPLOAD_FOLDER"]).purge_case(
        case, reason=reason, requested_by_user_id=current_user.id
    )

    flash(
        f"Case {result.case_identifier} permanently erased "
        f"({result.records_deleted} record(s), {result.files_deleted} file(s)).",
        category="success",
    )
    return redirect(url_for("cases.list_cases"))


@cases_bp.route("/erasure-log", methods=["GET"])
@admin_required
def erasure_log():
    """The record of what has been permanently erased and why."""
    service = RetentionService(current_app.config["UPLOAD_FOLDER"])
    return render_template("cases/erasure_log.html", entries=service.get_erasure_log())
