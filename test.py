# flask shell
from app import create_app
app = create_app()
ctx = app.app_context(); ctx.push()

from app.extensions import db
# Adjust these imports to your actual models if needed:
from app.models import User, Role, Permission

def get_or_create_perm(name):
    p = Permission.query.filter_by(name=name).first()
    if not p:
        p = Permission(name=name)
        db.session.add(p)
        db.session.commit()
    return p

p_view = get_or_create_perm("tickets.view")
p_create = get_or_create_perm("tickets.create")
p_redirect = get_or_create_perm("tickets.redirect")
p_delete = get_or_create_perm("tickets.delete")

# Pick a user to empower (change email/id as needed)
u = User.query.first()  # or e.g. User.query.filter_by(email="you@domain").first()

# Attach to a role the user already has (preferred)
r = None
for cand in ("administrator","admin","director","user"):
    r = Role.query.filter_by(name=cand).first() or r
if r:
    perms = getattr(r, "permissions", [])
    if p_view not in perms: r.permissions.append(p_view)
    if p_create not in perms: r.permissions.append(p_create)
    if p_redirect not in perms: r.permissions.append(p_redirect)
    # keep delete optional if you want
    db.session.commit()
else:
    # Fallback: if your app supports user.permissions directly
    if hasattr(u, "permissions"):
        if p_view not in u.permissions: u.permissions.append(p_view)
        db.session.commit()

print("Done: permissions seeded.")
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # helper methods
    def set_password(self, raw_password):
        """Hash and store a password."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, raw_password)
