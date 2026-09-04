from functools import wraps

from flask import abort, current_app, render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user

from app.services.auth_service import AuthService
from app.services.invite_service import InviteService
from app.views import auth_bp

auth_service = AuthService()
invite_service = InviteService()


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if getattr(current_user, "role", None) != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("cases.list_cases"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user, error = auth_service.authenticate(email, password)
        if error:
            flash(error, category="error")
        else:
            login_user(user)
            flash("Logged in successfully!", category="success")
            return redirect(url_for("cases.list_cases"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/sign-up", methods=["GET", "POST"])
def sign_up():
    if current_user.is_authenticated:
        return redirect(url_for("cases.list_cases"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        first_name = request.form.get("firstName", "").strip()
        password1 = request.form.get("password1", "")
        password2 = request.form.get("password2", "")
        invite_code = request.form.get("invite_code", "").strip()

        if password1 != password2:
            flash("Passwords don't match.", category="error")
        else:
            user, error = auth_service.register_user(
                email,
                first_name,
                password1,
                invite_code,
                expected_invite_code=current_app.config["SIGNUP_INVITE_CODE"],
                bootstrap_invite_enabled=current_app.config["BOOTSTRAP_INVITE_ENABLED"],
            )
            if error:
                flash(error, category="error")
            else:
                login_user(user)
                flash("Welcome to QuickCapture!", category="success")
                return redirect(url_for("cases.list_cases"))

    return render_template("auth/sign_up.html")


@auth_bp.route("/invite-codes", methods=["GET"])
@admin_required
def invite_codes():
    return render_template(
        "auth/invite_codes.html",
        invite_codes=invite_service.list_codes(),
    )


@auth_bp.route("/invite-codes", methods=["POST"])
@admin_required
def create_invite_code():
    label = request.form.get("label", "").strip()
    max_uses = request.form.get("max_uses", "1").strip()
    invite = invite_service.create_code(current_user.id, label, max_uses)
    flash(f"Invite code created: {invite.code}", category="success")
    return redirect(url_for("auth.invite_codes"))


@auth_bp.route("/invite-codes/<int:invite_id>/deny", methods=["POST"])
@admin_required
def deny_invite_code(invite_id):
    _, error = invite_service.deny_code(invite_id)
    if error:
        flash(error, category="error")
    else:
        flash("Invite code denied.", category="success")
    return redirect(url_for("auth.invite_codes"))
