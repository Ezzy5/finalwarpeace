# Feed Search (API + SPA widget)

Role-aware full-text search for feed posts. Uses PostgreSQL FTS (tsvector + GIN).  
If the index isn’t installed, it falls back to ILIKE.

## Install

1) Register blueprint:
```python
from app.feed_search import bp as feed_search_bp
app.register_blueprint(feed_search_bp)
