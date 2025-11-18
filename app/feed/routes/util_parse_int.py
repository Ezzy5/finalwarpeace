# app/feed/routes/util_parse_int.py
from __future__ import annotations

def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default
