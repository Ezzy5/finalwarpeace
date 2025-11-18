# app/users/routes/templates_store.py
from __future__ import annotations
import os
import uuid
from typing import Optional, Dict, Any, List
from flask import current_app
from werkzeug.utils import secure_filename

# NOTE: Replace these stubs if you already persist templates in DB.
# Here we keep a tiny in-memory store + JSON file on disk for simplicity.
# If you already have a Template model, adapt these functions accordingly.

_JSON_PATH = lambda: os.path.join(current_app.instance_path, "templates", "agreements", "_templates.json")
_MEMORY: Dict[int, Dict[str, Any]] = {}
_NEXT_ID = 1

def _load() -> None:
    global _MEMORY, _NEXT_ID
    try:
        import json
        with open(_JSON_PATH(), "r", encoding="utf-8") as f:
            data = json.load(f)
        _MEMORY = {int(k): v for k, v in data.get("items", {}).items()}
        _NEXT_ID = int(data.get("next_id", 1))
    except Exception:
        _MEMORY, _NEXT_ID = {}, 1

def _save() -> None:
    os.makedirs(os.path.dirname(_JSON_PATH()), exist_ok=True)
    try:
        import json
        with open(_JSON_PATH(), "w", encoding="utf-8") as f:
            json.dump({"items": _MEMORY, "next_id": _NEXT_ID}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _ensure_loaded():
    if not _MEMORY:
        _load()

def list_templates() -> List[Dict[str, Any]]:
    _ensure_loaded()
    items = list(_MEMORY.values())
    # Small helpful sort: DOCX first
    items.sort(key=lambda x: (x.get("type") != "docx", (x.get("name") or "").lower()))
    return items

def get_template_by_id(tid: int) -> Optional[Dict[str, Any]]:
    _ensure_loaded()
    return _MEMORY.get(int(tid))

def _save_docx_file(upload_file) -> str:
    """Save uploaded DOCX into AGREEMENT_TEMPLATES_DIR and return stored filename."""
    base_dir = current_app.config["AGREEMENT_TEMPLATES_DIR"]
    os.makedirs(base_dir, exist_ok=True)
    orig = secure_filename(upload_file.filename or "template.docx")
    if not orig.lower().endswith(".docx"):
        orig += ".docx"
    stored = f"{uuid.uuid4().hex}_{orig}"
    upload_file.save(os.path.join(base_dir, stored))
    return stored

def create_template(name: str, ttype: str, description: str = "", content: str = "", file=None) -> Dict[str, Any]:
    """
    - If ttype == 'docx', provide 'file' (werkzeug FileStorage).
    - If ttype == 'html', provide 'content' as HTML string.
    """
    _ensure_loaded()
    global _NEXT_ID
    rec = {
        "id": _NEXT_ID,
        "name": name,
        "type": (ttype or "docx").lower(),
        "description": description or "",
        # For docx we store the uploaded file name; for html we store the content
        "file_stored_name": None,
        "content": None,
    }
    if rec["type"] == "docx":
        if not file:
            raise ValueError("DOCX template requires a .docx file upload")
        rec["file_stored_name"] = _save_docx_file(file)
    else:
        rec["type"] = "html"
        rec["content"] = content or ""

    _MEMORY[_NEXT_ID] = rec
    _NEXT_ID += 1
    _save()
    return rec

def update_template(tid: int, name: Optional[str] = None, ttype: Optional[str] = None,
                    description: Optional[str] = None, content: Optional[str] = None, file=None) -> Optional[Dict[str, Any]]:
    _ensure_loaded()
    rec = _MEMORY.get(int(tid))
    if not rec:
        return None

    if name is not None:
        rec["name"] = name
    if description is not None:
        rec["description"] = description

    # type switches are allowed: if switching to docx, we need a file; if to html, we need content.
    if ttype:
        ttype = ttype.lower()
        if ttype not in ("docx", "html"):
            ttype = "docx"
        rec["type"] = ttype

    if rec["type"] == "docx":
        # You can replace file if provided; otherwise keep old file
        if file:
            rec["file_stored_name"] = _save_docx_file(file)
        # clear content
        rec["content"] = None
    else:
        # HTML template
        if content is not None:
            rec["content"] = content
        rec["file_stored_name"] = None

    _save()
    return rec

def delete_template(tid: int) -> bool:
    _ensure_loaded()
    rec = _MEMORY.pop(int(tid), None)
    _save()
    return bool(rec)
