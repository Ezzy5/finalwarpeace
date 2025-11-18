# app/users/routes/templates_crud.py
import os
from uuid import uuid4
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .. import bp
from ...extensions import db
from ...models import AgreementTemplate
from app.permissions import require_permission, USERS_AGREEMENT, USERS_CREATE_EDIT

TEMPLATES_DIR_KEY = "AGREEMENT_TEMPLATES_DIR"

def _templates_dir():
    base = current_app.config.get(TEMPLATES_DIR_KEY)
    if not base:
        base = os.path.join(current_app.instance_path, "agreement_templates")
    os.makedirs(base, exist_ok=True)
    return base

@bp.get("/api/agreements/templates")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_list():
    rows = AgreementTemplate.query.order_by(AgreementTemplate.updated_at.desc()).all()
    # For listing we don’t send body by default (could be large); add a /<id> details if needed
    return jsonify({"items": [
        {"id": t.id, "name": t.name, "type": t.type, "content_filename": t.content_filename}
        for t in rows
    ]})

@bp.get("/api/agreements/templates/<int:tpl_id>")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_get(tpl_id: int):
    t = AgreementTemplate.query.get_or_404(tpl_id)
    return jsonify({
        "id": t.id,
        "name": t.name,
        "type": t.type,
        "body": t.body if t.type == "text" else None,
        "content_filename": t.content_filename if t.type == "docx" else None,
    })

@bp.post("/api/agreements/templates")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_create():
    # Also require create/edit to change content
    if not current_user or not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401
    # If you want to enforce edit permission here:
    # from app.permissions import has_permission
    # if not has_permission(current_user, USERS_CREATE_EDIT): return jsonify({"error":"Forbidden"}), 403

    ttype = (request.form.get("type") or "").strip().lower()
    name  = (request.form.get("name") or "").strip()
    if not ttype or ttype not in {"text", "docx"}:
        return jsonify({"errors": {"type": "Must be 'text' or 'docx'."}}), 400
    if not name:
        return jsonify({"errors": {"name": "Required."}}), 400

    tpl = AgreementTemplate(name=name, type=ttype, created_by=getattr(current_user, "id", None))

    if ttype == "text":
        body = request.form.get("body") or ""
        if not body.strip():
            return jsonify({"errors": {"body": "Required for text templates."}}), 400
        tpl.body = body
    else:  # docx
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"errors": {"file": "Upload a .docx file."}}), 400
        safe = secure_filename(f.filename)
        if not safe.lower().endswith(".docx"):
            return jsonify({"errors": {"file": "Only .docx supported."}}), 400
        stored = f"{uuid4().hex}_{safe}"
        f.save(os.path.join(_templates_dir(), stored))
        tpl.file_path = stored
        tpl.content_filename = safe

    db.session.add(tpl)
    db.session.commit()
    return jsonify({"ok": True, "item": {"id": tpl.id, "name": tpl.name, "type": tpl.type}}), 201

@bp.post("/api/agreements/templates/<int:tpl_id>")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_update(tpl_id: int):
    tpl = AgreementTemplate.query.get_or_404(tpl_id)
    name = (request.form.get("name") or tpl.name).strip()
    tpl.name = name

    if tpl.type == "text":
        if "body" in request.form:
            tpl.body = request.form.get("body") or ""
    else:
        f = request.files.get("file")
        if f and f.filename:
            safe = secure_filename(f.filename)
            if not safe.lower().endswith(".docx"):
                return jsonify({"errors": {"file": "Only .docx supported."}}), 400
            stored = f"{uuid4().hex}_{safe}"
            f.save(os.path.join(_templates_dir(), stored))
            tpl.file_path = stored
            tpl.content_filename = safe

    db.session.commit()
    return jsonify({"ok": True})

@bp.post("/api/agreements/templates/<int:tpl_id>/delete")
@login_required
@require_permission(USERS_AGREEMENT)
def templates_delete(tpl_id: int):
    tpl = AgreementTemplate.query.get_or_404(tpl_id)
    if tpl.type == "docx" and tpl.file_path:
        try:
            os.remove(os.path.join(_templates_dir(), tpl.file_path))
        except Exception:
            pass
    db.session.delete(tpl)
    db.session.commit()
    return jsonify({"ok": True})
