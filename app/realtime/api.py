import json
from datetime import datetime
from flask import Response, stream_with_context, request, jsonify
from flask_login import login_required, current_user

from . import bp
from .broker import hub
from .triggers import install_triggers  # one-time installer

@bp.before_app_request
def _start():
    hub.start()

@bp.get("/stream")
@login_required
def stream():
    """
    SSE: emits events from channels:
      - feed_events: {type: "post|comment|reaction", id, post_id?, actor_id?, ...}
      - notif_events: {type: "post_created|comment_added|reacted", id, user_id, post_id, ...}
    """
    sid = hub.subscribe()

    def gen():
        try:
            # send a hello
            yield f"event: hello\ndata: {json.dumps({'time': datetime.utcnow().isoformat()})}\n\n"
            while True:
                evt = hub.poll(sid, timeout=15.0)
                if evt is None:
                    # keep-alive
                    yield ": keep-alive\n\n"
                    continue
                # Optional: light authorization filter per event
                # (We keep everything; your SPA decides what to use.)
                yield f"event: {evt.get('channel','evt')}\n"
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        finally:
            hub.unsubscribe(sid)

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream; charset=utf-8",
        "X-Accel-Buffering": "no",  # nginx: disable buffering
    }
    return Response(stream_with_context(gen()), headers=headers)

@bp.post("/install-triggers")
@login_required
def install():
    # Allow only admins to (re)install
    if getattr(current_user, "role", "user") != "admin":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    install_triggers()
    return jsonify({"ok": True})
