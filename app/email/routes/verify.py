# app/email/routes/verify.py
from datetime import datetime

from flask import render_template, redirect, url_for, session, flash, request
from flask_login import login_required, current_user

from app.email import bp
from app.email.forms.verify_form import VerifyForm
from app.email.services.verification import test_connection
from app.email.utils.encryption import encrypt_secret
from app.email.utils.logging import log_event
from app.email.models.connection import EmailConnection
from app.extensions import db


def _is_spa_request() -> bool:
    return (
        request.headers.get("X-Requested-With") in {"fetch", "XMLHttpRequest"}
        or request.headers.get("HX-Request") == "true"
    )


@bp.route("/verify", methods=["GET", "POST"])
@login_required
def verify_connection():
    """
    Step 4: verify the connection (incoming + outgoing).
    On success: save/update EmailConnection record for this user.
    """
    form = VerifyForm()

    cfg = session.get("email_config")
    provider = session.get("email_provider", "custom")
    mode = session.get("email_protocol", "imap")

    if not cfg:
        flash("Missing configuration. Please start again.", "warning")
        return redirect(url_for("email.provider_select"))

    # Ensure expected keys exist (avoid KeyErrors later)
    cfg.setdefault("incoming_security", "ssl")
    cfg.setdefault("outgoing_security", "ssl")
    cfg.setdefault("sync_window_days", 30)
    cfg.setdefault("use_idle", True)

    test_result = None

    if form.validate_on_submit():
        # 1) Run verification
        # augment cfg with protocol for the verifier
        cfg_for_test = dict(cfg)
        cfg_for_test["protocol"] = mode
        test_result = test_connection(cfg_for_test)

        if test_result.get("success"):
            # 2) Persist to DB (create or update)
            email_addr = cfg.get("email_address")

            # certificate policy
            if cfg.get("allow_self_signed"):
                cert_policy = "allow_self_signed"
            elif cfg.get("incoming_security") == "none" or cfg.get("outgoing_security") == "none":
                cert_policy = "none"
            else:
                cert_policy = "strict"

            secret_ref = encrypt_secret(cfg.get("password", "") or "")

            # Try to find existing connection for this user + email
            conn = (
                EmailConnection.query
                .filter_by(user_id=current_user.id, email_address=email_addr)
                .first()
            )

            if not conn:
                conn = EmailConnection(
                    user_id=current_user.id,
                    email_address=email_addr,
                    created_at=datetime.utcnow(),
                )
                db.session.add(conn)

            # Update all fields
            conn.provider = provider
            conn.mode = mode
            conn.display_name = cfg.get("display_name") or None
            conn.reply_to = cfg.get("reply_to") or None

            conn.incoming_host = cfg.get("incoming_host") or None
            conn.incoming_port = int(cfg.get("incoming_port") or 0) or None
            conn.incoming_security = (cfg.get("incoming_security") or "ssl").lower()

            conn.outgoing_host = cfg.get("outgoing_host") or None
            conn.outgoing_port = int(cfg.get("outgoing_port") or 0) or None
            conn.outgoing_security = (cfg.get("outgoing_security") or "ssl").lower()
            conn.outgoing_auth_custom = bool(cfg.get("outgoing_auth_custom"))

            conn.certificate_policy = cert_policy
            conn.secret_ref = secret_ref

            conn.use_idle = bool(cfg.get("use_idle"))
            try:
                conn.sync_window_days = int(cfg.get("sync_window_days") or 30)
            except Exception:
                conn.sync_window_days = 30

            conn.status = "connected"
            conn.last_verified_at = datetime.utcnow()

            db.session.commit()

            # 3) Log success
            try:
                log_event(conn.id, "verify_success", "Incoming and outgoing OK")
            except Exception:
                pass

            flash("✅ Email account connected successfully!", "success")
            # Optional: clean up session for next time
            # session.pop("email_config", None)

            return redirect(url_for("email.status_list"))
        else:
            # Log failure (no DB record to attach unless it already exists)
            email_addr = cfg.get("email_address") or ""
            existing = (
                EmailConnection.query
                .filter_by(user_id=current_user.id, email_address=email_addr)
                .first()
            )
            try:
                if existing:
                    log_event(existing.id, "verify_fail", test_result.get("error") or "Unknown error")
            except Exception:
                pass

            flash(f"❌ Connection failed: {test_result.get('error')}", "danger")

    # First load or failed submit → render panel
    panel_html = render_template("email/verify.html", form=form, user=current_user, result=test_result)
    if _is_spa_request():
        return panel_html
    return render_template("dashboard.html", initial_panel=panel_html)
