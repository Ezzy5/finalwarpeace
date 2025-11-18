/**
 * Simple, resilient SSE client with a tiny pub/sub.
 * Exposes window.Realtime.{connect,close,on,off,emit}.
 */

(function () {
  if (window.Realtime) return; // singleton

  const _listeners = new Map(); // eventName -> Set<fn>
  let _es = null;
  let _streamUrl = null;

  function _emit(type, data) {
    // Pub/Sub listeners
    const set = _listeners.get(type);
    if (set) {
      set.forEach((fn) => {
        try { fn(data); } catch (e) { console.warn("[realtime] listener error:", e); }
      });
    }
    // DOM CustomEvent
    try { window.dispatchEvent(new CustomEvent("realtime-event", { detail: { type, data } })); }
    catch (_e) {}
  }

  function on(type, fn) {
    if (!_listeners.has(type)) _listeners.set(type, new Set());
    _listeners.get(type).add(fn);
    return () => off(type, fn);
  }

  function off(type, fn) {
    const set = _listeners.get(type);
    if (set) {
      set.delete(fn);
      if (set.size === 0) _listeners.delete(type);
    }
  }

  function _attachES(es) {
    // 🔹 We listen to backend channels: "feed_events" and "notif_events"
    es.addEventListener("feed_events", (e) => {
      let payload = null;
      try {
        payload = e.data ? JSON.parse(e.data) : null;
      } catch {
        payload = null;
      }
      if (!payload) return;

      // payload.type e.g. "feed:new_post"
      const t = payload.type || "feed_events";
      _emit(t, payload);       // e.g. emits "feed:new_post"
      _emit("feed_events", payload); // optional generic
    });

    es.addEventListener("notif_events", (e) => {
      let payload = null;
      try {
        payload = e.data ? JSON.parse(e.data) : null;
      } catch {
        payload = null;
      }
      if (!payload) return;

      const t = payload.type || "notif_events";
      _emit(t, payload);
      _emit("notif_events", payload);
    });

    // Fallback generic messages (if ever sent without event:)
    es.onmessage = (e) => {
      try {
        const data = e.data ? JSON.parse(e.data) : null;
        _emit("message", data);
      } catch {
        _emit("message", e.data);
      }
    };

    es.onerror = (e) => {
      console.debug("[realtime] error/closed:", e);
      // EventSource auto-reconnects; we just log here.
    };

    es.onopen = () => {
      console.debug("[realtime] connected:", _streamUrl);
    };
  }

  const Realtime = {
    connect(streamUrl) {
      if (_es) return _es;
      _streamUrl = streamUrl || "/api/realtime/stream";
      try {
        const es = new EventSource(_streamUrl, { withCredentials: true });
        _es = es;
        _attachES(es);
        console.debug("[realtime] connecting to", _streamUrl);
        return es;
      } catch (e) {
        console.warn("[realtime] failed to connect:", e);
        return null;
      }
    },
    close() {
      try { if (_es) _es.close(); } catch (_e) {}
      _es = null;
    },
    on,
    off,
    emit(type, data) { _emit(type, data); }
  };

  window.Realtime = Realtime;
})();

/* -------------------------------------------------------------
   ✅ AUTO UI UPDATE: LIVE FEED NEW POSTS
   ------------------------------------------------------------- */
(function () {
  if (!window.Realtime) return;

  window.Realtime.on("feed:new_post", (payload) => {
    if (!payload || !payload.post) return;

    if (window.FeedApp && typeof window.FeedApp.prependPost === "function") {
      try {
        window.FeedApp.prependPost(payload.post);
        console.debug("[realtime] Live post added to feed:", payload.post.id);
      } catch (e) {
        console.warn("[realtime] failed to prepend new post", e);
      }
    }
  });
})();
