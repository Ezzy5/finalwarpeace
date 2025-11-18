# app/uploader/storage.py
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from flask import current_app
from werkzeug.utils import secure_filename

# Try Pillow for thumbnails (optional). If not installed, previews fall back to original.
try:
    from PIL import Image  # type: ignore
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


def _cfg(key: str, default: str | int | None = None):
    return current_app.config.get(key, default)


def get_upload_root() -> Path:
    """
    Disk root where files are stored.
    Defaults to '<project_root>/uploads'.
    Override with app.config['UPLOAD_ROOT'] (absolute path).
    """
    root = _cfg("UPLOAD_ROOT")
    if root:
        p = Path(root)
    else:
        # project root (two levels up from app folder)
        p = Path(current_app.root_path).parent / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_public_base() -> str:
    """
    Public URL prefix that serves uploaded files.
    We serve with our own blueprint route '/u/<path>'.
    """
    return _cfg("UPLOAD_URL_PREFIX", "/u")


def date_slug() -> str:
    return datetime.utcnow().strftime("%Y/%m/%d")


def allowed_mime(filename: str, content_type: str | None) -> bool:
    # Keep it pragmatic; tighten if needed.
    whitelist = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain"
    }
    if content_type in whitelist:
        return True
    # small fallback: detect by extension
    ext = (filename.rsplit(".", 1)[-1] or "").lower()
    return ext in {"jpg", "jpeg", "png", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"}


def _gen_name(filename: str) -> str:
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    return f"{uuid.uuid4().hex}{ext}"


def _maybe_fix_image_extension(abs_path: Path) -> Path:
    """
    If file has no extension and we have Pillow, try to detect format and append one.
    Safe no-op otherwise.
    """
    if abs_path.suffix:
        return abs_path
    if not _HAS_PIL:
        return abs_path
    try:
        with Image.open(abs_path) as im:
            fmt = (im.format or "").lower()
        if not fmt:
            return abs_path
        # map a few common values to preferred extensions
        ext = {
            "jpeg": ".jpg",
            "jpg": ".jpg",
            "png": ".png",
            "gif": ".gif",
            "webp": ".webp",
            "tiff": ".tif",
            "bmp": ".bmp",
        }.get(fmt, f".{fmt}")
        new_path = abs_path.with_suffix(ext)
        abs_path.rename(new_path)
        return new_path
    except Exception:
        return abs_path


def save_file(file_storage, subdir: str = "feed") -> Tuple[Path, str]:
    """
    Save a Werkzeug FileStorage to disk and return (abs_path, public_url).
    Creates date-based subfolders: <root>/<subdir>/<YYYY>/<MM>/<DD>/<filename>
    """
    fname = secure_filename(file_storage.filename or "file")
    ct = file_storage.mimetype or ""
    if not allowed_mime(fname, ct):
        raise ValueError("File type not allowed")

    root = get_upload_root()
    ds = date_slug()
    rel_dir = Path(subdir) / ds
    abs_dir = root / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    final_name = _gen_name(fname)
    abs_path = abs_dir / final_name
    file_storage.save(abs_path)

    # If image and missing extension, try to detect via Pillow
    if not abs_path.suffix and (ct.startswith("image/") or _HAS_PIL):
        abs_path = _maybe_fix_image_extension(abs_path)

    public_url = f"{get_public_base().rstrip('/')}/{rel_dir.as_posix()}/{abs_path.name}"
    return abs_path, public_url


def make_thumbnail(src_path: Path, max_side: int = 512) -> Optional[Tuple[Path, str]]:
    """
    Create a JPEG thumbnail next to the original.
    Returns (abs_path, public_url) or None if not an image or Pillow missing.
    """
    if not _HAS_PIL:
        return None
    try:
        with Image.open(src_path) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side))
            thumb_name = src_path.stem + "_thumb.jpg"
            thumb_path = src_path.parent / thumb_name
            im.save(thumb_path, format="JPEG", quality=82)
        rel = thumb_path.relative_to(get_upload_root())
        public_url = f"{get_public_base().rstrip('/')}/{rel.as_posix()}"
        return thumb_path, public_url
    except Exception:
        return None
