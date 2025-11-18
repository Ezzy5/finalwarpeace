# app/feed/routes/serializers_safe_author_dict.py
from __future__ import annotations
from typing import Any, Dict

def _safe_author_dict(a: Any) -> Dict[str, Any]:
    if not a:
        return {"id": None, "full_name": "Корисник", "avatar_url": None}
    full_name = (
        getattr(a, "full_name", None)
        or getattr(a, "name", None)
        or getattr(a, "email", None)
        or "Корисник"
    )
    avatar = getattr(a, "avatar_url", None)
    aid = getattr(a, "id", None)
    return {"id": aid, "full_name": full_name, "avatar_url": avatar}
