# Feed Post Drawer (SPA, static-only)

A sleek side-panel that opens a feed post with full content, attachments, reactions, and live comments.
It **does not** modify other code. It listens for an event and uses the existing Feed API.

## Mount

Include once in your SPA shell/layout:
```html
<link rel="stylesheet" href="/static/feed-drawer/feed-drawer.css">
<script defer src="/static/feed-drawer/feed-drawer.js"></script>
