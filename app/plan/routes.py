# app/plan/routes.py
import mimetypes, shutil, subprocess, tempfile, os, uuid
from pathlib import Path
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import (
    request, jsonify, render_template, abort, current_app, url_for, send_file, redirect, Response
)
from flask_login import login_required, current_user
from werkzeug.routing import BuildError
from werkzeug.utils import secure_filename

from ..extensions import db
from . import bp

from ..models import (
    User, Department, Attachment,
    PlanTask, PlanComment, PlanActivity,
    TaskStatus, TaskPriority,
)

TZ = ZoneInfo("Europe/Skopje")

# ======================
# Helpers (roles/authz)
# ======================


RENDER_INLINE = {
    "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
    "text/plain",
}

OFFICE_EXTS = {
    ".doc", ".docx", ".rtf", ".odt",
    ".xls", ".xlsx", ".ods", ".csv",
    ".ppt", ".pptx", ".odp",
}

def _upload_root():
    return current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(current_app.root_path, "uploads")
    )
def _lo_workdir() -> Path:
    cfg = current_app.config.get("LIBREOFFICE_WORKDIR")
    if cfg:
        p = Path(cfg)
    else:
        p = Path("C:/lo_work") if os.name == "nt" else Path("/tmp/lo_work")
    p.mkdir(parents=True, exist_ok=True)
    return p

def _short_path(p: str) -> str:
    if os.name != "nt":
        return p
    try:
        import ctypes
        from ctypes import wintypes
        _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        _GetShortPathNameW.restype = wintypes.DWORD
        buf = ctypes.create_unicode_buffer(4096)
        r = _GetShortPathNameW(p, buf, len(buf))
        if r and r < len(buf):
            return buf.value
    except Exception:
        pass
    return p

def _guess_office_ext(att) -> str:
    """
    Pick an extension for LO if the stored file lost its suffix.
    """
    name = (getattr(att, "original_name", None) or getattr(att, "filename", "") or "").lower()
    ext = Path(name).suffix.lower()
    if ext in OFFICE_EXTS:
        return ext
    ctype = (getattr(att, "content_type", None) or "").lower()
    if "word" in ctype or "msword" in ctype:
        return ".docx"
    if "excel" in ctype or "sheet" in ctype:
        return ".xlsx"
    if "powerpoint" in ctype or "presentation" in ctype:
        return ".pptx"
    if name.endswith(".csv"):
        return ".csv"
    if name.endswith(".tsv"):
        return ".tsv"
    return ".docx"

def _resolve_attachment_abs_path(att) -> str | None:
    """
    Resolve the absolute path of the stored file across common field/dir layouts.
    As a last resort, recursively search likely roots to find the file.
    """
    # Candidate names from the model
    rel_names = [
        getattr(att, "absolute_path", None),   # absolute is fine if exists
        getattr(att, "stored_name", None),
        getattr(att, "stored_path", None),
        getattr(att, "path", None),
        getattr(att, "file_path", None),
        getattr(att, "filepath", None),
        getattr(att, "filename", None),
        getattr(att, "original_name", None),
    ]
    rel_names = [str(x).strip() for x in rel_names if x]

    # Primary roots (most specific first)
    roots: list[Path] = []
    try:
        up = current_app.config.get("UPLOAD_FOLDER", "")
        if up:
            roots.append(Path(up))
    except Exception:
        pass

    app_root = Path(current_app.root_path)
    proj_root = app_root.parent  # project dir containing `app/`
    roots += [
        app_root / "uploads",
        app_root / "static" / "uploads",
        Path(current_app.instance_path) / "uploads",
        proj_root / "uploads",
        proj_root,  # last resort: project root (for recursive search)
    ]

    # Variants commonly used
    def variants(base: Path) -> list[Path]:
        return [base, base / "attachments", base / "files", base / "media"]

    root_variants: list[Path] = []
    for r in roots:
        root_variants += variants(r)

    # 1) Any absolute that already exists?
    for name in rel_names:
        p = Path(name)
        if p.is_absolute() and p.exists():
            return str(p)

    # 2) Direct join with roots
    for base in root_variants:
        for name in rel_names:
            if not name:
                continue
            p = base / name
            if p.exists():
                return str(p)

    # 3) Fallback name guesses: id_filename and raw filename
    att_id = getattr(att, "id", None)
    fn = (getattr(att, "filename", None) or getattr(att, "original_name", None) or "").strip()
    fallback_names = []
    if att_id and fn:
        fallback_names += [f"{att_id}_{fn}", fn]
    elif fn:
        fallback_names += [fn]

    for base in root_variants:
        for name in fallback_names:
            p = base / name
            if p.exists():
                return str(p)

    # 4) LAST RESORT: recursive search for stored_name/filename under likely roots
    try:
        to_find = [x for x in [
            getattr(att, "stored_name", None),
            getattr(att, "filename", None),
            getattr(att, "original_name", None),
        ] if x]

        seen: set[str] = set()
        for base in root_variants:
            if not base.exists():
                continue
            # guard against enormous trees by skipping if we've already searched this absolute path
            bstr = str(base.resolve())
            if bstr in seen:
                continue
            seen.add(bstr)
            for needle in to_find:
                try:
                    for hit in base.rglob(needle):
                        if hit.is_file():
                            return str(hit)
                except Exception:
                    # ignore permission/IO errors and continue
                    pass
    except Exception:
        pass

    # Diagnostics
    try:
        current_app.logger.warning(
            "Attachment path not found. att.id=%s fields=%r probed_roots=%r",
            getattr(att, "id", None),
            {
                "absolute_path": getattr(att, "absolute_path", None),
                "stored_name": getattr(att, "stored_name", None),
                "stored_path": getattr(att, "stored_path", None),
                "path": getattr(att, "path", None),
                "file_path": getattr(att, "file_path", None),
                "filepath": getattr(att, "filepath", None),
                "filename": getattr(att, "filename", None),
                "original_name": getattr(att, "original_name", None),
                "content_type": getattr(att, "content_type", None),
            },
            [str(r) for r in root_variants],
        )
    except Exception:
        pass

    return None


def _is_office_like(att) -> bool:
    name = (getattr(att, "original_name", None) or getattr(att, "filename", "") or "")
    ext = Path(name).suffix.lower()
    if ext in OFFICE_EXTS:
        return True
    ctype = (getattr(att, "content_type", None) or "").lower()
    if any(k in ctype for k in ("msword", "officedocument", "ms-excel", "ms-powerpoint", "vnd.oasis.opendocument")):
        return True
    return False

def _ensure_pdf_preview(att) -> tuple[str | None, str | None]:
    """
    Convert Office docs to PDF using LibreOffice (headless), cached at <UPLOAD_FOLDER>/previews/<att.id>.pdf.
    ALWAYS returns (pdf_path, error_text).
    """
    try:
        current_app.logger.info("PLAN_PREVIEW: USING_WORKDIR_CONVERTER for att.id=%s", getattr(att, "id", None))

        if not _is_office_like(att):
            return (None, "not-office")

        upload_root = Path(_upload_root())
        upload_root.mkdir(parents=True, exist_ok=True)
        previews_dir = upload_root / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)

        src_real = _resolve_attachment_abs_path(att)
        if not src_real or not os.path.exists(src_real):
            return (None, f"source-missing: {src_real!r}")

        out_pdf = previews_dir / f"{att.id}.pdf"
        try:
            if out_pdf.exists() and out_pdf.stat().st_size > 800 and os.path.getmtime(out_pdf) >= os.path.getmtime(src_real):
                return (str(out_pdf), None)
        except Exception:
            pass

        soffice = _find_soffice()
        if not soffice:
            return (None, "LibreOffice 'soffice' not found. Set LIBREOFFICE_PATH or add to PATH.")

        # copy to safe ASCII/no-space work dir
        work_dir = _lo_workdir()
        work_dir.mkdir(parents=True, exist_ok=True)

        want_ext = _guess_office_ext(att)
        safe_base = f"att_{att.id}_{uuid.uuid4().hex}"
        temp_src = work_dir / f"{safe_base}{want_ext}"
        try:
            shutil.copyfile(src_real, temp_src)
        except Exception as e:
            return (None, f"temp-copy-failed: {e!r}")

        # prefer short 8.3 paths on Windows
        src_for_lo = _short_path(str(temp_src))
        outdir_for_lo = _short_path(str(work_dir))

        # per-run LO profile
        lo_profile_dir = work_dir / f"lo_profile_{os.getpid()}_{uuid.uuid4().hex}"
        lo_profile_dir.mkdir(parents=True, exist_ok=True)
        lo_profile_uri = "file:///" + str(lo_profile_dir).replace("\\", "/")

        env = os.environ.copy()
        if os.name == "nt":
            env["HOME"] = str(work_dir)
            env["TMP"] = str(work_dir)
            env["TEMP"] = str(work_dir)

        cmd = [
            soffice,
            "--headless", "--nologo", "--nofirststartwizard",
            "--nodefault", "--nolockcheck", "--norestore",
            f"-env:UserInstallation={lo_profile_uri}",
            "--convert-to", "pdf",
            "--outdir", outdir_for_lo,
            src_for_lo,
        ]
        current_app.logger.info("LibreOffice convert (cwd=%s): %s", work_dir, " ".join(cmd))

        startupinfo = None
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo = si

        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(current_app.config.get("LIBREOFFICE_TIMEOUT", 90)),
            check=False,
            env=env,
            startupinfo=startupinfo,
            cwd=str(work_dir),
        )
        out = res.stdout.decode(errors="ignore")
        err = res.stderr.decode(errors="ignore")

        generated = work_dir / f"{Path(src_for_lo).with_suffix('.pdf').name}"

        if res.returncode != 0:
            msg = (f"LibreOffice rc={res.returncode}\n"
                   f"soffice: {soffice}\n"
                   f"src_for_lo: {src_for_lo}\n"
                   f"outdir: {outdir_for_lo}\n"
                   f"cwd: {work_dir}\n"
                   f"STDOUT:\n{out}\n\nSTDERR:\n{err}\n")
            current_app.logger.error(msg)
            try: shutil.rmtree(lo_profile_dir, ignore_errors=True)
            except Exception: pass
            try: temp_src.unlink(missing_ok=True)
            except Exception: pass
            return (None, msg)

        # copy to cache as <id>.pdf
        try:
            if generated.exists():
                if out_pdf.exists():
                    out_pdf.unlink(missing_ok=True)
                shutil.copyfile(generated, out_pdf)
        except Exception as e:
            return (None, f"move-failed: {e!r}")

        # cleanup
        try: shutil.rmtree(lo_profile_dir, ignore_errors=True)
        except Exception: pass
        try: temp_src.unlink(missing_ok=True)
        except Exception: pass
        try: generated.unlink(missing_ok=True)
        except Exception: pass

        if out_pdf.exists() and out_pdf.stat().st_size > 800:
            return (str(out_pdf), None)

        return (None, "Converted PDF missing or empty.")
    except Exception as e:
        current_app.logger.exception("Unexpected error in _ensure_pdf_preview")
        return (None, f"unexpected-error: {e!r}")


def _find_soffice() -> str | None:
    """
    Locate LibreOffice 'soffice' binary using config, PATH, or common locations.
    """
    # 0) Config override
    cfg = current_app.config.get("LIBREOFFICE_PATH")
    if cfg and Path(cfg).exists():
        return str(Path(cfg))

    # 1) PATH
    exe = shutil.which("soffice")
    if exe:
        return exe

    # 2) Windows common installs
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    # 3) macOS Homebrew (sometimes)
    macs = ["/usr/local/bin/soffice", "/opt/homebrew/bin/soffice"]
    for c in macs:
        if Path(c).exists():
            return c

    return None

def _send_inline_file(path: str, mime: str, filename: str):
    resp = send_file(
        path,
        mimetype=(mime or "application/octet-stream"),
        as_attachment=False,
        download_name=filename,
        conditional=True,
        max_age=0,
        etag=True,
        last_modified=None,
    )
    disp_name = filename.replace('"', '\\"')
    resp.headers["Content-Disposition"] = f'inline; filename="{disp_name}"; filename*=UTF-8\'\'{disp_name}'
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp

def _norm(s):
    try:
        return str(s).strip().casefold()
    except Exception:
        return str(s).strip().lower()

DIRECTOR_NAMES = {
    "director", "manager", "lead",
    "директор", "менаџер", "раководител", "руководител",
}

def _utcnow():
    return datetime.utcnow()

def _has_role_name(user, names_set=DIRECTOR_NAMES):
    r = getattr(user, "role", None)
    if r and getattr(r, "name", None):
        if _norm(r.name) in names_set:
            return True
    roles = getattr(user, "roles", None)
    if roles:
        for rr in roles:
            nm = getattr(rr, "name", None)
            if nm and _norm(nm) in names_set:
                return True
    if hasattr(user, "has_role"):
        for nm in names_set:
            try:
                if user.has_role(nm):
                    return True
            except Exception:
                pass
    return False

def _has_director_permissions(user):
    for attr in ("can_review", "can_approve", "can_manage_plan"):
        if getattr(user, attr, False):
            return True
    perms = getattr(user, "permissions", None)
    if isinstance(perms, (list, tuple, set)):
        perms_norm = {_norm(p) for p in perms}
        if {"plan:review", "plan:approve", "plan:manage"} & perms_norm:
            return True
    return False

def is_director(user) -> bool:
    if getattr(user, "is_director", False):
        return True
    if _has_role_name(user):
        return True
    if _has_director_permissions(user):
        return True
    if getattr(user, "is_admin", False) or _norm(getattr(getattr(user, "role", None), "name", "")) == "admin":
        return True
    return False

def _user_name(u):
    if not u:
        return "—"
    full = getattr(u, "full_name", None)
    if full:
        return full
    parts = f"{(u.first_name or '').strip()} {(u.last_name or '').strip()}".strip()
    return parts or (u.username or u.email or "—")

def director_department_ids(user):
    ids = []
    if getattr(user, "department_id", None):
        ids.append(user.department_id)
    if hasattr(user, "departments"):
        try:
            for d in user.departments:
                ids.append(d.id)
        except Exception:
            pass
    return [i for i in ids if i]

def ensure_task_visible_to_user(task, user) -> bool:
    if is_director(user):
        return (task.department_id in director_department_ids(user))
    return (task.owner_user_id == user.id)

# ======================
# Attachment preview helpers
# ======================


def _safe_url(endpoint, **values):
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return None



@bp.route("/preview/<int:att_id>")
@login_required
def preview_attachment(att_id: int):
    att = Attachment.query.get_or_404(att_id)

    # Office => PDF conversion then inline
    if _is_office_like(att):
        pdf_path, err = _ensure_pdf_preview(att)
        if pdf_path and os.path.exists(pdf_path):
            return _send_inline_file(pdf_path, "application/pdf", Path(pdf_path).name)
        return Response(err or "Conversion failed.", 500, {"Content-Type": "text/plain; charset=utf-8"})

    # Non-office: stream original inline
    src = _resolve_attachment_abs_path(att)
    if src and os.path.exists(src):
        ctype = (getattr(att, "content_type", None) or mimetypes.guess_type(src)[0] or "").lower()
        name  = getattr(att, "filename", None) or getattr(att, "original_name", None) or Path(src).name
        return _send_inline_file(src, ctype or "application/octet-stream", name)

    # Fallback: redirect to download if available
    dl = _safe_url("attachments.download", att_id=att_id)
    if dl:
        return redirect(dl, code=302)
    abort(404)





# IMPORTANT: single source of truth for URLs (no duplicate definitions)
def attachment_json(a):
    return {
        "id": a.id,
        "filename": a.filename,
        "inline_url":  url_for("plan.preview_attachment", att_id=a.id),
        "download_url": _safe_url("attachments.download", att_id=a.id) or url_for("plan.preview_attachment", att_id=a.id),
    }


def comment_json(c):
    atts = c.attachments.all() if hasattr(c.attachments, "all") else (c.attachments or [])
    return {
        "id": c.id,
        "author_id": c.author_id,
        "author_name": _user_name(c.author),
        "text": c.text or "",
        "is_system": bool(c.is_system),
        "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
        "attachments": [attachment_json(a) for a in atts],
    }

def _save_upload_fs(file_storage, uploaded_by_user_id):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    upload_root = _upload_root()
    os.makedirs(upload_root, exist_ok=True)

    original = secure_filename(file_storage.filename)
    ts = _utcnow().strftime("%Y%m%d%H%M%S%f")
    stored = f"{ts}_{original}" if original else ts
    abs_path = os.path.join(upload_root, stored)
    file_storage.save(abs_path)

    att = Attachment()
    if hasattr(att, "filename"): att.filename = original or stored
    if hasattr(att, "original_name"): att.original_name = original or stored
    if hasattr(att, "stored_name"): att.stored_name = stored
    if hasattr(att, "path"): att.path = stored
    if hasattr(att, "content_type"): att.content_type = getattr(file_storage, "mimetype", None)
    if hasattr(att, "user_id"): att.user_id = uploaded_by_user_id
    if hasattr(att, "uploaded_at"): att.uploaded_at = _utcnow()

    db.session.add(att)
    db.session.flush()
    return att

# ======================
# Views
# ======================

@bp.route("/panel")
@login_required
def panel():
    role = "director" if is_director(current_user) else "user"
    if request.headers.get("X-Requested-With") in ("fetch", "XMLHttpRequest"):
        return render_template("plan.html", role=role)
    return render_template("dashboard.html", initial_panel="plan")

@bp.route("/api/whoami")
@login_required
def api_whoami():
    is_dir = is_director(current_user)
    return jsonify({
        "role": "director" if is_dir else "user",
        "user_id": current_user.id,
        "department_ids": director_department_ids(current_user) if is_dir else [],
        "debug": {
            "is_director_flag": bool(getattr(current_user, "is_director", False)),
            "role_name": getattr(getattr(current_user, "role", None), "name", None),
            "roles": [getattr(r, "name", None) for r in getattr(current_user, "roles", [])] if hasattr(current_user, "roles") else None,
            "permissions": list(getattr(current_user, "permissions", []) or []),
            "is_admin": bool(getattr(current_user, "is_admin", False)),
        }
    })

@bp.route("/api/week")
@login_required
def api_week():
    if not is_director(current_user):
        abort(403)

    start_str = request.args.get("start")
    days = int(request.args.get("days", 7))
    if not start_str:
        today = datetime.now(TZ).date()
        monday = today - timedelta(days=today.weekday())
        start = monday
    else:
        start = date.fromisoformat(start_str)
    end = start + timedelta(days=days - 1)

    dept_ids = director_department_ids(current_user)
    if not dept_ids:
        return jsonify({"users": [], "tasks": []})

    users = (
        User.query
        .filter(User.department_id.in_(dept_ids))
        .order_by(User.first_name, User.last_name)
        .all()
    )
    user_rows = [{"id": u.id, "name": f"{u.first_name} {u.last_name}"} for u in users]

    tasks = (
        PlanTask.query
        .filter(PlanTask.department_id.in_(dept_ids))
        .filter(PlanTask.deleted_at.is_(None))
        .filter(PlanTask.start_date <= end, PlanTask.due_date >= start)
        .all()
    )

    def tjson(t: PlanTask):
        return {
            "id": t.id,
            "title": t.title,
            "description": t.description or "",
            "owner_user_id": t.owner_user_id,
            "director_id": t.director_id,
            "department_id": t.department_id,
            "start_date": t.start_date.isoformat(),
            "due_date": t.due_date.isoformat(),
            "status": t.status.value,
            "priority": t.priority.value if t.priority else None,
        }

    return jsonify({
        "start": start.isoformat(),
        "end": end.isoformat(),
        "users": user_rows,
        "tasks": [tjson(t) for t in tasks],
    })

# Make sure 'request' is imported at top (you already have it)
# from flask import request

@bp.after_app_request
def _plan_preview_headers(resp):
    p = (request.path or "") if hasattr(request, "path") else ""
    if p.startswith("/plan/preview/"):
        # Allow embedding our own preview
        if resp.headers.get("X-Frame-Options", "").upper() == "DENY":
            resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        # Minimal CSP if none present (merge with your own if you already set CSP elsewhere)
        if "Content-Security-Policy" not in resp.headers:
            resp.headers["Content-Security-Policy"] = "frame-ancestors 'self'; frame-src 'self' blob: data:;"
        # Be explicit about inline
        resp.headers.setdefault("Content-Disposition", "inline")
    return resp




@bp.route("/api/task", methods=["POST"])
@login_required
def api_task_create():
    if not is_director(current_user):
        abort(403)

    fm = request.form
    title = (fm.get("title") or "").strip()
    owner_user_id = (fm.get("owner_user_id") or "").strip()
    start_date_raw = (fm.get("start_date") or "").strip()
    due_date_raw   = (fm.get("due_date") or "").strip() or start_date_raw
    description = (fm.get("description") or "").strip()
    priority_in = (fm.get("priority") or "").strip().lower() or None

    if not title:
        return jsonify(error="Title is required."), 400
    if not owner_user_id.isdigit():
        return jsonify(error="Assignee (owner_user_id) is required."), 400
    if not start_date_raw:
        return jsonify(error="Start date is required."), 400

    try:
        start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        due_date   = datetime.strptime(due_date_raw,   "%Y-%m-%d").date()
    except ValueError:
        return jsonify(error="Dates must be in YYYY-MM-DD format."), 400

    priority = None
    if priority_in in {"low", "medium", "high"}:
        priority = getattr(TaskPriority, priority_in.upper())

    try:
        t = PlanTask(
            title=title,
            description=description or None,
            owner_user_id=int(owner_user_id),
            director_id=current_user.id,
            department_id=getattr(current_user, "department_id", None),
            start_date=start_date,
            due_date=due_date,
            status=TaskStatus.ASSIGNED,
            priority=priority
        )
    except Exception as e:
        return jsonify(error=f"Failed to initialize PlanTask: {e}"), 400

    db.session.add(t)
    db.session.flush()

    files = request.files.getlist("files[]") if request.files else []
    for f in files:
        if not f or not f.filename:
            continue
        try:
            saver = getattr(Attachment, "save_upload", None)
            if callable(saver):
                att = saver(f, current_user.id)
            else:
                att = _save_upload_fs(f, current_user.id)
            if att is not None:
                t.attachments.append(att)
        except Exception as e:
            current_app.logger.warning("Attachment save failed: %s", e)

    t.activities.append(PlanActivity.make(t.id, current_user.id, "create", {
        "title": title,
        "owner_user_id": int(owner_user_id),
        "start_date": start_date_raw,
        "due_date": due_date_raw,
        "priority": priority_in or None
    }))

    db.session.commit()
    return jsonify({"ok": True, "id": t.id})

@bp.route("/api/task/<int:task_id>", methods=["GET"])
@login_required
def api_task_get(task_id):
    t = PlanTask.query.get_or_404(task_id)

    if current_user.id not in {t.director_id, t.owner_user_id}:
        return jsonify(error="Forbidden"), 403

    task_atts = t.attachments.all() if hasattr(t.attachments, "all") else (t.attachments or [])
    comments_q = t.comments.order_by(PlanComment.created_at.asc())
    comments = comments_q.all() if hasattr(comments_q, "all") else list(comments_q)

    role = "director" if current_user.id == t.director_id else "user"

    return jsonify({
        "id": t.id,
        "title": t.title,
        "description": t.description or "",
        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
        "priority": (t.priority.value if getattr(t, "priority", None) else None),
        "start_date": t.start_date.strftime("%Y-%m-%d"),
        "due_date": t.due_date.strftime("%Y-%m-%d"),
        "owner_id": t.owner_user_id,
        "owner_name": _user_name(t.owner),
        "director_id": t.director_id,
        "director_name": _user_name(t.director),
        "attachments": [attachment_json(a) for a in task_atts],
        "comments": [comment_json(c) for c in comments],
        "viewer_role": role,
    })

@bp.route("/api/kanban")
@login_required
def api_kanban():
    tasks = (
        PlanTask.query
        .filter(PlanTask.owner_user_id == current_user.id)
        .filter(PlanTask.deleted_at.is_(None))
        .order_by(PlanTask.due_date.asc(), PlanTask.created_at.asc())
        .all()
    )

    buckets = {
        "assigned": [],
        "in_progress": [],
        "under_review": [],
        "returned": [],
        "completed": [],
    }
    for t in tasks:
        key = t.status.value
        payload = {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.isoformat(),
            "start_date": t.start_date.isoformat(),
            "director_name": f"{t.director.first_name} {t.director.last_name}",
            "department_id": t.department_id,
            "priority": t.priority.value if t.priority else None,
            "comments_count": t.comments.count(),
            "attachments_count": t.attachments.count(),
            "status": key,
        }
        if key in buckets:
            buckets[key].append(payload)
        elif key == TaskStatus.APPROVED.value:
            buckets["completed"].append(payload)

    return jsonify(buckets)

@bp.route("/api/task/<int:task_id>/status", methods=["POST"])
@login_required
def api_task_status(task_id):
    t = PlanTask.query.get_or_404(task_id)
    if not ensure_task_visible_to_user(t, current_user):
        abort(403)

    data = request.json or request.form or {}
    action = (data.get("action") or "").strip()
    comment_text = (data.get("comment") or "").strip()

    if current_user.id == t.owner_user_id:
        if action == "start" and t.status == TaskStatus.ASSIGNED:
            t.status = TaskStatus.IN_PROGRESS
            db.session.add(PlanActivity.make(t.id, current_user.id, "start", {}))
        elif action == "submit" and t.status == TaskStatus.IN_PROGRESS:
            if not comment_text:
                return jsonify({"error": "Comment is required on submit."}), 400
            t.status = TaskStatus.UNDER_REVIEW
            c = PlanComment(task_id=t.id, author_id=current_user.id, text=comment_text, is_system=False)
            db.session.add(c)
            db.session.add(PlanActivity.make(t.id, current_user.id, "submit", {"comment": True}))
        elif action == "restart" and t.status == TaskStatus.RETURNED:
            t.status = TaskStatus.IN_PROGRESS
            db.session.add(PlanActivity.make(t.id, current_user.id, "restart", {}))
        else:
            return jsonify({"error": "Invalid status transition."}), 400

        db.session.commit()
        return jsonify({"ok": True, "status": t.status.value})

    if is_director(current_user):
        if t.department_id not in director_department_ids(current_user):
            abort(403)
        if action == "approve" and t.status == TaskStatus.UNDER_REVIEW:
            t.status = TaskStatus.APPROVED
            db.session.add(PlanActivity.make(t.id, current_user.id, "approve", {}))
        elif action == "deny" and t.status == TaskStatus.UNDER_REVIEW:
            if not comment_text:
                return jsonify({"error": "Note is required on denial."}), 400
            t.status = TaskStatus.DENIED
            c = PlanComment(task_id=t.id, author_id=current_user.id, text=comment_text, is_system=False)
            db.session.add(c)
            db.session.add(PlanActivity.make(t.id, current_user.id, "deny", {"note": True}))
            t.status = TaskStatus.RETURNED
        else:
            return jsonify({"error": "Invalid status transition."}), 400

        db.session.commit()
        return jsonify({"ok": True, "status": t.status.value})

    abort(403)

@bp.route("/api/review")
@login_required
def api_review():
    if not is_director(current_user):
        abort(403)

    dept_ids = director_department_ids(current_user)
    q = (
        PlanTask.query
        .filter(PlanTask.department_id.in_(dept_ids))
        .filter(PlanTask.deleted_at.is_(None))
        .filter(PlanTask.status == TaskStatus.UNDER_REVIEW)
        .order_by(PlanTask.updated_at.desc())
    )

    items = []
    for t in q.all():
        items.append({
            "id": t.id,
            "title": t.title,
            "owner_user_id": t.owner_user_id,
            "owner_name": f"{t.owner.first_name} {t.owner.last_name}",
            "start_date": t.start_date.isoformat(),
            "due_date": t.due_date.isoformat(),
            "priority": t.priority.value if t.priority else None,
            "comments_count": t.comments.count(),
            "attachments_count": t.attachments.count(),
        })
    return jsonify({"items": items})

@bp.route("/api/task/<int:task_id>/delete", methods=["POST"])
@login_required
def api_task_delete(task_id):
    if not is_director(current_user):
        abort(403)
    t = PlanTask.query.get_or_404(task_id)
    if t.department_id not in director_department_ids(current_user):
        abort(403)
    t.soft_delete(current_user.id)
    db.session.commit()
    return jsonify({"ok": True})

@bp.route("/api/task/<int:task_id>/restore", methods=["POST"])
@login_required
def api_task_restore(task_id):
    if not is_director(current_user):
        abort(403)
    t = PlanTask.query.get_or_404(task_id)
    if t.department_id not in director_department_ids(current_user):
        abort(403)
    t.restore(current_user.id)
    db.session.commit()
    return jsonify({"ok": True})

@bp.route("/api/comment", methods=["POST"])
@login_required
def api_comment():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        task_id = int(data.get("task_id", 0))
        text = (data.get("text") or "").strip()
        files = []
    else:
        task_id = int((request.form.get("task_id") or "0"))
        text = (request.form.get("text") or "").strip()
        files = request.files.getlist("files[]") if request.files else []

    if not task_id or not text:
        return jsonify({"error": "Missing fields."}), 400

    t = PlanTask.query.get_or_404(task_id)
    if not ensure_task_visible_to_user(t, current_user):
        abort(403)

    c = PlanComment(task_id=task_id, author_id=current_user.id, text=text, is_system=False)
    db.session.add(c)
    db.session.flush()

    for f in files:
        if not f or not f.filename:
            continue
        try:
            att = Attachment.save_upload(f, current_user.id)
            if att:
                c.attachments.append(att)
        except Exception as e:
            current_app.logger.warning("Comment attachment save failed: %s", e)

    db.session.add(PlanActivity.make(t.id, current_user.id, "comment", {"has_files": bool(files)}))
    db.session.commit()

    atts = c.attachments.all() if hasattr(c.attachments, "all") else (c.attachments or [])
    return jsonify({
        "ok": True,
        "comment": {
            "id": c.id,
            "author_id": c.author_id,
            "author_name": _user_name(c.author),
            "text": c.text or "",
            "is_system": bool(c.is_system),
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
            "attachments": [attachment_json(a) for a in atts],
        }
    })

@bp.route("/api/task/<int:task_id>/submit", methods=["POST"])
@login_required
def api_task_submit(task_id):
    t = PlanTask.query.get_or_404(task_id)
    if current_user.id != t.owner_user_id:
        return jsonify(error="Forbidden"), 403
    if t.status not in (TaskStatus.IN_PROGRESS,):
        return jsonify(error="Task is not in progress."), 400

    comment_text = (request.form.get("comment") or "").strip()
    if not comment_text:
        return jsonify(error="Comment is required."), 400

    c = PlanComment(task_id=t.id, author_id=current_user.id, text=comment_text, is_system=False)
    db.session.add(c)
    db.session.flush()

    files = request.files.getlist("files[]") if request.files else []
    for f in files:
        if not f or not f.filename:
            continue
        try:
            saver = getattr(Attachment, "save_upload", None)
            if callable(saver):
                att = saver(f, current_user.id)
            else:
                att = _save_upload_fs(f, current_user.id)
            if att:
                c.attachments.append(att)
        except Exception as e:
            current_app.logger.warning("submit attachment failed: %s", e)

    t.status = TaskStatus.UNDER_REVIEW
    t.activities.append(PlanActivity.make(t.id, current_user.id, "submit", {
        "comment": True,
        "when": _utcnow().isoformat()
    }))
    db.session.commit()
    return jsonify({"ok": True})
