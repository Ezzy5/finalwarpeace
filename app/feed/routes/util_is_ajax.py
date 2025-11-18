# app/feed/routes/util_is_ajax.py
from __future__ import annotations
from flask import request

def _is_ajax() -> bool:
    """Detect if the request is coming from the SPA loader (AJAX fetch)."""
    return request.headers.get("X-Requested-With") == "fetch"
