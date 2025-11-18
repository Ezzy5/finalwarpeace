# app/feed/routes/util_static_url.py
from __future__ import annotations
from flask import url_for

def _static_url(rel_path: str) -> str:
    rel = rel_path.lstrip("/").replace("\\", "/")
    return url_for("static", filename=rel, _external=False)
