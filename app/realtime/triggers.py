from textwrap import dedent
from sqlalchemy import text
from app.extensions import db

SQL = dedent("""
-- === REALTIME NOTIFY TRIGGERS (PostgreSQL) ===
-- Broadcast lightweight JSON on:
--   feed_posts, feed_comments, feed_reactions, feed_notifications

-- FEED POSTS
CREATE OR REPLACE FUNCTION fn_rt_feed_post() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    PERFORM pg_notify('feed_events',
      json_build_object(
        'type','post',
        'id', NEW.id,
        'author_id', NEW.author_id,
        'audience_type', NEW.audience_type,
        'audience_id', NEW.audience_id,
        'created_at', to_char(NEW.created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      )::text
    );
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rt_feed_post ON feed_posts;
CREATE TRIGGER trg_rt_feed_post AFTER INSERT ON feed_posts
FOR EACH ROW EXECUTE FUNCTION fn_rt_feed_post();

-- FEED COMMENTS
CREATE OR REPLACE FUNCTION fn_rt_feed_comment() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    PERFORM pg_notify('feed_events',
      json_build_object(
        'type','comment',
        'id', NEW.id,
        'post_id', NEW.post_id,
        'author_id', NEW.author_id,
        'created_at', to_char(NEW.created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      )::text
    );
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rt_feed_comment ON feed_comments;
CREATE TRIGGER trg_rt_feed_comment AFTER INSERT ON feed_comments
FOR EACH ROW EXECUTE FUNCTION fn_rt_feed_comment();

-- FEED REACTIONS
CREATE OR REPLACE FUNCTION fn_rt_feed_reaction() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    PERFORM pg_notify('feed_events',
      json_build_object(
        'type','reaction',
        'id', NEW.id,
        'post_id', NEW.post_id,
        'user_id', NEW.user_id,
        'emoji', NEW.emoji,
        'created_at', to_char(NEW.created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      )::text
    );
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rt_feed_reaction ON feed_reactions;
CREATE TRIGGER trg_rt_feed_reaction AFTER INSERT ON feed_reactions
FOR EACH ROW EXECUTE FUNCTION fn_rt_feed_reaction();

-- FEED NOTIFICATIONS (from your feed_notifications module)
CREATE OR REPLACE FUNCTION fn_rt_feed_notification() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    PERFORM pg_notify('notif_events',
      json_build_object(
        'type', NEW.kind,
        'id', NEW.id,
        'user_id', NEW.user_id,
        'actor_id', NEW.actor_id,
        'post_id', NEW.post_id,
        'created_at', to_char(NEW.created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      )::text
    );
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_rt_feed_notification ON feed_notifications;
CREATE TRIGGER trg_rt_feed_notification AFTER INSERT ON feed_notifications
FOR EACH ROW EXECUTE FUNCTION fn_rt_feed_notification();
""")

def install_triggers():
    with db.engine.begin() as conn:
        conn.execute(text(SQL))
