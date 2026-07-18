from flask import render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user

from app.services.auth_service import AuthService
from app.views import auth_bp

auth_service = AuthService()


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
            login_user(user, remember=True)
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

        if password1 != password2:
            flash("Passwords don't match.", category="error")
        else:
            user, error = auth_service.register_user(email, first_name, password1)
            if error:
                flash(error, category="error")
            else:
                flash("Account created!", category="success")
                return redirect(url_for("auth.login"))

    return render_template("auth/sign_up.html")
