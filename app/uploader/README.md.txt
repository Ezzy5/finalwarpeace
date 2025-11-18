# Uploader (Feed attachments)

Turns SPA feed previews into real URLs, stored on disk and served via `/u/...`.
No changes to other files required.

## Endpoints

- **POST `/api/upload/feed`** (multipart)
  - Field: `files` (multiple accepted)
  - Response:
    ```json
    {
      "ok": true,
      "items": [
        {
          "name": "photo.jpg",
          "mime": "image/jpeg",
          "size": 123456,
          "url": "/u/feed/2025/10/17/3fa85f64....jpg",
          "preview_url": "/u/feed/2025/10/17/3fa85f64...._thumb.jpg"
        }
      ]
    }
    ```

- **GET `/u/<path>`** — serves uploaded files (public).

- **DELETE `/api/upload/purge?url=/u/...`** — optional cleanup of a single file.

## Install

1) Register the two blueprints:
```python
from app.uploader import bp as uploader_bp
from app.uploader.api import public_bp as uploads_public_bp

app.register_blueprint(uploader_bp)         # /api/upload/...
app.register_blueprint(uploads_public_bp)   # /u/...
