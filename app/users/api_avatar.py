from __future__ import annotations
import os
import uuid
import filetype
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, url_for
from flask_login import login_required, current_user
from app.extensions import db

bp = Blueprint("account_api", __name__, url_prefix="/api/users")

MAX_AVATAR_MB = 10
ALLOWED_TYPES = {"jpeg", "jpg", "png", "gif", "webp"}


# ---------- helpers ----------
def _static_root() -> str:
    return current_app.static_folder or os.path.join(current_app.root_path, "static")


def _ensure_avatar_dir() -> str:
    path = os.path.join(_static_root(), "uploads", "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def _static_url(rel_path: str) -> str:
    rel = rel_path.lstrip("/").replace("\\", "/")
    return url_for("static", filename=rel, _external=False)


# ---------- routes ----------
@bp.post("/me/avatar")
@login_required
def upload_avatar():
    """Upload new avatar for the logged-in user."""
    if not hasattr(current_user, "avatar_url"):
        return jsonify({"error": "avatar_url column missing on User model"}), 500

    f = request.files.get("file") or request.files.get("avatar")
    if not f:
        return jsonify({"error": "No file"}), 400

    # size check
    f.seek(0, os.SEEK_END)
    size = f.tell()
    if size > MAX_AVATAR_MB * 1024 * 1024:
        return jsonify({"error": f"File too large (>{MAX_AVATAR_MB}MB)"}), 400
    f.seek(0)

    out_dir = _ensure_avatar_dir()
    original_name = secure_filename(f.filename or "avatar")
    token = uuid.uuid4().hex[:8]
    tmp_name = f"tmp_{token}_{original_name}"
    tmp_path = os.path.join(out_dir, tmp_name)
    f.save(tmp_path)

    # detect image type using filetype
    try:
        kind = filetype.guess(tmp_path)
    except Exception:
        kind = None

    if not kind or not kind.mime.startswith("image/"):
        os.remove(tmp_path)
        return jsonify({"error": "Unsupported or invalid image file"}), 400

    ext = (kind.extension or "").lower()
    if ext not in ALLOWED_TYPES:
        os.remove(tmp_path)
        return jsonify({"error": "Unsupported image type"}), 400

    final_name = f"user_{current_user.id}_{token}.{ext}"
    final_path = os.path.join(out_dir, final_name)

    try:
        os.replace(tmp_path, final_path)
    except Exception as e:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return jsonify({"error": f"Failed to store file: {e}"}), 500

    rel = os.path.join("uploads", "avatars", final_name).replace("\\", "/")
    avatar_url = _static_url(rel)

    current_user.avatar_url = avatar_url
    if hasattr(current_user, "avatar_updated_at"):
        current_user.avatar_updated_at = datetime.utcnow()

    db.session.commit()

    bust = f"{avatar_url}{'&' if '?' in avatar_url else '?'}t={int(datetime.utcnow().timestamp())}"
    return jsonify({"ok": True, "avatar_url": bust})


@bp.delete("/me/avatar")
@login_required
def delete_avatar():
    """Remove current avatar (optional)."""
    if not hasattr(current_user, "avatar_url"):
        return jsonify({"error": "avatar_url column missing on User model"}), 500

    current_user.avatar_url = None
    if hasattr(current_user, "avatar_updated_at"):
        current_user.avatar_updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})
