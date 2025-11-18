# app/email/routes/compose.py
from __future__ import annotations
import time
import email.utils
from email.message import EmailMessage
from flask import request, render_template, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.account import build_runtime_cfg
from app.email.services.connection import open_smtp, open_imap
from app.email.services.folders.specials import resolve_specials
from app.email.services.mail_ops import append_sent_copy, append_draft
from app.email.routes._helpers import _is_spa_request

IDEMP_TTL_SECONDS = 120  # window to ignore duplicate send of same Message-ID


def _get_first_account():
    return EmailConnection.query.filter_by(user_id=current_user.id).first()


def _split_addrs(s: str) -> list[str]:
    return [p.strip() for p in (s or "").replace(";", ",").split(",") if p.strip()]


def _dedupe(seq: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in seq:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _build_message(account: EmailConnection, form) -> EmailMessage:
    from_addr = account.email_address
    display_name = (form.get("display_name") or account.display_name or "").strip()
    reply_to = (form.get("reply_to") or account.reply_to or "").strip()
    subject = (form.get("subject") or "").strip()
    body = form.get("body") or ""
    is_html = (form.get("is_html") == "1")

    msg = EmailMessage()
    msg["From"] = email.utils.formataddr((display_name, from_addr)) if display_name else from_addr

    to = _split_addrs(form.get("to"))
    cc = _split_addrs(form.get("cc"))
    bcc = _split_addrs(form.get("bcc"))

    if to:
        msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to

    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    # Generate an idempotent Message-ID so we can detect duplicates
    msg_id = email.utils.make_msgid()
    msg["Message-ID"] = msg_id

    if is_html:
        msg.set_content("This email contains HTML.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    # attachments
    for f in request.files.getlist("attachments"):
        if not f or not f.filename:
            continue
        data = f.read()
        ctype = f.mimetype or "application/octet-stream"
        maintype, _, subtype = ctype.partition("/")
        msg.add_attachment(
            data,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=f.filename,
        )
    return msg


def _already_sent_now_set(message_id: str) -> bool:
    """
    Check a short-lived idempotency cache in Flask session to prevent duplicate sends.
    Returns True if we've seen this Message-ID in the last TTL window.
    Otherwise records it and returns False.
    """
    if not message_id:
        return False
    now = int(time.time())
    store = session.get("email_sent_recent", {})
    # prune
    store = {k: v for k, v in store.items() if (now - v) <= IDEMP_TTL_SECONDS}
    if message_id in store:
        session["email_sent_recent"] = store
        session.modified = True
        return True
    store[message_id] = now
    session["email_sent_recent"] = store
    session.modified = True
    return False


@bp.route("/compose", methods=["GET", "POST"])
@login_required
def compose():
    acc_id = request.args.get("acc", type=int) or request.form.get("acc", type=int)
    account = (
        EmailConnection.query.filter_by(user_id=current_user.id, id=acc_id).first()
        if acc_id else _get_first_account()
    )
    if not account:
        msg = "No connected email account."
        if _is_spa_request():
            return render_template("email/compose.html", account=None, error=msg)
        flash(msg, "danger")
        return redirect(url_for("email.status"))

    if request.method == "GET":
        html = render_template("email/compose.html", account=account, error=None)
        return html if _is_spa_request() else render_template("dashboard.html", initial_panel=html)

    # POST (Send)
    to = _split_addrs(request.form.get("to"))
    if not to:
        err = "Recipient (To) is required."
        if _is_spa_request():
            return jsonify(ok=False, error=err), 400
        flash(err, "danger")
        return redirect(url_for("email.compose", acc=account.id))

    msg = _build_message(account, request.form)
    message_id = msg.get("Message-ID") or ""

    # 🔒 Idempotency guard — if this Message-ID was recently sent, skip sending again
    if _already_sent_now_set(message_id):
        # Just redirect as if it succeeded
        target = url_for("email.mailbox_folder", folder="Sent", acc=account.id)
        return (jsonify(ok=True, redirect=target)) if _is_spa_request() else redirect(target)

    # Deduplicate all recipient addresses for the SMTP call
    rcpts = _dedupe(to + _split_addrs(request.form.get("cc")) + _split_addrs(request.form.get("bcc")))
    if not rcpts:
        if _is_spa_request():
            return jsonify(ok=False, error="No valid recipients."), 400
        flash("No valid recipients.", "danger")
        return redirect(url_for("email.compose", acc=account.id))

    # Send via SMTP (single attempt)
    try:
        cfg = build_runtime_cfg(account)
        smtp = open_smtp(cfg)
        try:
            smtp.send_message(msg, from_addr=account.email_address, to_addrs=rcpts)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
    except Exception as e:
        # On failure, remove the idempotency mark so the user can retry
        store = session.get("email_sent_recent", {})
        if message_id in store:
            store.pop(message_id, None)
            session["email_sent_recent"] = store
            session.modified = True
        if _is_spa_request():
            return jsonify(ok=False, error=str(e)), 400
        flash(f"Send failed: {e}", "danger")
        return redirect(url_for("email.compose", acc=account.id))

    # Save a copy to Sent via IMAP APPEND (non-fatal if it fails)
    try:
        cfg = build_runtime_cfg(account)
        imap = open_imap(cfg)
        try:
            specials = resolve_specials(imap, account.provider or "")
            sent_box = specials.get("sent") or "Sent"
            ok, err = append_sent_copy(imap, sent_box, msg)
            # ignore errors, optionally log
            _ = (ok, err)
        finally:
            try:
                imap.logout()
            except Exception:
                pass
    except Exception:
        pass

    # PRG / SPA response
    target = url_for("email.mailbox_folder", folder="Sent", acc=account.id)
    return (jsonify(ok=True, redirect=target)) if _is_spa_request() else redirect(target)


@bp.post("/compose/autosave")
@login_required
def compose_autosave():
    """
    Body: FormData with fields: acc, draft_uid?, to, cc, bcc, subject, body, is_html, (files optional)
    Returns JSON: {ok, draft_uid?, error?}
    """
    acc_id = request.form.get("acc", type=int)
    if not acc_id:
        return jsonify(ok=False, error="Missing acc"), 400
    account = EmailConnection.query.filter_by(user_id=current_user.id, id=acc_id).first()
    if not account:
        return jsonify(ok=False, error="Account not found"), 404

    msg = _build_message(account, request.form)
    draft_uid = request.form.get("draft_uid") or None

    try:
        cfg = build_runtime_cfg(account)
        imap = open_imap(cfg)
        try:
            specials = resolve_specials(imap, account.provider or "")
            drafts_box = specials.get("drafts") or "Drafts"
            ok, new_uid, err = append_draft(imap, drafts_box, msg, draft_uid=draft_uid)
            if not ok:
                return jsonify(ok=False, error=err or "Autosave failed"), 400
            return jsonify(ok=True, draft_uid=new_uid or draft_uid)
        finally:
            try:
                imap.logout()
            except Exception:
                pass
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400
