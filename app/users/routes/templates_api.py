# app/users/routes/templates_api.py
from __future__ import annotations
from flask import jsonify, request
from flask_login import login_required, current_user

from .. import bp
from app.permissions import require_permission, has_permission, USERS_AGREEMENT, USERS_CREATE_EDIT

from .templates_store import (
    list_templates,
    get_template_by_id,
    create_template,
    update_template,
    delete_template,
)

@bp.get("/api/agreements/templates")
@login_required
@require_permission(USERS_AGREEMENT)
def api_templates_list():
    items = list_templates()
    return jsonify({"items": items})

@bp.get("/api/agreements/templates/<int:tid>")
@login_required
@require_permission(USERS_AGREEMENT)
def api_templates_get(tid: int):
    item = get_template_by_id(tid)
    if not item:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"item": item})

@bp.post("/api/agreements/templates")
@login_required
@require_permission(USERS_AGREEMENT)
def api_templates_create():
    if not has_permission(current_user, USERS_CREATE_EDIT):
        return jsonify({"error": "Forbidden"}), 403

    # Accept both JSON (html type) and multipart/form-data (docx type)
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        name = (request.form.get("name") or "").strip()
        ttype = (request.form.get("type") or "docx").strip().lower()
        description = (request.form.get("description") or "").strip()
        file = request.files.get("file") if ttype == "docx" else None
        if not name:
            return jsonify({"error": "Name is required"}), 400
        try:
            rec = create_template(name, ttype, description=description, file=file)
        except ValueError as ex:
            return jsonify({"error": str(ex)}), 400
        return jsonify({"ok": True, "item": rec})

    # JSON path (HTML templates)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    ttype = (data.get("type") or "html").strip().lower()
    description = (data.get("description") or "").strip()
    content = data.get("content") or ""
    if not name:
        return jsonify({"error": "Name is required"}), 400
    rec = create_template(name, ttype, description=description, content=content)
    return jsonify({"ok": True, "item": rec})

@bp.put("/api/agreements/templates/<int:tid>")
@login_required
@require_permission(USERS_AGREEMENT)
def api_templates_update(tid: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        return jsonify({"error": "Forbidden"}), 403

    if request.content_type and request.content_type.startswith("multipart/form-data"):
        name = request.form.get("name")
        ttype = request.form.get("type")
        description = request.form.get("description")
        file = request.files.get("file")
        rec = update_template(tid, name=name, ttype=ttype, description=description, file=file)
        if not rec:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"ok": True, "item": rec})

    data = request.get_json(silent=True) or {}
    rec = update_template(
        tid,
        name=data.get("name"),
        ttype=data.get("type"),
        description=data.get("description"),
        content=data.get("content"),
    )
    if not rec:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True, "item": rec})

@bp.delete("/api/agreements/templates/<int:tid>")
@login_required
@require_permission(USERS_AGREEMENT)
def api_templates_delete(tid: int):
    if not has_permission(current_user, USERS_CREATE_EDIT):
        return jsonify({"error": "Forbidden"}), 403
    ok = delete_template(tid)
    return (jsonify({"ok": True}) if ok else (jsonify({"error": "Not found"}), 404))
