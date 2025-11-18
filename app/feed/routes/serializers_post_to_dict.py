# app/feed/routes/serializers_post_to_dict.py
from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

from app.models import User  # noqa: F401
from app.feed.models import FeedPost
from app.feed.routes.serializers_safe_author_dict import _safe_author_dict
from app.feed.routes.attachments_list import _attachments_list
from app.feed.routes.reactions_reaction_count import _reaction_count
from app.feed.routes.reactions_user_reacted import _user_reacted
from app.feed.routes.comments_comment_count import _comment_count
from app.feed.routes.pins_user_pinned import _user_pinned


def _post_to_dict(
    p: "FeedPost",
    with_rel: bool = True,
    u: "User | None" = None,
) -> Dict[str, Any]:
    pid = getattr(p, "id", None) or 0
    author_id = getattr(p, "author_id", None)

    data: Dict[str, Any] = {
        "id": pid,
        "title": getattr(p, "title", "") or "",
        "html": getattr(p, "html", "") or "",
        "audience_type": getattr(p, "audience_type", "all"),
        "audience_id": getattr(p, "audience_id", None),
        "created_at": (getattr(p, "created_at", None) or datetime.utcnow()).isoformat(),
        "updated_at": (
            getattr(p, "updated_at", None)
            or getattr(p, "created_at", None)
            or datetime.utcnow()
        ).isoformat(),
        "is_deleted": bool(getattr(p, "is_deleted", False)),
    }

    # ------------------------------------------------------
    # Allowed users (permissions) for audience_type="users"
    # ------------------------------------------------------
    allowed_ids: List[int] = []
    allowed_users: List[Dict[str, Any]] = []

    if getattr(p, "audience_type", None) == "users":
        try:
            # p.allowed_users = relationship to FeedPostAllowedUser
            for rel in (getattr(p, "allowed_users", None) or []):
                uid = getattr(rel, "user_id", None)
                if uid is None:
                    continue

                try:
                    uid_int = int(uid)
                except (TypeError, ValueError):
                    continue

                # Keep unique IDs (used by backend filters / checks)
                if uid_int not in allowed_ids:
                    allowed_ids.append(uid_int)

                # ❗ UI LIST: do NOT include the author here.
                # Otherwise you get: "Creator > Creator, User1"
                if author_id is not None and uid_int == int(author_id):
                    continue

                # Build full name if we have the User
                user_obj = getattr(rel, "user", None)
                if user_obj is not None:
                    fn = (getattr(user_obj, "first_name", "") or "").strip()
                    ln = (getattr(user_obj, "last_name", "") or "").strip()
                    if fn or ln:
                        full_name = (fn + " " + ln).strip()
                    else:
                        full_name = getattr(user_obj, "email", "") or f"ID {uid_int}"
                else:
                    full_name = f"ID {uid_int}"

                # Avoid duplicates in the allowed_users output
                if not any(uo.get("id") == uid_int for uo in allowed_users):
                    allowed_users.append(
                        {
                            "id": uid_int,
                            "full_name": full_name,
                        }
                    )
        except Exception:
            # Don't break serialization if relationship is missing/broken
            allowed_ids = []
            allowed_users = []

    # Always include ID list (backend filters / checks use it)
    data["allowed_user_ids"] = allowed_ids

    # Only expose names to:
    #  - author of the post
    #  - or a user who is in the allowed list
    viewer_id = getattr(u, "id", None) if u is not None else None
    if viewer_id and (
        viewer_id == author_id
        or viewer_id in allowed_ids
    ):
        data["allowed_users"] = allowed_users
    else:
        # hide list for others (or they won't see the post anyway)
        data["allowed_users"] = []

    # ------------------------------------------------------
    # Other relations
    # ------------------------------------------------------
    if with_rel:
        data["author"] = _safe_author_dict(getattr(p, "author", None))
        data["attachments"] = _attachments_list(p)
        data["reactions_summary"] = {"👍": _reaction_count(pid)}
        data["user_reacted"] = bool(u and _user_reacted(pid, getattr(u, "id", 0)))
        data["comments_count"] = _comment_count(pid)
        data["user_pinned"] = bool(u and _user_pinned(pid, getattr(u, "id", 0)))

    return data
