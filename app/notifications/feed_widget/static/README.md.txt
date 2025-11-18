# Feed Notifications Widget (SPA)

Client-side widget for your notifications sidebar. No framework, no routes, no templates.

## Mount

```html
<!-- Where you want the widget -->
<div id="feed-notify-root"
     data-endpoint="/api/notifications/feed"
     data-avatar="/static/img/avatar-placeholder.png"
     data-badge="#notif-badge"
     data-poll="20"></div>

<!-- Somewhere in your header/topbar -->
<span id="notif-badge" style="display:none"></span>

<!-- Include files -->
<link rel="stylesheet" href="/static/feed-notify/feed-notify.css">
<script defer src="/static/feed-notify/feed-notify.js"></script>
