from textwrap import dedent
from sqlalchemy import text
from app.extensions import db

SQL = dedent("""
-- Full-text search for feed_posts
-- Requires PostgreSQL.
-- Language: english (adjust to your needs).

-- Add generated tsvector column (safe if already exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='feed_posts' AND column_name='tsv'
  ) THEN
    ALTER TABLE feed_posts
      ADD COLUMN tsv tsvector
      GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
        setweight(to_tsvector('english', regexp_replace(coalesce(html,''), '<[^>]+>', ' ', 'g')), 'B')
      ) STORED;
  END IF;
END$$;

-- Index
DROP INDEX IF EXISTS idx_feed_posts_fts;
CREATE INDEX idx_feed_posts_fts ON feed_posts USING GIN (tsv);
""")

def install_search():
    with db.engine.begin() as conn:
        conn.execute(text(SQL))
