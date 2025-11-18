# Analytics Dashboard (SPA, static)

Sleek analytics UI for the Feed. Uses your existing API:
- `/api/feed/analytics/overview`
- `/api/feed/analytics/reactions`
- `/api/feed/analytics/top-contributors`
- `/api/feed/analytics/active-hours`

## Mount

```html
<!-- Optional: Chart.js for rich charts (fallback bars without it) -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- Analytics widget -->
<link rel="stylesheet" href="/static/analytics/analytics.css">
<div id="feed-analytics" data-endpoint="/api/feed/analytics" data-days="14" data-avatar-fallback="/static/img/avatar-placeholder.png"></div>
<script defer src="/static/analytics/analytics.js"></script>
