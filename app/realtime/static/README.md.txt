# Realtime (SSE over Postgres LISTEN/NOTIFY)

**No edits to other files needed.**  
This module installs DB triggers that `pg_notify()` on inserts and streams them to clients via SSE.

## Install

1) Register blueprint:
```python
from app.realtime import bp as realtime_bp
app.register_blueprint(realtime_bp)
