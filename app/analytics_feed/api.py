from flask import jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func, case
from datetime import datetime, timedelta

from app.extensions import db
from app.models import User
from app.feed.models import FeedPost, FeedComment, FeedReaction  # adjust if feed models in different module

from . import bp


def _can_view_post(p: FeedPost) -> bool:
    """Simple visibility logic consistent with the feed audience model."""
    role = getattr(current_user, "role", "user")
    if role == "admin":
        return True
    if p.audience_type == "all":
        return True
    if p.audience_type == "sector":
        return getattr(current_user, "sector_id", None) == p.audience_id
    if p.audience_type == "users":
        return current_user.id in [u.id for u in getattr(p, "allowed_users", [])]
    return False


@bp.get("/overview")
@login_required
def overview():
    """
    Returns general feed stats for the user’s visible posts within a period.
    GET /api/feed/analytics/overview?days=7
    """
    days = request.args.get("days", 7, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    posts_q = FeedPost.query.filter(FeedPost.created_at >= since)
    reactions_q = FeedReaction.query.join(FeedPost).filter(FeedPost.created_at >= since)
    comments_q = FeedComment.query.join(FeedPost).filter(FeedPost.created_at >= since)

    # Filter by role
    role = getattr(current_user, "role", "user")
    sid = getattr(current_user, "sector_id", None)
    if role == "director" and sid:
        posts_q = posts_q.filter((FeedPost.audience_type == "all") | (FeedPost.audience_id == sid))
        reactions_q = reactions_q.filter((FeedPost.audience_type == "all") | (FeedPost.audience_id == sid))
        comments_q = comments_q.filter((FeedPost.audience_type == "all") | (FeedPost.audience_id == sid))
    elif role == "user":
        posts_q = posts_q.filter((FeedPost.audience_type == "all") | (FeedPost.author_id == current_user.id))
        reactions_q = reactions_q.filter((FeedPost.audience_type == "all") | (FeedPost.author_id == current_user.id))
        comments_q = comments_q.filter((FeedPost.audience_type == "all") | (FeedPost.author_id == current_user.id))

    stats = {
        "posts": posts_q.count(),
        "comments": comments_q.count(),
        "reactions": reactions_q.count(),
    }

    return jsonify({"ok": True, "since": since.isoformat(), "stats": stats})


@bp.get("/reactions")
@login_required
def reactions_breakdown():
    """GET /api/feed/analytics/reactions?days=30"""
    days = request.args.get("days", 30, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    q = db.session.query(
        FeedReaction.emoji,
        func.count(FeedReaction.id).label("count")
    ).join(FeedPost).filter(FeedPost.created_at >= since)

    role = getattr(current_user, "role", "user")
    sid = getattr(current_user, "sector_id", None)
    if role == "director" and sid:
        q = q.filter((FeedPost.audience_type == "all") | (FeedPost.audience_id == sid))
    elif role == "user":
        q = q.filter(FeedReaction.user_id == current_user.id)

    q = q.group_by(FeedReaction.emoji).order_by(func.count(FeedReaction.id).desc())
    data = [{"emoji": e, "count": c} for e, c in q.all()]

    return jsonify({"ok": True, "since": since.isoformat(), "items": data})


@bp.get("/top-contributors")
@login_required
def top_contributors():
    """GET /api/feed/analytics/top-contributors?days=30"""
    days = request.args.get("days", 30, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    q = db.session.query(
        FeedPost.author_id,
        func.count(FeedPost.id).label("posts"),
        func.coalesce(func.sum(func.count(FeedReaction.id)).over(partition_by=FeedPost.author_id), 0).label("total_rx")
    ).join(FeedReaction, FeedReaction.post_id == FeedPost.id, isouter=True)\
     .filter(FeedPost.created_at >= since)

    role = getattr(current_user, "role", "user")
    sid = getattr(current_user, "sector_id", None)
    if role == "director" and sid:
        q = q.filter((FeedPost.audience_type == "all") | (FeedPost.audience_id == sid))
    elif role == "user":
        q = q.filter(FeedPost.author_id == current_user.id)

    rows = q.group_by(FeedPost.author_id).all()

    results = []
    for uid, posts, total_rx in rows:
        u = User.query.get(uid)
        if not u:
            continue
        results.append({
            "user_id": uid,
            "name": getattr(u, "full_name", u.username),
            "avatar": getattr(u, "avatar_url", None),
            "posts": int(posts or 0),
            "reactions": int(total_rx or 0)
        })

    results = sorted(results, key=lambda x: (x["reactions"], x["posts"]), reverse=True)
    return jsonify({"ok": True, "since": since.isoformat(), "items": results[:10]})


@bp.get("/active-hours")
@login_required
def active_hours():
    """
    Returns comment activity grouped by hour of day.
    Useful for heatmaps.
    """
    days = request.args.get("days", 7, type=int)
    since = datetime.utcnow() - timedelta(days=days)

    q = db.session.query(
        func.extract("hour", FeedComment.created_at).label("hour"),
        func.count(FeedComment.id)
    ).join(FeedPost).filter(FeedPost.created_at >= since)

    role = getattr(current_user, "role", "user")
    sid = getattr(current_user, "sector_id", None)
    if role == "director" and sid:
        q = q.filter((FeedPost.audience_type == "all") | (FeedPost.audience_id == sid))
    elif role == "user":
        q = q.filter(FeedComment.author_id == current_user.id)

    q = q.group_by(func.extract("hour", FeedComment.created_at)).order_by("hour")
    rows = q.all()

    data = [{"hour": int(h), "count": int(c)} for h, c in rows]
    return jsonify({"ok": True, "since": since.isoformat(), "items": data})
