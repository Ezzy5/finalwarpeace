# app/feed/routes/route_upload_attachments.py
from __future__ import annotations
import os
import uuid
import mimetypes
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import request, jsonify
from flask_login import login_required
from flask import current_app
from app.feed import bp
from app.feed.routes.uploads_ensure_feed_upload_dir import _ensure_feed_upload_dir
from app.feed.routes.util_static_url import _static_url

# Local constant (kept here to avoid extra module)
MAX_UPLOAD_MB = 50  # allow up to 50MB per file

@bp.post("/upload")
@login_required
def upload_attachments():
    """
    Accepts multipart/form-data with one or more "files" (any type).
    Saves into static/uploads/feed and returns metadata for each file.
    NO DB writes here (post_id is NOT NULL in FeedAttachment).
    """
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files"}), 400

        out_dir = _ensure_feed_upload_dir()
        items = []

        for f in files:
            orig_name = secure_filename(f.filename or "")
            if not orig_name:
                return jsonify({"error": "Missing filename"}), 400

            # size guard
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                return jsonify({"error": f"File too large (>{MAX_UPLOAD_MB}MB)"}), 400
            f.seek(0)

            # unique stored name
            ts = int(datetime.utcnow().timestamp() * 1000)
            token = uuid.uuid4().hex[:6]
            _, ext = os.path.splitext(orig_name)
            stored = f"{ts}_{token}{ext.lower()}"
            save_path = os.path.join(out_dir, stored)
            f.save(save_path)

            rel_path = f"uploads/feed/{stored}"
            file_url = _static_url(rel_path)

            # MIME detect
            mime = f.mimetype or mimetypes.guess_type(orig_name)[0] or "application/octet-stream"
            preview_url = file_url if mime.startswith("image/") else None

            items.append({
                "path": rel_path,
                "file_name": orig_name,
                "file_type": mime,
                "file_size": size,
                "file_url": file_url,
                "preview_url": preview_url,
            })

        return jsonify({"items": items}), 201
    except Exception as e:
        current_app.logger.exception("upload_attachments failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
