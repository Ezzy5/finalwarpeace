# Refs API (Sectors & Users)

Small helper API used by the SPA feed composer to populate **audience** selectors.

## Endpoints

- `GET /api/refs/sectors?q=&after_id=&limit=`
  - **admin** → all sectors
  - **director** → only their sector(s)
  - **user** → only their sector(s)
  - Response: `{ ok, items: [{id, name}], next_after_id }`

- `GET /api/refs/users?q=&after_id=&limit=`
  - **admin** → all users
  - **director** → users in their sector(s)
  - **user** → self + users in their sector(s)
  - Response: `{ ok, items: [{id, name, avatar, sector_id, role}], next_after_id }`

Both endpoints support:
- `q` (case-insensitive contains)
- `after_id` (cursor pagination)
- `limit` (max 100)

## Wiring

Register the blueprint where you register others:
```python
from app.refs import bp as refs_api_bp
app.register_blueprint(refs_api_bp)
