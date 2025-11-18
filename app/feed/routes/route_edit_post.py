# app/feed/routes/route_edit_post.py
from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime
from flask import request, jsonify, abort
from flask_login import login_required, current_user
from app.extensions import db
from flask import current_app
from app.feed import bp
from app.feed.models import FeedPost
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.util_can_edit_post import _can_edit_post
from app.feed.routes.posts_reconcile_post_attachments_keep_only import _reconcile_post_attachments_keep_only
from app.feed.routes.posts_attach_local_uploads_to_post import _attach_local_uploads_to_post
from app.feed.routes.posts_attach_drive_items_to_post import _attach_drive_items_to_post
from app.feed.routes.serializers_post_to_dict import _post_to_dict

@bp.route("/<int:post_id>", methods=["PATCH", "POST"])
@login_required
def edit_post(post_id: int):
    """
    Accepts:
      - title, html
      - upload_paths: list[str]        -> add more local files (from /api/feed/upload)
      - drive_items:  list[dict]       -> add more drive items
      - keep_attachment_ids: list[int] -> keep only these; others are removed (soft-delete if model supports it)
    """
    # Allow POST with X-HTTP-Method-Override: PATCH
    if request.method == "POST" and (request.headers.get("X-HTTP-Method-Override","").upper() != "PATCH"):
        abort(405)

    p: FeedPost | None = db.session.get(FeedPost, post_id)
    if not p:
        return jsonify({"error": "Not found"}), 404
    if _has_col(FeedPost, "is_deleted") and getattr(p, "is_deleted", False):
        return jsonify({"error": "Not found"}), 404
    if not _can_edit_post(current_user, p):
        return jsonify({"error": "Forbidden"}), 403

    data: Dict[str, Any] = request.get_json(silent=True) or {}
    title = data.get("title")
    html = data.get("html")
    upload_paths: List[str] = data.get("upload_paths") or []
    drive_items: List[Dict[str, Any]] = data.get("drive_items") or []
    keep_attachment_ids: List[int] | None = data.get("keep_attachment_ids")

    changed = False
    if title is not None:
        p.title = (title or "").strip() or None
        changed = True
    if html is not None:
        p.html = (html or "").strip() or None
        changed = True

    # reconcile attachments if keep list provided
    if keep_attachment_ids is not None:
        _reconcile_post_attachments_keep_only(p, keep_attachment_ids)
        changed = True

    # add new attachments, if any
    if upload_paths:
        _attach_local_uploads_to_post(p, upload_paths, current_user.id)
        changed = True
    if drive_items:
        _attach_drive_items_to_post(p, drive_items, current_user.id)
        changed = True

    if not changed:
        return jsonify({"error": "No changes"}), 400

    if _has_col(FeedPost, "updated_at"):
        p.updated_at = datetime.utcnow()

    db.session.commit()
    return jsonify(_post_to_dict(p, with_rel=True, u=current_user)), 200
