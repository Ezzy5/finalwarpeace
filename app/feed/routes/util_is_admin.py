# app/feed/routes/util_is_admin.py
from __future__ import annotations
from app.models import User  # noqa: F401

def _is_admin(u: "User") -> bool:
    return bool(getattr(u, "is_admin", False) or getattr(u, "is_superuser", False))
