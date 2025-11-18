# app/feed/routes/route_drive_picker.py
from __future__ import annotations
from flask import request, jsonify
from flask_login import login_required
from flask import current_app
from app.feed import bp
from app.feed.routes.util_parse_int import _parse_int
from app.feed.routes.drive_drive_fs_list import _drive_fs_list

@bp.get("/drive-picker")
@login_required
def drive_picker():
    """
    A simple, in-app Drive picker endpoint used by the Feed composer modal.
    Supports:
      - ?q=<search string>
      - ?limit=<int> (default 24)
      - ?cursor=<offset as string>
    Returns:
      { "items": [ {file_url, file_name, file_type, file_size, preview_url?} ], "next_cursor": "..." }
    """
    try:
        q = (request.args.get("q") or "").strip()
        limit = max(1, min(_parse_int(request.args.get("limit"), 24), 100))
        cursor = request.args.get("cursor")

        data = _drive_fs_list(q=q, limit=limit, cursor=cursor)
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("drive_picker failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
