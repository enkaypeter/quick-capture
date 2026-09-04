from functools import wraps

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.invite_service import InviteService
from app.services.login_throttle_service import LoginThrottleService
from app.services.mfa_service import MfaService
from app.views import auth_bp

auth_service = AuthService()
invite_service = InviteService()
mfa_service = MfaService()

# Session keys for the half-completed login that is waiting on a second factor.
PENDING_MFA_USER_ID = "_pending_mfa_user_id"
# Recovery codes are shown exactly once, on the page after enrolment.
PENDING_RECOVERY_CODES = "_pending_recovery_codes"


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if getattr(current_user, "role", None) != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _throttle() -> LoginThrottleService:
    return LoginThrottleService.from_config(current_app.config)


def _client_ip() -> str:
    """The caller's IP address.

    Behind a reverse proxy this is only correct if the proxy sets
    X-Forwarded-For and the app runs behind ProxyFix - see
    docs/operations/deployment.md. Getting it wrong makes the per-IP limit
    apply to the proxy rather than the caller, so the per-account limit is
    the one that must always hold.
    """
    return request.remote_addr or "unknown"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("cases.list_cases"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        throttle = _throttle()
        ip_address = _client_ip()

        decision = throttle.check(email, ip_address)
        if not decision.allowed:
            # The same message for a locked account and a throttled IP, so the
            # response does not confirm whether an address is registered.
            flash(
                "Too many failed attempts. Try again in "
                f"{decision.retry_after_minutes} minute(s).",
                category="error",
            )
            return render_template("auth/login.html"), 429

        user, error = auth_service.authenticate(email, password)
        if error:
            throttle.record_failure(email, ip_address)
            flash(error, category="error")
        else:
            throttle.record_success(email, ip_address)

            if user.mfa_enabled:
                # Hold the login until the second factor is presented. The
                # user is deliberately not logged in yet.
                session[PENDING_MFA_USER_ID] = user.id
                return redirect(url_for("auth.mfa_verify"))

            login_user(user)
            flash("Logged in successfully!", category="success")
            return redirect(url_for("cases.list_cases"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop(PENDING_MFA_USER_ID, None)
    session.pop(PENDING_RECOVERY_CODES, None)
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


# --- Multi-factor authentication (blocker 8) ----------------------------


@auth_bp.route("/mfa/setup", methods=["GET"])
@login_required
def mfa_setup():
    """Show the QR code and secret for enrolling an authenticator app."""
    if current_user.mfa_enabled:
        return redirect(url_for("auth.mfa_status"))

    enrolment = mfa_service.begin_enrolment(
        current_user, current_app.config["MFA_ISSUER"]
    )
    return render_template(
        "auth/mfa_setup.html",
        secret=enrolment.secret,
        provisioning_uri=enrolment.provisioning_uri,
        qr_svg=_qr_svg(enrolment.provisioning_uri),
        required=mfa_service.is_required_for(
            current_user, current_app.config["MFA_REQUIRED_ROLES"]
        ),
    )


@auth_bp.route("/mfa/setup", methods=["POST"])
@login_required
def mfa_confirm():
    """Activate MFA once the user proves the secret reached their app."""
    code = request.form.get("code", "")
    success, error, recovery_codes = mfa_service.confirm_enrolment(current_user, code)

    if not success:
        flash(error, category="error")
        return redirect(url_for("auth.mfa_setup"))

    session[PENDING_RECOVERY_CODES] = recovery_codes
    flash("Two-factor authentication is on.", category="success")
    return redirect(url_for("auth.mfa_recovery_codes"))


@auth_bp.route("/mfa/recovery-codes", methods=["GET"])
@login_required
def mfa_recovery_codes():
    """Show freshly issued recovery codes exactly once."""
    codes = session.pop(PENDING_RECOVERY_CODES, None)
    if not codes:
        return redirect(url_for("auth.mfa_status"))

    return render_template("auth/mfa_recovery_codes.html", codes=codes)


@auth_bp.route("/mfa/status", methods=["GET"])
@login_required
def mfa_status():
    return render_template(
        "auth/mfa_status.html",
        unused_codes=mfa_service.unused_recovery_code_count(current_user),
        required=mfa_service.is_required_for(
            current_user, current_app.config["MFA_REQUIRED_ROLES"]
        ),
    )


@auth_bp.route("/mfa/recovery-codes/regenerate", methods=["POST"])
@login_required
def mfa_regenerate_recovery_codes():
    if not current_user.mfa_enabled:
        abort(400)

    session[PENDING_RECOVERY_CODES] = mfa_service.regenerate_recovery_codes(
        current_user
    )
    flash("New recovery codes issued. The old ones no longer work.", category="success")
    return redirect(url_for("auth.mfa_recovery_codes"))


@auth_bp.route("/mfa/verify", methods=["GET", "POST"])
def mfa_verify():
    """Second step of login for a user with MFA enabled."""
    user_id = session.get(PENDING_MFA_USER_ID)
    if not user_id:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user or not user.mfa_enabled:
        session.pop(PENDING_MFA_USER_ID, None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        throttle = _throttle()
        ip_address = _client_ip()

        decision = throttle.check(user.email, ip_address)
        if not decision.allowed:
            flash(
                "Too many failed attempts. Try again in "
                f"{decision.retry_after_minutes} minute(s).",
                category="error",
            )
            return render_template("auth/mfa_verify.html"), 429

        success, error = mfa_service.verify(user, request.form.get("code", ""))
        if not success:
            # Second-factor failures count towards the same lockout as
            # password failures; a stolen password should not buy an
            # unlimited number of code guesses.
            throttle.record_failure(user.email, ip_address)
            flash(error, category="error")
        else:
            throttle.record_success(user.email, ip_address)
            session.pop(PENDING_MFA_USER_ID, None)
            login_user(user)
            flash("Logged in successfully!", category="success")
            return redirect(url_for("cases.list_cases"))

    return render_template("auth/mfa_verify.html")


def _qr_svg(provisioning_uri: str) -> str:
    """Render the otpauth URI as an inline SVG.

    Inline rather than an <img> so the secret never becomes a separately
    fetchable URL, and so no image host is needed under the CSP.
    """
    import io

    import qrcode
    import qrcode.image.svg

    image = qrcode.make(
        provisioning_uri, image_factory=qrcode.image.svg.SvgPathImage
    )
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()


# --- Invite codes -------------------------------------------------------


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


# --- Account administration ---------------------------------------------


@auth_bp.route("/users", methods=["GET"])
@admin_required
def users():
    """List accounts so an admin can see who has access and who is locked out."""
    return render_template(
        "auth/users.html",
        users=User.query.order_by(User.created_at.asc()).all(),
    )


@auth_bp.route("/users/<int:user_id>/unlock", methods=["POST"])
@admin_required
def unlock_user(user_id):
    """Clear a lockout so a worker who forgot their password can try again."""
    user = User.query.get_or_404(user_id)
    _throttle().unlock(user)
    flash(f"{user.email} unlocked.", category="success")
    return redirect(url_for("auth.users"))
