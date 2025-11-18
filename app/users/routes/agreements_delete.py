# app/users/routes/agreements_delete.py
from __future__ import annotations
import os

from flask import jsonify, abort, current_app
from flask_login import login_required, current_user

from .. import bp
from ...extensions import db
from ...models import Agreement, Attachment
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT

def _agreements_dir() -> str:
    base = current_app.config.get("AGREEMENTS_UPLOAD_DIR")
    if not base:
        base = os.path.join(current_app.instance_path, "agreements")
    os.makedirs(base, exist_ok=True)
    return base

def _attachments_sorted_for_agreement(a: Agreement):
    """
    Return attachments sorted newest-first and support both:
      - dynamic relationship (has .order_by)
      - list-like relationship (InstrumentedList)
    """
    try:
        rel = a.attachments
        if hasattr(rel, "order_by"):  # lazy="dynamic"
            return rel.order_by(Attachment.uploaded_at.desc()).all()
        # list-like: sort manually (uploaded_at can be None)
        return sorted(
            rel or [],
            key=lambda x: (x.uploaded_at is None, x.uploaded_at),  # None last
            reverse=True,
        )
    except Exception:
        return []

@bp.route("/api/agreements/<int:user_id>/<int:agreement_id>/delete", methods=["POST"])
@login_required
@require_permission(USERS_AGREEMENT)
def api_agreements_delete(user_id: int, agreement_id: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        abort(403)

    a = Agreement.query.filter_by(id=agreement_id, user_id=user_id).first_or_404()

    # delete files from disk (best-effort), then DB rows
    base = _agreements_dir()
    for att in _attachments_sorted_for_agreement(a):
        try:
            safe_name = os.path.basename(att.stored_name or "")
            if safe_name:
                path = os.path.join(base, safe_name)
                if os.path.isfile(path):
                    os.remove(path)
        except Exception:
            pass
        try:
            db.session.delete(att)
        except Exception:
            pass

    try:
        db.session.delete(a)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete agreement"}), 400

    return jsonify({"ok": True})
