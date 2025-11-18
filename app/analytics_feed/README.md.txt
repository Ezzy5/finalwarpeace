# Feed Analytics API

Self-contained analytics endpoints for your SPA feed dashboard.

## Endpoints

- `GET /api/feed/analytics/overview?days=7`
  - Counts posts, comments, and reactions for last N days.

- `GET /api/feed/analytics/reactions?days=30`
  - Emoji breakdown (`👍🔥🎉...`).

- `GET /api/feed/analytics/top-contributors?days=30`
  - Top 10 most active authors by posts and reactions.

- `GET /api/feed/analytics/active-hours?days=7`
  - Comment frequency by hour of day.

## Role Logic

| Role | Visibility |
|------|-------------|
| Admin | All data |
| Director | Their sector + public posts |
| User | Own posts/comments only |

## Register

```python
from app.analytics_feed import bp as feed_analytics_bp
app.register_blueprint(feed_analytics_bp)
