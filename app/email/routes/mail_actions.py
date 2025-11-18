# app/email/routes/mail_actions.py
from __future__ import annotations
from flask import request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user

from app.email import bp
from app.email.models.connection import EmailConnection
from app.email.services.account import build_runtime_cfg
from app.email.services.connection import open_imap
from app.email.services.mail_ops import move_to_mailbox
from app.email.services.folders.specials import resolve_specials
from app.email.routes._helpers import _is_spa_request

def _get_account(acc_id: int | None):
    if not acc_id:
        return None
    return EmailConnection.query.filter_by(user_id=current_user.id, id=acc_id).first()

def _do_move(to_label: str):
    """
    Common handler that moves a message to a special folder:
    to_label ∈ {"trash","spam","archive"}
    """
    acc_id = request.form.get("acc", type=int)
    folder = request.form.get("folder") or "INBOX"
    uid = request.form.get("uid")

    if not acc_id or not uid:
        msg = "Missing acc or uid."
        if _is_spa_request():
            return jsonify(ok=False, error=msg), 400
        flash(msg, "danger")
        return redirect(url_for("email.mailbox_folder", folder=folder, acc=acc_id or ""))

    account = _get_account(acc_id)
    if not account:
        msg = "Account not found."
        if _is_spa_request():
            return jsonify(ok=False, error=msg), 404
        flash(msg, "danger")
        return redirect(url_for("email.mailbox_folder", folder=folder, acc=acc_id))

    try:
        cfg = build_runtime_cfg(account)
        imap = open_imap(cfg)
        try:
            specials = resolve_specials(imap, account.provider or "")
            targets = {
                "trash": specials.get("trash") or "Trash",
                "spam": specials.get("spam") or "Spam",
                "archive": specials.get("archive") or "Archive",
            }
            to_mailbox = targets[to_label]
            ok, err = move_to_mailbox(imap, folder, uid, to_mailbox)
            if not ok:
                if _is_spa_request():
                    return jsonify(ok=False, error=err or f"Move to {to_label} failed"), 400
                flash(err or f"Move to {to_label} failed", "danger")
                return redirect(url_for("email.mailbox_folder", folder=folder, acc=account.id))

            # Success: answer JSON for SPA, redirect for non-SPA
            if _is_spa_request():
                return jsonify(ok=True, to=to_mailbox)
            else:
                flash(f"Moved to {to_label.title()}.", "success")
                return redirect(url_for("email.mailbox_folder", folder=to_mailbox, acc=account.id))
        finally:
            try: imap.logout()
            except Exception: pass
    except Exception as e:
        if _is_spa_request():
            return jsonify(ok=False, error=str(e)), 400
        flash(str(e), "danger")
        return redirect(url_for("email.mailbox_folder", folder=folder, acc=acc_id))

@bp.post("/mail/action/delete")
@login_required
def mail_action_delete():
    return _do_move("trash")

@bp.post("/mail/action/spam")
@login_required
def mail_action_spam():
    return _do_move("spam")

@bp.post("/mail/action/archive")
@login_required
def mail_action_archive():
    return _do_move("archive")
