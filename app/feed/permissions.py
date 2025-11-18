from typing import Iterable
from flask_login import current_user
from sqlalchemy.orm import Query
from app.extensions import db
from .models import FeedPost

def _user_sector_ids() -> set[int]:
    sids = set()
    sid = getattr(current_user, "sector_id", None)
    if sid: sids.add(int(sid))
    maybe_many: Iterable = getattr(current_user, "sector_ids", []) or []
    try:
        for s in maybe_many:
            sids.add(int(getattr(s, "id", s)))
    except Exception:
        pass
    return sids

def feed_queryset_for_current_user(q: Query) -> Query:
    role = getattr(current_user, "role", "user")
    if role == "admin":
        return q.filter(FeedPost.is_deleted.is_(False))

    sids = _user_sector_ids()
    return q.filter(FeedPost.is_deleted.is_(False)).filter(
        db.or_(
            FeedPost.audience_type == "all",
            db.and_(FeedPost.audience_type == "sector", FeedPost.audience_id.in_(sids if sids else [-1])),
            db.and_(FeedPost.audience_type == "users", FeedPost.allowed_users.any(id=current_user.id)),
        )
    )

def can_manage_post(post: FeedPost) -> bool:
    role = getattr(current_user, "role", "user")
    if role == "admin": return True
    if role == "director": return post.author_id == current_user.id
    return post.author_id == current_user.id

def can_view_post(post: FeedPost) -> bool:
    if post.is_deleted: return False
    role = getattr(current_user, "role", "user")
    if role == "admin": return True
    if post.audience_type == "all": return True
    if post.audience_type == "sector":
        return post.audience_id in _user_sector_ids()
    if post.audience_type == "users":
        return any(u.id == current_user.id for u in post.allowed_users)
    return False
