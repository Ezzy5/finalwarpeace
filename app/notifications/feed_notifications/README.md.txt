# Feed Notifications (DB-triggered, API exposed)

This module auto-creates notifications for Feed events **without touching other files** by using **PostgreSQL triggers**.

## What it does
- On **new post**: notifies audience (all / sector / explicit users), excluding the author.
- On **new comment**: notifies post author + distinct previous commenters (excluding actor).
- On **new reaction**: notifies post author (excluding reactor).
- Provides JSON API to list, count unread, and mark as seen.

## Install

1) Register blueprint somewhere you register others:
```python
from app.notifications.feed_notifications import bp as feed_notify_api_bp
app.register_blueprint(feed_notify_api_bp)
