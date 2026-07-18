from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user

from app.services.case_service import CaseService
from app.views import cases_bp

case_service = CaseService()


@cases_bp.route("/")
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
        notes = request.form.get("notes", "").strip()
        category = request.form.get("category", "").strip()

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
            notes=notes or None,
            category=category or None,
            voice_note_file=voice_note_file,
        )

        if error:
            flash(error, category="error")
        else:
            flash("Case created successfully!", category="success")
            return redirect(url_for("cases.list_cases"))

    return render_template("cases/create.html")


@cases_bp.route("/cases/<int:case_id>")
@login_required
def view_case(case_id):
    """View a single case."""
    case = case_service.get_case(case_id)
    if not case or case.user_id != current_user.id:
        flash("Case not found.", category="error")
        return redirect(url_for("cases.list_cases"))
    return render_template("cases/detail.html", case=case)


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
