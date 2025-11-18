# app/drive/routes.py
import os
import uuid
import mimetypes
import subprocess
import shutil
from pathlib import Path

from flask import (
    Blueprint, render_template, request, jsonify, current_app, send_file, abort
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import and_, func

from ..extensions import db
from ..models import DriveFolder, DriveFile, DriveACL, DrivePermission, User
from . import bp  # blueprint defined in app/drive/__init__.py with url_prefix="/drive"

# --------------------------------------
# Constants / helpers
# --------------------------------------

OFFICE_EXTS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}

def _uploads_root() -> str:
    """
    Directory where uploaded binaries are stored.
    Uses app.config["DRIVE_UPLOAD_FOLDER"] and creates it if needed.
    """
    root = current_app.config.get("DRIVE_UPLOAD_FOLDER")
    Path(root).mkdir(parents=True, exist_ok=True)
    return root

def _previews_root() -> str:
    """
    Directory where generated previews (e.g., converted PDFs) are stored.
    Uses app.config["DRIVE_PREVIEW_FOLDER"] and creates it if needed.
    """
    root = current_app.config.get("DRIVE_PREVIEW_FOLDER")
    Path(root).mkdir(parents=True, exist_ok=True)
    return root

def _ext(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()

def _is_image(mime: str) -> bool:
    return (mime or "").startswith("image/")

def _is_video(mime: str) -> bool:
    return (mime or "").startswith("video/")

def _is_audio(mime: str) -> bool:
    return (mime or "").startswith("audio/")

def _is_pdf(mime: str) -> bool:
    return (mime or "").lower() == "application/pdf"

def _soffice_path() -> str | None:
    # Prefer explicit config; fallback to PATH lookup
    p = current_app.config.get("DRIVE_SOFFICE_PATH")
    if p:
        return p
    return shutil.which("soffice")

def _has_libreoffice() -> bool:
    p = _soffice_path()
    return bool(p and os.path.exists(p))

def _convert_office_to_pdf(src_path: str) -> str | None:
    """
    Convert Office file to PDF via LibreOffice headless.
    Returns path to generated PDF, or None on failure.
    """
    soffice = _soffice_path()
    if not soffice:
        return None

    previews = _previews_root()
    base = os.path.splitext(os.path.basename(src_path))[0]
    out_pdf = os.path.join(previews, base + ".pdf")

    # Cache: reuse if output is newer than source
    try:
        if os.path.exists(out_pdf) and os.path.getmtime(out_pdf) >= os.path.getmtime(src_path):
            return out_pdf
    except Exception:
        pass

    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", previews, src_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out_pdf if os.path.exists(out_pdf) else None
    except Exception as e:
        current_app.logger.warning("LibreOffice convert failed: %s", e)
        return None

def _folder_or_404(folder_id):
    if folder_id in (None, "", "null", "None"):
        return None
    f = DriveFolder.query.get(int(folder_id))
    if not f:
        abort(404)
    return f

def _delete_folder_recursive(folder: DriveFolder):
    """
    Delete all files and subfolders under `folder`, then delete `folder`.
    (Not currently used because we rely on DELETE endpoint + cascade deletes.)
    """
    # Delete files from disk + DB
    for f in list(folder.files):
        try:
            if f.stored_name:
                path = os.path.join(_uploads_root(), f.stored_name)
                if os.path.exists(path):
                    os.remove(path)
        except Exception:
            pass
        db.session.delete(f)

    # Recurse into subfolders
    for sub in list(folder.children):
        _delete_folder_recursive(sub)

    db.session.delete(folder)

# --------------------------------------
# Permissions helpers (owner has FULL)
# --------------------------------------

def _is_owner_folder(user_id: int, folder: DriveFolder) -> bool:
    return folder and folder.owner_id == user_id

def _is_owner_file(user_id: int, file: DriveFile) -> bool:
    return file and file.uploader_id == user_id

def _direct_perm(user_id: int, target_type: str, target_id: int) -> DrivePermission | None:
    row = DriveACL.query.filter_by(target_type=target_type, target_id=target_id, user_id=user_id).first()
    return row.permission if row else None

def has_perm(user_id: int, obj, need: DrivePermission) -> bool:
    """
    need in {read, write, full}
    Owner => full.
    We propagate folder ACL to descendants, so direct lookups suffice.
    """
    if obj is None:
        return False

    if isinstance(obj, DriveFolder):
        if _is_owner_folder(user_id, obj):
            return True
        perm = _direct_perm(user_id, "folder", obj.id)
    else:
        if _is_owner_file(user_id, obj):
            return True
        perm = _direct_perm(user_id, "file", obj.id)

    order = [DrivePermission.read, DrivePermission.write, DrivePermission.full]
    if perm is None:
        return False
    return order.index(perm) >= order.index(need)

def require_perm(obj, need: DrivePermission):
    if not has_perm(current_user.id, obj, need):
        abort(403)

# --------------------------------------
# Subtree utils (ACL propagation)
# --------------------------------------

def _collect_descendants(folder_id: int):
    """
    Return (folder_ids, file_ids) for all descendants of folder_id.
    Folders: excludes the starting folder_id itself.
    """
    folder_ids = []
    stack = [folder_id]
    while stack:
        f_id = stack.pop()
        children = DriveFolder.query.filter_by(parent_id=f_id).all()
        for c in children:
            folder_ids.append(c.id)
            stack.append(c.id)

    file_ids = []
    if folder_ids:
        files = DriveFile.query.filter(DriveFile.folder_id.in_(folder_ids)).all()
        file_ids = [x.id for x in files]
    return folder_ids, file_ids

def _build_breadcrumbs(folder: DriveFolder):
    crumbs = []
    cur = folder
    while cur:
        crumbs.append({"id": cur.id, "name": cur.name})
        cur = cur.parent
    crumbs.reverse()
    return crumbs

# --------------------------------------
# Pages
# --------------------------------------

@bp.route("/panel")
@login_required
def panel():
    # If fetched via SPA loader, return just the partial.
    if request.headers.get("X-Requested-With") == "fetch":
        return render_template("panel_drive.html")
    # Otherwise load the dashboard and hint the drive tab.
    return render_template("dashboard.html", initial_panel="drive")

# --------------------------------------
# API: List (root or inside folder)
# --------------------------------------

@bp.route("/api/list", methods=["GET"])
@login_required
def api_list():
    folder_id = request.args.get("folder_id", type=int)

    if folder_id:
        folder = db.session.get(DriveFolder, folder_id)
        if not folder:
            abort(404)
        require_perm(folder, DrivePermission.read)

        breadcrumbs = _build_breadcrumbs(folder)

        # child folders visible to the user
        child_q = DriveFolder.query.filter_by(parent_id=folder_id)
        child_folders = []
        for f in child_q:
            if has_perm(current_user.id, f, DrivePermission.read):
                shared = (not _is_owner_folder(current_user.id, f)) and (_direct_perm(current_user.id, "folder", f.id) is not None)
                child_folders.append(f.to_dict(current_user_id=current_user.id, shared=shared))

        # files visible to the user
        files_q = DriveFile.query.filter_by(folder_id=folder_id)
        files = []
        for fi in files_q:
            if has_perm(current_user.id, fi, DrivePermission.read):
                shared = (not _is_owner_file(current_user.id, fi)) and (_direct_perm(current_user.id, "file", fi.id) is not None)
                files.append(fi.to_dict(current_user_id=current_user.id, shared=shared))

        return jsonify({
            "ok": True,
            "current_folder": folder.to_dict(current_user_id=current_user.id),
            "breadcrumbs": breadcrumbs,
            "folders": child_folders,
            "files": files,
        })

    # ROOT: show owned items + items explicitly shared to current user

    # folders the user owns at root
    own_root_folders = DriveFolder.query.filter_by(parent_id=None, owner_id=current_user.id).all()

    # folders shared to current user at root
    acl_folder_ids = [a.target_id for a in DriveACL.query.filter_by(target_type="folder", user_id=current_user.id).all()]
    shared_root_folders = []
    if acl_folder_ids:
        shared_root_folders = DriveFolder.query.filter(
            and_(DriveFolder.parent_id.is_(None), DriveFolder.id.in_(acl_folder_ids))
        ).all()

    # files at root that user owns
    own_root_files = DriveFile.query.filter_by(folder_id=None, uploader_id=current_user.id).all()

    # files at root shared to user
    acl_file_ids = [a.target_id for a in DriveACL.query.filter_by(target_type="file", user_id=current_user.id).all()]
    shared_root_files = []
    if acl_file_ids:
        shared_root_files = DriveFile.query.filter(
            and_(DriveFile.folder_id.is_(None), DriveFile.id.in_(acl_file_ids))
        ).all()

    folders = [f.to_dict(current_user_id=current_user.id) for f in own_root_folders] + \
              [f.to_dict(current_user_id=current_user.id, shared=True) for f in shared_root_folders]
    files = [fi.to_dict(current_user_id=current_user.id) for fi in own_root_files] + \
            [fi.to_dict(current_user_id=current_user.id, shared=True) for fi in shared_root_files]

    return jsonify({
        "ok": True,
        "current_folder": None,
        "breadcrumbs": [],
        "folders": folders,
        "files": files,
    })

# --------------------------------------
# API: Users (for share modal)
# --------------------------------------

@bp.route("/api/users", methods=["GET"])
@login_required
def api_users():
    """
    Return other users (to share with). Robust to different User fields.
    URL: /drive/api/users
    """
    try:
        users = User.query.filter(User.id != current_user.id).all()

        def display_name(u):
            return (
                getattr(u, "full_name", None)
                or getattr(u, "name", None)
                or getattr(u, "username", None)
                or getattr(u, "email", None)
                or f"User #{u.id}"
            )

        payload = [
            {"id": u.id, "name": display_name(u), "email": getattr(u, "email", "") or ""}
            for u in users
        ]
        payload.sort(key=lambda x: (x["name"] or "").lower())
        return jsonify({"ok": True, "users": payload})
    except Exception:
        current_app.logger.exception("api_users failed")
        return jsonify({"ok": False, "error": "Users query failed."}), 500

# --------------------------------------
# API: Create / Delete / Move (Folders & Files)
# --------------------------------------

@bp.route("/api/folder/create", methods=["POST"])
@login_required
def api_folder_create():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    parent_id = data.get("parent_id", None)

    if not name:
        return jsonify({"error": "Name required."}), 400

    parent = None
    if parent_id:
        parent = db.session.get(DriveFolder, int(parent_id))
        if not parent:
            return jsonify({"error": "Parent not found."}), 404
        require_perm(parent, DrivePermission.write)

    folder = DriveFolder(name=name, parent=parent, owner=current_user)
    db.session.add(folder)
    db.session.commit()
    return jsonify({"ok": True, "folder": folder.to_dict(current_user_id=current_user.id)})

from flask import jsonify, abort, request
from sqlalchemy import func

@bp.route("/api/folder/<int:folder_id>/delete", methods=["POST"])
@login_required
def api_folder_delete(folder_id: int):
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))

    folder = db.session.get(DriveFolder, folder_id)
    if not folder:
        abort(404)

    # only FULL can delete (owner included)
    require_perm(folder, DrivePermission.full)

    # Efficiently check if folder is empty
    children_count = db.session.query(func.count(DriveFolder.id))\
                               .filter(DriveFolder.parent_id == folder.id)\
                               .scalar()
    files_count = db.session.query(func.count(DriveFile.id))\
                            .filter(DriveFile.folder_id == folder.id)\
                            .scalar()

    if not force and (children_count > 0 or files_count > 0):
        return jsonify({"error": "Folder is not empty."}), 400

    if force:
        # Recursively delete subtree (folders + files on disk)
        _delete_folder_recursive(folder)

    else:
        # No children/files; just delete this folder
        db.session.delete(folder)

    db.session.commit()
    return jsonify({"ok": True})


def _delete_folder_recursive(folder: "DriveFolder"):
    """
    Deletes all files (including on-disk blobs) and child folders, then the folder itself.
    Assumes caller has permission on the root 'folder'.
    """
    # Delete files in this folder (remove blob if present)
    files = db.session.query(DriveFile).filter(DriveFile.folder_id == folder.id).all()
    for f in files:
        if f.stored_name:
            try:
                path = os.path.join(_uploads_root(), f.stored_name)
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                # Keep going; we don't want FS hiccups to wedge the DB transaction
                pass
        db.session.delete(f)

    # Recurse into children
    children = db.session.query(DriveFolder).filter(DriveFolder.parent_id == folder.id).all()
    for child in children:
        # Optional: permission enforcement per child; comment out if not needed:
        # require_perm(child, DrivePermission.full)
        _delete_folder_recursive(child)

    # Finally delete this folder
    db.session.delete(folder)


@bp.route("/api/file/<int:file_id>/delete", methods=["POST"])
@login_required
def api_file_delete(file_id: int):
    f = db.session.get(DriveFile, file_id)
    if not f:
        abort(404)
    require_perm(f, DrivePermission.full)  # only full can delete

    if f.stored_name:
        try:
            path = os.path.join(_uploads_root(), f.stored_name)
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass

    db.session.delete(f)
    db.session.commit()
    return jsonify({"ok": True})

@bp.route("/api/file/upload", methods=["POST"])
@login_required
def api_file_upload():
    folder_id = request.form.get("folder_id", type=int)
    folder = db.session.get(DriveFolder, folder_id) if folder_id else None
    if folder:
        require_perm(folder, DrivePermission.write)

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file provided."}), 400

    original_name = secure_filename(file.filename)
    ext = os.path.splitext(original_name)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"

    up_root = _uploads_root()
    file_path = os.path.join(up_root, stored_name)
    file.save(file_path)
    size = os.path.getsize(file_path)

    rec = DriveFile(
        folder=folder,
        original_name=original_name,
        stored_name=stored_name,
        mimetype=file.mimetype,
        size=size,
        uploader=current_user,
    )
    db.session.add(rec)
    db.session.commit()
    return jsonify({"ok": True, "file": rec.to_dict(current_user_id=current_user.id)})

@bp.route("/api/file/move", methods=["POST"])
@login_required
def api_file_move():
    data = request.get_json(silent=True) or {}

    # params
    force = bool(data.get("force", False))  # fine to keep; unused for now
    file_id = data.get("id")
    target_folder_id = data.get("target_folder_id")

    # validate
    if file_id is None:
        return jsonify({"error": "Missing required parameter: id"}), 400
    try:
        file_id = int(file_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Parameter 'id' must be an integer"}), 400

    if target_folder_id in ("", None):
        target_folder_id = None
    else:
        try:
            target_folder_id = int(target_folder_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Parameter 'target_folder_id' must be an integer or null"}), 400

    # load + perms
    f = db.session.get(DriveFile, file_id)
    if not f:
        return jsonify({"error": "File not found."}), 404
    require_perm(f, DrivePermission.full)

    target_folder = None
    if target_folder_id is not None:
        target_folder = db.session.get(DriveFolder, target_folder_id)
        if not target_folder:
            return jsonify({"error": "Target folder not found."}), 404
        require_perm(target_folder, DrivePermission.write)

    # move
    f.folder = target_folder
    db.session.commit()

    return jsonify({"ok": True})


@bp.route("/api/folder/move", methods=["POST"])
@login_required
def api_folder_move():
    # Parse JSON safely once
    data = request.get_json(silent=True) or {}

    # Params
    force = bool(data.get("force", False))  # keep if you’ll use it later

    # Validate folder_id
    folder_id = data.get("id")
    if folder_id is None:
        return jsonify({"error": "Missing required parameter: id"}), 400
    try:
        folder_id = int(folder_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Parameter 'id' must be an integer"}), 400

    # Validate target_parent_id (optional)
    target_parent_id = data.get("target_parent_id", None)
    if target_parent_id in ("", None):
        target_parent_id = None
    else:
        try:
            target_parent_id = int(target_parent_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Parameter 'target_parent_id' must be an integer or null"}), 400

    # Load current folder + permission
    folder = db.session.get(DriveFolder, folder_id)
    if not folder:
        return jsonify({"error": "Folder not found."}), 404
    require_perm(folder, DrivePermission.full)  # moving a folder requires full

    # Short-circuit: no change
    if (target_parent_id is None and getattr(folder, "parent_id", None) is None) or \
       (target_parent_id is not None and target_parent_id == getattr(folder, "parent_id", None)):
        return jsonify({"ok": True})  # nothing to do

    # Load target parent (if provided) + permission
    new_parent = None
    if target_parent_id is not None:
        if target_parent_id == folder_id:
            return jsonify({"error": "Cannot move a folder into itself."}), 400

        new_parent = db.session.get(DriveFolder, target_parent_id)
        if not new_parent:
            return jsonify({"error": "Target folder not found."}), 404
        require_perm(new_parent, DrivePermission.write)

        # Prevent moving into a descendant (cycle check via ancestor walk)
        p = new_parent
        while p is not None:
            if p.id == folder.id:
                return jsonify({"error": "Cannot move a folder into itself or its descendant."}), 400
            p = p.parent  # assumes relationship DriveFolder.parent exists

    # Apply move
    folder.parent = new_parent
    db.session.commit()

    return jsonify({"ok": True})

# --------------------------------------
# File serving / preview
# --------------------------------------

@bp.route("/files/<int:file_id>/download")
@login_required
def file_download(file_id: int):
    """
    Single endpoint for both 'attachment' and 'inline' delivery:
      - ?disposition=inline  -> attempt in-browser view
      - default (or anything else) -> attachment download
    """
    f = db.session.get(DriveFile, file_id) or abort(404)
    require_perm(f, DrivePermission.read)

    path = os.path.join(_uploads_root(), f.stored_name or "")
    if not os.path.isfile(path):
        abort(404)

    mime = f.mimetype or mimetypes.guess_type(f.original_name or "")[0] or "application/octet-stream"
    disp = (request.args.get("disposition") or "attachment").lower()
    as_attachment = (disp != "inline")

    resp = send_file(path, mimetype=mime, as_attachment=as_attachment, download_name=f.original_name)
    if not as_attachment:
        # Make intent explicit for browsers that honor it
        resp.headers["Content-Disposition"] = f'inline; filename="{f.original_name}"'
    return resp

@bp.route("/files/<int:file_id>/viewer")
@login_required
def file_viewer(file_id: int):
    """
    Render an HTML viewer that tries to show the file inline.
    - images/video/audio/text/pdf render directly
    - office docs are converted to PDF via LibreOffice if possible
    - otherwise show a helpful fallback with a download link
    """
    f: DriveFile = DriveFile.query.get_or_404(file_id)
    require_perm(f, DrivePermission.read)

    up_path = os.path.join(_uploads_root(), f.stored_name or "")
    if not os.path.isfile(up_path):
        abort(404)

    mime = f.mimetype or mimetypes.guess_type(f.original_name or "")[0] or "application/octet-stream"
    ext = _ext(f.original_name or f.stored_name or "")

    preview = {
        "kind": "unsupported",     # "image"|"video"|"audio"|"pdf"|"text"|"unsupported"
        "src": None,
        "name": f.original_name,
        "mime": mime
    }

    if _is_image(mime):
        preview["kind"] = "image"
        preview["src"] = f"/drive/files/{file_id}/download?disposition=inline"
    elif _is_video(mime):
        preview["kind"] = "video"
        preview["src"] = f"/drive/files/{file_id}/download?disposition=inline"
    elif _is_audio(mime):
        preview["kind"] = "audio"
        preview["src"] = f"/drive/files/{file_id}/download?disposition=inline"
    elif _is_pdf(mime):
        preview["kind"] = "pdf"
        preview["src"] = f"/drive/files/{file_id}/download?disposition=inline"
    elif ext in {".txt", ".md", ".csv", ".log"}:
        preview["kind"] = "text"
        preview["src"] = f"/drive/files/{file_id}/raw"
    elif ext in OFFICE_EXTS:
        pdf_path = _convert_office_to_pdf(up_path)
        if pdf_path and os.path.exists(pdf_path):
            preview["kind"] = "pdf"
            preview["src"] = f"/drive/preview-cache/{os.path.basename(pdf_path)}"
        else:
            preview["kind"] = "unsupported"
    else:
        preview["kind"] = "unsupported"

    return render_template("viewer.html", file=f, preview=preview)

@bp.route("/preview-cache/<path:filename>")
@login_required
def preview_cache(filename):
    """Serve generated preview artifacts (e.g., converted PDFs)."""
    path = os.path.join(_previews_root(), filename)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=filename)

@bp.route("/files/<int:file_id>/raw")
@login_required
def file_raw(file_id: int):
    """Serve small text files as text/plain for inline <pre> viewing."""
    f: DriveFile = DriveFile.query.get_or_404(file_id)
    require_perm(f, DrivePermission.read)

    path = os.path.join(_uploads_root(), f.stored_name or "")
    if not os.path.isfile(path):
        abort(404)
    return send_file(
        path,
        mimetype="text/plain; charset=utf-8",
        as_attachment=False,
        download_name=f.original_name or "text.txt"
    )

# --------------------------------------
# ACL (get/set)
# --------------------------------------

def _get_target(target_type: str, target_id: int):
    if target_type == "folder":
        obj = db.session.get(DriveFolder, target_id)
    elif target_type == "file":
        obj = db.session.get(DriveFile, target_id)
    else:
        obj = None
    return obj

@bp.route("/api/acl/<string:target_type>/<int:target_id>", methods=["GET"])
@login_required
def api_acl_get(target_type, target_id):
    obj = _get_target(target_type, target_id)
    if not obj:
        abort(404)
    # Only owners or FULL can manage ACL
    require_perm(obj, DrivePermission.full)

    rows = DriveACL.query.filter_by(target_type=target_type, target_id=target_id).all()
    return jsonify({
        "ok": True,
        "grants": [
            {
                "user_id": r.user_id,
                "permission": r.permission.value,
                "inherited": r.inherited
            } for r in rows
        ]
    })

@bp.route("/api/acl/<string:target_type>/<int:target_id>", methods=["POST"])
@login_required
def api_acl_set(target_type, target_id):
    """
    Replace ACL for this target with provided grants.
    For folders: also propagate to descendants (replace inherited grants).
    Body: { "grants": [ {"user_id": <int>, "permission": "read|write|full"}, ... ] }
    """
    obj = _get_target(target_type, target_id)
    if not obj:
        abort(404)
    # Only owners or FULL can manage
    require_perm(obj, DrivePermission.full)

    data = request.get_json() or {}
    grants = data.get("grants", [])

    # Sanitize
    seen = set()
    cleaned = []
    for g in grants:
        uid = int(g.get("user_id"))
        perm_str = (g.get("permission") or "read").lower()
        if uid == current_user.id:
            continue
        if perm_str not in ("read", "write", "full"):
            continue
        if uid in seen:
            continue
        seen.add(uid)
        cleaned.append((uid, DrivePermission(perm_str)))

    # Replace direct ACL on target
    DriveACL.query.filter_by(target_type=target_type, target_id=target_id, inherited=False).delete()
    for uid, perm in cleaned:
        db.session.add(DriveACL(
            target_type=target_type,
            target_id=target_id,
            user_id=uid,
            permission=perm,
            inherited=False
        ))
    db.session.flush()

    # If folder → propagate to descendants as inherited rows
    if target_type == "folder":
        folder_id = target_id
        desc_folders, desc_files = _collect_descendants(folder_id)

        if desc_folders:
            DriveACL.query.filter(
                DriveACL.target_type == "folder",
                DriveACL.target_id.in_(desc_folders),
                DriveACL.inherited.is_(True)
            ).delete(synchronize_session=False)

        if desc_files:
            DriveACL.query.filter(
                DriveACL.target_type == "file",
                DriveACL.target_id.in_(desc_files),
                DriveACL.inherited.is_(True)
            ).delete(synchronize_session=False)

        for fid in desc_folders:
            for uid, perm in cleaned:
                db.session.add(DriveACL(
                    target_type="folder",
                    target_id=fid,
                    user_id=uid,
                    permission=perm,
                    inherited=True
                ))
        for file_id in desc_files:
            for uid, perm in cleaned:
                db.session.add(DriveACL(
                    target_type="file",
                    target_id=file_id,
                    user_id=uid,
                    permission=perm,
                    inherited=True
                ))

    db.session.commit()
    return jsonify({"ok": True})
