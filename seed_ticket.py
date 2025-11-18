# app/commands/tickets_perms.py
import click
from flask import current_app
from flask.cli import AppGroup

from app.extensions import db

# >>> Adjust imports to match your project <<<
from app.models import Role, Permission  # Role(name=...), Permission(name=...)

tickets_cli = AppGroup("tickets", help="Tickets module management commands")

PERMS = [
    "tickets.view",
    "tickets.create",
    "tickets.redirect",
    "tickets.delete",
]

DEFAULT_ROLE_MAP = {
    # role_name: [permissions...]
    "administrator": PERMS,
    "admin": PERMS,
    "director": ["tickets.view", "tickets.create", "tickets.redirect"],  # no delete by default
    "user": ["tickets.view"],
}

@tickets_cli.command("seed-perms")
@click.option("--assign-defaults/--no-assign-defaults", default=True, help="Assign default permission sets to common roles.")
def seed_perms(assign_defaults: bool):
    """Create ticket permissions and (optionally) assign to standard roles."""
    app = current_app._get_current_object()
    created = 0

    # Ensure permissions exist
    existing = {p.name for p in Permission.query.filter(Permission.name.in_(PERMS)).all()}
    for name in PERMS:
        if name not in existing:
            db.session.add(Permission(name=name))
            created += 1
    db.session.commit()
    click.echo(f"Permissions created: {created} (total now: {Permission.query.count()})")

    if not assign_defaults:
        return

    # Assign defaults to roles if those roles exist
    perms_by_name = {p.name: p for p in Permission.query.filter(Permission.name.in_(PERMS)).all()}

    updated_roles = []
    for role_name, perm_names in DEFAULT_ROLE_MAP.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            continue

        # role.permissions is expected to be a relationship list
        rp = set(getattr(role, "permissions", []) or [])
        rp_names = {p.name for p in rp}
        changed = False

        for pn in perm_names:
            if pn not in rp_names:
                role.permissions.append(perms_by_name[pn])
                changed = True

        if changed:
            updated_roles.append(role_name)

    if updated_roles:
        db.session.commit()
    click.echo(f"Updated roles: {', '.join(updated_roles) if updated_roles else 'none'}")
