# app/auth/routes.py
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from . import bp                 # use the Blueprint defined in app/auth/__init__.py
from app.models import User
from app.permissions import is_admin_like, effective_codes


def _is_safe_next(nxt: str | None) -> bool:
    """Allow only safe local redirects (relative paths, not protocol-relative)."""
    if not nxt:
        return False
    return nxt.startswith("/") and not nxt.startswith("//")


@bp.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in → redirect to dashboard (or safe 'next')
    if current_user.is_authenticated:
        nxt = request.args.get("next")
        return redirect(nxt) if _is_safe_next(nxt) else redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()

        # Invalid credentials
        if not user or not user.check_password(password):
            flash("Invalid email or password", "error")
            return render_template("login.html", email=email)

        # Suspended account
        if getattr(user, "is_suspended", False):
            flash("Вашата сметка е суспендирана. Контактирајте администратор.", "error")
            return render_template("login.html", email=email), 403

        # Successful login
        login_user(user, remember=remember)
        nxt = request.args.get("next")
        return redirect(nxt) if _is_safe_next(nxt) else redirect(url_for("feed_api.panel"))


    # GET → render login page
    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/whoami", methods=["GET"])
@login_required
def whoami():
    u = current_user
    codes = sorted([c for c in effective_codes(u) if c != "*admin*"])
    return jsonify({
        "id": u.id,
        "email": u.email,
        "role_name": getattr(getattr(u, "role", None), "name", None),
        "admin_like": is_admin_like(u),
        "codes": codes,
    })
