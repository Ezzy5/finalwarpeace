from textwrap import dedent
from sqlalchemy import text
from app.extensions import db

SQL = dedent("""
-- === FEED NOTIFICATIONS TRIGGERS (PostgreSQL) ===
-- ASSUMPTIONS:
--  - users table: "user" with columns id, role, sector_id, (optional: is_active boolean default true)
--  - feed tables: feed_posts, feed_comments, feed_reactions (as provided in app/feed)
--  - audience control on feed_posts: audience_type ('all'|'sector'|'users'), audience_id (sector), and join table feed_post_allowed_users(post_id,user_id)
--  - This creates notifications in feed_notifications (recipient user_id) for:
--      * New post: all eligible audience except the author
--      * New comment: post author + previous commenters (distinct), except the actor
--      * New reaction: post author, except the reactor

-- ---------- Helper: coalesce active users ----------
CREATE OR REPLACE VIEW v_active_users AS
SELECT id, role, sector_id
FROM "user"
-- if you have a flag like is_active, add: WHERE is_active IS TRUE
;

-- ---------- New Post notifications ----------
CREATE OR REPLACE FUNCTION fn_notify_feed_post() RETURNS trigger AS $$
DECLARE
    actor INT := NEW.author_id;
BEGIN
    IF NEW.is_deleted IS TRUE THEN
        RETURN NEW;
    END IF;

    -- All
    IF NEW.audience_type = 'all' THEN
        INSERT INTO feed_notifications(user_id, actor_id, post_id, kind, payload, created_at)
        SELECT u.id, actor, NEW.id, 'post_created',
               jsonb_build_object('title', COALESCE(NEW.title,'')),
               now()
        FROM v_active_users u
        WHERE u.id <> actor;

    -- Sector
    ELSIF NEW.audience_type = 'sector' THEN
        INSERT INTO feed_notifications(user_id, actor_id, post_id, kind, payload, created_at)
        SELECT u.id, actor, NEW.id, 'post_created',
               jsonb_build_object('title', COALESCE(NEW.title,''), 'sector_id', NEW.audience_id),
               now()
        FROM v_active_users u
        WHERE u.sector_id = NEW.audience_id
          AND u.id <> actor;

    -- Users (explicit list)
    ELSIF NEW.audience_type = 'users' THEN
        INSERT INTO feed_notifications(user_id, actor_id, post_id, kind, payload, created_at)
        SELECT fpu.user_id, actor, NEW.id, 'post_created',
               jsonb_build_object('title', COALESCE(NEW.title,'')),
               now()
        FROM feed_post_allowed_users fpu
        WHERE fpu.post_id = NEW.id
          AND fpu.user_id <> actor;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_feed_post ON feed_posts;
CREATE TRIGGER trg_notify_feed_post
AFTER INSERT ON feed_posts
FOR EACH ROW EXECUTE FUNCTION fn_notify_feed_post();

-- ---------- New Comment notifications ----------
CREATE OR REPLACE FUNCTION fn_notify_feed_comment() RETURNS trigger AS $$
DECLARE
    actor INT := NEW.author_id;
    p_audience TEXT;
    p_audience_id INT;
    p_author INT;
BEGIN
    SELECT audience_type, audience_id, author_id INTO p_audience, p_audience_id, p_author
    FROM feed_posts WHERE id = NEW.post_id;

    -- Notify post author (if not self)
    IF p_author IS NOT NULL AND p_author <> actor THEN
        INSERT INTO feed_notifications(user_id, actor_id, post_id, kind, payload, created_at)
        VALUES (p_author, actor, NEW.post_id, 'comment_added',
                jsonb_build_object('comment_id', NEW.id), now());
    END IF;

    -- Notify previous commenters (distinct) in same visibility, excluding actor and post author duplicate
    INSERT INTO feed_notifications(user_id, actor_id, post_id, kind, payload, created_at)
    SELECT DISTINCT c.author_id, actor, NEW.post_id, 'comment_added',
           jsonb_build_object('comment_id', NEW.id), now()
    FROM feed_comments c
    WHERE c.post_id = NEW.post_id
      AND c.author_id <> actor
      AND c.author_id <> COALESCE(p_author, -1)
      AND c.id <> NEW.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_feed_comment ON feed_comments;
CREATE TRIGGER trg_notify_feed_comment
AFTER INSERT ON feed_comments
FOR EACH ROW EXECUTE FUNCTION fn_notify_feed_comment();

-- ---------- New Reaction notifications ----------
CREATE OR REPLACE FUNCTION fn_notify_feed_reaction() RETURNS trigger AS $$
DECLARE
    actor INT := NEW.user_id;
    p_author INT;
BEGIN
    SELECT author_id INTO p_author FROM feed_posts WHERE id = NEW.post_id;

    IF p_author IS NOT NULL AND p_author <> actor THEN
        INSERT INTO feed_notifications(user_id, actor_id, post_id, kind, payload, created_at)
        VALUES (p_author, actor, NEW.post_id, 'reacted',
                jsonb_build_object('emoji', NEW.emoji), now());
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_feed_reaction ON feed_reactions;
CREATE TRIGGER trg_notify_feed_reaction
AFTER INSERT ON feed_reactions
FOR EACH ROW EXECUTE FUNCTION fn_notify_feed_reaction();
""")

def install_triggers():
    """Run once to install/replace the PostgreSQL trigger functions."""
    with db.engine.begin() as conn:
        conn.execute(text(SQL))
