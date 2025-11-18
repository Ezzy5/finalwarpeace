# bootstrap_admin.py
from app import create_app
from app.extensions import db
from app.models import User, Role
from sqlalchemy import func

EMAIL = "admin@primer.com"  # <-- put the email you sign in with

app = create_app()
with app.app_context():
    u = User.query.filter(func.lower(User.email) == EMAIL.lower()).first()
    assert u, f"No user with email {EMAIL}"

    admin = Role.query.filter(func.lower(Role.name) == "admin").first()
    if not admin:
        admin = Role(name="admin")
        db.session.add(admin)
        db.session.flush()

    u.role = admin
    db.session.commit()
    print("✅", u.email, "is now ADMIN")
