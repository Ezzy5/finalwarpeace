import json
import threading
import time
from queue import Queue, Empty
from typing import Dict, Any, Optional

from sqlalchemy import text
from app.extensions import db

CHANNELS = ("feed_events", "notif_events")

class _Hub:
    """
    Simple pub/sub hub + PG LISTEN bridge.
    - Per-connection queues (for SSE clients)
    - Background thread: LISTEN on PG channels and publish to subscribers
    """
    def __init__(self):
        self._subs = {}  # id -> Queue
        self._lock = threading.Lock()
        self._listener_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        if self._listener_thread and self._listener_thread.is_alive():
            return
        self._stop.clear()
        self._listener_thread = threading.Thread(target=self._pg_listener_loop, daemon=True)
        self._listener_thread.start()

    def stop(self):
        self._stop.set()

    def subscribe(self) -> str:
        q = Queue(maxsize=1000)
        sid = f"s_{time.time_ns()}"
        with self._lock:
            self._subs[sid] = q
        return sid

    def unsubscribe(self, sid: str):
        with self._lock:
            self._subs.pop(sid, None)

    def poll(self, sid: str, timeout=15.0) -> Optional[Dict[str, Any]]:
        q = None
        with self._lock:
            q = self._subs.get(sid)
        if not q:
            return None
        try:
            return q.get(timeout=timeout)
        except Empty:
            return None

    def publish(self, payload: Dict[str, Any]):
        # Fan out non-blocking
        with self._lock:
            subs = list(self._subs.values())
        for q in subs:
            try:
                q.put_nowait(payload)
            except Exception:
                # queue full: drop event for that client
                pass

    def _pg_listener_loop(self):
        # Dedicated raw connection for async notifications
        while not self._stop.is_set():
            try:
                # Use the DBAPI connection underneath SQLAlchemy
                with db.engine.connect() as conn:
                    raw = conn.connection
                    cursor = raw.cursor()
                    for ch in CHANNELS:
                        cursor.execute(f'LISTEN "{ch}";')
                    conn.commit()

                    # polling loop
                    while not self._stop.is_set():
                        raw.poll()
                        while raw.notifies:
                            n = raw.notifies.pop(0)
                            try:
                                data = json.loads(n.payload)
                                self.publish({"channel": n.channel, **data})
                            except Exception:
                                self.publish({"channel": n.channel, "type": "raw", "payload": n.payload})
                        time.sleep(0.2)
            except Exception:
                # Backoff on error
                time.sleep(1.0)

hub = _Hub()
