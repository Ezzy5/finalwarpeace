# app/feed/routes/util_cursor_decode.py
from __future__ import annotations
from typing import Tuple
from datetime import datetime

def _cursor_decode(cur: str | None) -> Tuple[datetime | None, int | None]:
    if not cur:
        return None, None
    try:
        ts_str, id_str = cur.split(".", 1)
        ms = int(ts_str)
        dt = datetime.utcfromtimestamp(ms / 1000.0)
        pid = int(id_str)
        return dt, pid
    except Exception:
        return None, None
