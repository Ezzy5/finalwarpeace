import os
from pathlib import Path

from flask import request, jsonify, send_from_directory, Blueprint, current_app
from flask_login import login_required, current_user

from . import bp
from .storage import save_file, make_thumbnail, get_upload_root

# ---------- Public file serving (no auth) ----------
# We expose a tiny public blueprint at /u/<path> for the URLs we issue.
public_bp = Blueprint("uploads_public", __name__, url_prefix="/u")

@public_bp.route("/<path:relpath>")
def serve_upload(relpath: str):
    root = get_upload_root()
    # prevent path traversal
    rel = Path(relpath)
    try:
        abs_path = (root / rel).resolve()
    except Exception:
        return ("Not found", 404)
    if not str(abs_path).startswith(str(root.resolve())) or not abs_path.exists():
        return ("Not found", 404)
    return send_from_directory(abs_path.parent.as_posix(), abs_path.name, conditional=True)

# You must register public_bp alongside this module's bp in your app factory.


# ---------- Secure upload endpoints ----------
@bp.post("/feed")
@login_required
def upload_feed_files():
    """
    Multipart upload: field name 'files' (can be multiple).
    Returns: { ok, items: [ { name, mime, size, url, preview_url } ] }
    Access: anyone logged in; your feed audience rules govern visibility.
    """
    if "files" not in request.files:
        return jsonify({"ok": False, "error": "No files"}), 400

    files = request.files.getlist("files")
    items = []
    for f in files:
        try:
            abs_path, url = save_file(f, subdir="feed")
            preview_url = None
            if (f.mimetype or "").startswith("image/"):
                t = make_thumbnail(abs_path)
                if t:
                    preview_url = t[1]
            items.append({
                "name": f.filename,
                "mime": f.mimetype,
                "size": os.path.getsize(abs_path),
                "url": url,
                "preview_url": preview_url or url if (f.mimetype or "").startswith("image/") else None
            })
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except Exception as e:
            current_app.logger.exception("Upload error: %s", e)
            return jsonify({"ok": False, "error": "Upload failed"}), 500

    return jsonify({"ok": True, "items": items})


@bp.delete("/purge")
@login_required
def purge_file():
    """
    Optional helper: DELETE ?url=/u/feed/2025/10/17/<file>
    Removes a single file you previously uploaded (does not touch DB).
    """
    url = request.args.get("url", "").strip()
    if not url or "/u/" not in url:
        return jsonify({"ok": False, "error": "Invalid URL"}), 400
    root = get_upload_root().resolve()
    rel = url.split("/u/", 1)[-1]
    path = (root / rel).resolve()
    if not str(path).startswith(str(root)) or not path.exists():
        return jsonify({"ok": False, "error": "Not found"}), 404
    try:
        path.unlink(missing_ok=True)
        # try thumbnail too
        t = path.with_name(path.stem + "_thumb.jpg")
        if t.exists():
            t.unlink(missing_ok=True)
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"ok": False, "error": "Cannot delete"}), 500
