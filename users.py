from app import create_app
from app.extensions import db
from app.models import Permission
from app.permissions import PERMISSION_CATALOG

app = create_app()
with app.app_context():
    existing = {p.code for p in Permission.query.all()}
    created = 0
    for code, name in PERMISSION_CATALOG.items():
        if code not in existing:
            db.session.add(Permission(code=code, name=name))
            created += 1
    if created:
        db.session.commit()
    print(f"✅ Seed complete. Added {created} new permissions.")
