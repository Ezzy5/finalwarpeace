from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import desc, text
from app.extensions import db
from app.feed.models import FeedPost
from app.feed.permissions import feed_queryset_for_current_user
from . import bp

PAGE_SIZE = 10

def _post_to_json(p: FeedPost):
    # Minimal payload for search results (open full post via drawer)
    return {
        "id": p.id,
        "title": p.title,
        "snippet": (p.html[:240] + "…") if p.html and len(p.html) > 240 else (p.html or ""),
        "created_at": p.created_at.isoformat(),
        "author": {
            "id": getattr(p.author, "id", None),
            "name": getattr(p.author, "full_name", None) or getattr(p.author, "username", None),
            "avatar": getattr(p.author, "avatar_url", None),
        }
    }

@bp.get("/")
@login_required
def search():
    """
    GET /api/feed/search/?q=term&after_id=123&after_created=ISO
    Uses PostgreSQL FTS (generated tsvector & GIN index).
    Falls back to ILIKE if FTS not available.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": True, "items": [], "next": None})

    after_id = request.args.get("after_id", type=int)
    after_created = request.args.get("after_created")

    base = feed_queryset_for_current_user(FeedPost.query).order_by(desc(FeedPost.created_at), desc(FeedPost.id))

    # Prefer FTS if column exists; otherwise fallback
    use_fts = False
    try:
        # light check for column presence
        db.session.execute(text("SELECT to_regclass('public.idx_feed_posts_fts');"))
        use_fts = True
    except Exception:
        use_fts = False

    items = []
    next_cursor = None

    if use_fts:
        # plainto_tsquery for safer parsing; use english by default (configure in SQL installer)
        sql = """
            SELECT p.*
            FROM feed_posts p
            WHERE p.is_deleted = FALSE
              AND ({visibility_sql})
              AND p.tsv @@ plainto_tsquery('english', :term)
            {cursor}
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT :lim
        """
        # visibility_sql mirrors feed_queryset_for_current_user by reusing ORM filter subquery
        # Easiest: fetch visible IDs via ORM first, then filter by FTS for those IDs
        visible_ids = [r[0] for r in base.with_entities(FeedPost.id).limit(1000).all()]  # cap for sanity
        if not visible_ids:
            return jsonify({"ok": True, "items": [], "next": None})

        cursor_sql = ""
        params = {"term": q, "lim": PAGE_SIZE + 1}
        if after_created and after_id:
            cursor_sql = "AND (p.created_at, p.id) < (:ac::timestamptz, :aid)"
            params["ac"] = after_created
            params["aid"] = after_id

        sql = sql.format(
            visibility_sql="p.id = ANY(:ids)",
            cursor=cursor_sql
        )
        params["ids"] = visible_ids

        rows = db.session.execute(text(sql), params).mappings().all()
        posts = [FeedPost(**dict(r)) for r in rows]  # lightweight row->model init
    else:
        # Fallback: ILIKE search on title/html
        q_like = f"%{q}%"
        qry = base.filter(
            db.or_(
                FeedPost.title.ilike(q_like),
                FeedPost.html.ilike(q_like),
            )
        )
        if after_created and after_id:
            from datetime import datetime
            try:
                from dateutil.parser import isoparse  # optional
                ac = isoparse(after_created)  # type: ignore
            except Exception:
                from datetime import datetime
                ac = datetime.fromisoformat(after_created)
            qry = qry.filter(
                db.or_(
                    FeedPost.created_at < ac,
                    db.and_(FeedPost.created_at == ac, FeedPost.id < after_id)
                )
            )
        posts = qry.limit(PAGE_SIZE + 1).all()

    has_next = len(posts) > PAGE_SIZE
    posts = posts[:PAGE_SIZE]
    if has_next and posts:
        last = posts[-1]
        next_cursor = {"after_created": last.created_at.isoformat(), "after_id": last.id}

    return jsonify({
        "ok": True,
        "items": [_post_to_json(p) for p in posts],
        "next": next_cursor
    })
