from flask_login import login_required
from flask import jsonify, request, current_app
import os, uuid
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import User, Attachment
from app.permissions import require_permission, USERS_CREATE_EDIT
from .. import bp
from .helpers import _collect_files_from_request, _filesize, _ensure_upload_dir

@bp.route("/api/attachments/<int:user_id>", methods=["POST"])
@login_required
@require_permission(USERS_CREATE_EDIT)
def upload_attachment(user_id: int):
    u = User.query.get_or_404(user_id)

    incoming = _collect_files_from_request()
    if not incoming:
        return jsonify({"errors": {"file": "Please choose a file."}}), 400

    unique_files, seen = [], set()
    for f in incoming:
        if not f or not f.filename:
            continue
        safe = secure_filename(f.filename)
        key = (safe, _filesize(f))
        if key in seen:
            continue
        seen.add(key)
        unique_files.append((f, safe))

    if not unique_files:
        return jsonify({"errors": {"file": "No new files to upload."}}), 400

    owners = {
        "agreement_id":      request.form.get("agreement_id"),
        "sick_leave_id":     request.form.get("sick_leave_id"),
        "vacation_id":       request.form.get("vacation_id"),
        "uniform_id":        request.form.get("uniform_id"),
        "training_id":       request.form.get("training_id"),
        "reward_penalty_id": request.form.get("reward_penalty_id"),
    }
    non_null = [(k, v) for k, v in owners.items() if v not in (None, "", "null")]
    if len(non_null) > 1:
        return jsonify({"errors": {"owner": "Provide only one owner id."}}), 400
    owner_kwargs = {}
    if non_null:
        k, v = non_null[0]
        try:
            owner_kwargs[k] = int(v)
        except ValueError:
            return jsonify({"errors": {"owner": f"{k} must be an integer"}}), 400

    rep_kind = (request.form.get("report_kind") or request.form.get("kind") or request.form.get("context") or "").strip().lower()
    if rep_kind not in ("sanitary", "system"):
        rep_kind = None

    raw_date = (request.form.get("last_date") or request.form.get("date") or "").strip()
    from datetime import date, datetime as dt
    rep_date = None
    if raw_date:
        try:
            rep_date = dt.strptime(raw_date, "%Y-%m-%d").date()
        except Exception:
            rep_date = None
    if rep_kind and not rep_date:
        rep_date = date.today()

    allowed = set(current_app.config.get("ALLOWED_UPLOADS", []))
    upload_dir = _ensure_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)

    saved = []
    for f, safe in unique_files:
        ct = (f.mimetype or "").lower()
        if allowed and ct not in allowed:
            return jsonify({"errors": {"file": f"Unsupported file type: {ct}"}}), 400

        if rep_kind and not owner_kwargs:
            date_str = rep_date.strftime("%Y-%m-%d")
            stored = f"REP_{rep_kind}_{date_str}_{uuid.uuid4().hex}_{safe}"
        else:
            stored = f"{uuid.uuid4().hex}_{safe}"

        f.save(os.path.join(upload_dir, stored))

        kwargs = dict(owner_kwargs)
        if hasattr(Attachment, "report_kind") and rep_kind and not owner_kwargs:
            kwargs["report_kind"] = rep_kind

        att = Attachment(
            user_id=u.id,
            filename=safe,
            stored_name=stored,
            content_type=ct,
            **kwargs,
        )
        db.session.add(att)
        saved.append(att)

    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return jsonify({"errors": {"_": f"Failed to save attachments: {type(ex).__name__}"}}), 400

    return jsonify({"ok": True, "items": [{
        "id": a.id, "filename": a.filename, "stored_name": a.stored_name,
        "content_type": a.content_type,
        "uploaded_at": a.uploaded_at.isoformat() if getattr(a, "uploaded_at", None) else None,
    } for a in saved]})
