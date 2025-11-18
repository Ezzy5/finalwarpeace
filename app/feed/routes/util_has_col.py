# app/feed/routes/util_has_col.py
from __future__ import annotations

def _has_col(model, name: str) -> bool:
    try:
        return hasattr(model, name) or (name in model.__table__.columns)  # type: ignore[attr-defined]
    except Exception:
        return hasattr(model, name)
