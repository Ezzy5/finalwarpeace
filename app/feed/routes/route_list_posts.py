# app/feed/routes/route_list_posts.py
from __future__ import annotations
from typing import List
from datetime import datetime, date, time as dt_time, timedelta

from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, and_

from app.extensions import db  # may be unused but kept for consistency
from app.feed import bp
from app.feed.models import FeedPost
from app.feed.routes.util_parse_int import _parse_int
from app.feed.routes.util_has_col import _has_col
from app.feed.routes.util_cursor_decode import _cursor_decode
from app.feed.routes.util_cursor_encode import _cursor_encode
from app.feed.routes.perms_can_view_post import _can_view_post
from app.feed.routes.serializers_post_to_dict import _post_to_dict


def _apply_date_preset(query, preset: str):
    """
    Apply a date range filter based on a preset string.
    Uses server-local dates; precise timezone handling is not critical here.
    """
    preset = (preset or "").strip().lower()
    if not preset or preset == "all":
        return query

    today = date.today()

    start_dt = None  # type: ignore
    end_dt = None    # type: ignore

    if preset == "today":
        start_dt = datetime.combine(today, dt_time.min)
        end_dt = datetime.combine(today, dt_time.max)
    elif preset == "yesterday":
        d = today - timedelta(days=1)
        start_dt = datetime.combine(d, dt_time.min)
        end_dt = datetime.combine(d, dt_time.max)
    elif preset == "week":
        # This week: from Monday
        monday = today - timedelta(days=today.weekday())
        start_dt = datetime.combine(monday, dt_time.min)
        end_dt = datetime.combine(today, dt_time.max)
    elif preset == "month":
        first = today.replace(day=1)
        start_dt = datetime.combine(first, dt_time.min)
        end_dt = datetime.combine(today, dt_time.max)
    elif preset == "year":
        first = today.replace(month=1, day=1)
        start_dt = datetime.combine(first, dt_time.min)
        end_dt = datetime.combine(today, dt_time.max)
    elif preset in {"30", "60", "90"}:
        days = int(preset)
        start_dt = datetime.combine(today - timedelta(days=days), dt_time.min)
        end_dt = datetime.combine(today, dt_time.max)

    if start_dt and end_dt and _has_col(FeedPost, "created_at"):
        query = query.filter(
            FeedPost.created_at >= start_dt,
            FeedPost.created_at <= end_dt,
        )

    return query


@bp.get("")
@bp.get("/")
@login_required
def list_posts():
    try:
        # --- basic paging ---
        limit = max(1, min(_parse_int(request.args.get("limit"), 10), 50))
        cursor = request.args.get("cursor")
        cur_dt, cur_id = _cursor_decode(cursor)

        # --- filters from query string ---
        date_preset = request.args.get("date_preset", "").strip().lower()
        author_name = (request.args.get("author_name") or "").strip().lower()
        tagged_only_raw = (request.args.get("tagged_only") or "").strip().lower()
        tagged_only = tagged_only_raw in {"1", "true", "yes", "on"}
        search_q = (request.args.get("q") or "").strip()

        # --- base query ---
        q = FeedPost.query
        if _has_col(FeedPost, "is_deleted"):
            q = q.filter_by(is_deleted=False)

        # apply date filter first
        if date_preset:
            q = _apply_date_preset(q, date_preset)

        # keyword search in title/html (best-effort)
        if search_q:
            like = f"%{search_q}%"
            conds = []
            if _has_col(FeedPost, "title"):
                conds.append(FeedPost.title.ilike(like))
            if _has_col(FeedPost, "html"):
                conds.append(FeedPost.html.ilike(like))
            if conds:
                q = q.filter(or_(*conds))

        # existing cursor-based pagination (created_at + id)
        if cur_dt is not None and cur_id is not None and _has_col(FeedPost, "created_at"):
            q = q.filter(
                or_(
                    FeedPost.created_at < cur_dt,
                    and_(FeedPost.created_at == cur_dt, FeedPost.id < cur_id),
                )
            )

        # ordering
        if _has_col(FeedPost, "created_at"):
            q = q.order_by(FeedPost.created_at.desc(), FeedPost.id.desc())
        else:
            q = q.order_by(FeedPost.id.desc())

        # --- collect items, enforcing permissions, tagged_only and author_name ---
        items: List[FeedPost] = []

        # We still use limit+1 on the SQL side, then filter in Python.
        # If many posts are filtered out, the page may have fewer than `limit` items,
        # but it will never show posts the user shouldn’t see.
        for p in q.limit(limit + 1).all():
            # permission guard
            if not _can_view_post(current_user, p):
                continue

            # tagged_only: only posts where audience_type=="users" AND current user in allowed_users
            if tagged_only:
                audience_type = getattr(p, "audience_type", None)
                if audience_type != "users":
                    # skip global/all-employee posts when "TO" filter is active
                    continue
                allowed = getattr(p, "allowed_users", []) or []
                if not any(getattr(u, "id", None) == current_user.id for u in allowed):
                    continue

            # author_name filter (by full_name or first+last, case-insensitive)
            if author_name:
                a = getattr(p, "author", None)
                if not a:
                    continue
                full_name = (
                    getattr(a, "full_name", None)
                    or getattr(a, "name", None)
                    or (
                        (
                            (getattr(a, "first_name", "") or "") + " " +
                            (getattr(a, "last_name", "") or "")
                        ).strip()
                    )
                    or getattr(a, "email", None)
                    or ""
                )
                if author_name not in full_name.lower():
                    continue

            items.append(p)
            if len(items) >= limit + 1:
                break

        sliced = items[:limit]
        next_cursor = _cursor_encode(sliced[-1]) if len(items) > limit else None
        resp = {
            "items": [_post_to_dict(p, with_rel=True, u=current_user) for p in sliced],
            "next_cursor": next_cursor,
            "done": next_cursor is None,
        }
        return jsonify(resp)
    except Exception as e:
        current_app.logger.exception("list_posts failed")
        return jsonify({"error": "internal", "detail": str(e)}), 500
