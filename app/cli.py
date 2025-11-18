# -*- coding: utf-8 -*-
import click
from app import db
from app.models import Role, Permission  # adjust import path if needed
from sqlalchemy import func

@click.group()
def seed():
    """Data seeding commands."""
    pass

@seed.command("tickets")
def seed_tickets_permissions():
    """
    Seed tickets permissions and attach them to the Admin role.
    Assumes Permission has columns: code (unique, not null), name (string).
    """
    # code, human-readable name
    needed = [
        ("tickets.view",   "View tickets"),
        ("tickets.create", "Create tickets"),
        ("tickets.edit",   "Edit tickets"),
    ]

    created = []

    # Avoid autoflush while we query-and-insert in one go
    with db.session.no_autoflush:
        for code, name in needed:
            p = Permission.query.filter(func.lower(Permission.code) == code.lower()).first()
            if not p:
                p = Permission(code=code, name=name)
                db.session.add(p)
                created.append(code)

    db.session.flush()  # ensure IDs present for relationship work

    # Find an Admin role (case-insensitive). Change the string if your role is named differently.
    admin = Role.query.filter(func.lower(Role.name) == "admin").first()
    if admin:
        for code, _ in needed:
            p = Permission.query.filter(func.lower(Permission.code) == code.lower()).first()
            if p not in admin.permissions:
                admin.permissions.append(p)
        db.session.commit()
        click.echo("Permissions ensured: " + ", ".join([c for c, _ in needed]))
        if created:
            click.echo("Created: " + ", ".join(created))
        click.echo("Attached to Admin role.")
    else:
        db.session.commit()
        click.echo("Permissions ensured: " + ", ".join([c for c, _ in needed]))
        if created:
            click.echo("Created: " + ", ".join(created))
        click.echo("No 'Admin' role found. Skipping role assignment.")
