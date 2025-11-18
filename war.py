# scripts/war/war.py
from __future__ import annotations

import sys
from typing import Iterable

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db
from app.models import Department

# Permissions you want to seed per department
PERMISSIONS: Iterable[str] = (
    "war.view",
    "war.manage",
    "war.interact",
    "war.comment",
)

def schema_is_new() -> bool:
    """Return True if department_permissions has the new 'permission' column."""
    insp = inspect(db.engine)
    cols = {c["name"] for c in insp.get_columns("department_permissions")}
    return ("permission" in cols) and ("code" not in cols)

def seed_new_schema():
    """
    New schema:
      department_permissions(department_id INTEGER, permission TEXT NOT NULL,
      UNIQUE(department_id, permission))
    """
    sql = text("""
        INSERT OR IGNORE INTO department_permissions (department_id, permission)
        VALUES (:d, :p)
    """)
    depts = Department.query.all()
    for dep in depts:
        for perm in PERMISSIONS:
            db.session.execute(sql, {"d": dep.id, "p": perm})
    db.session.commit()

def seed_legacy_schema():
    """
    Legacy schema (before refactor):
      department_permissions(department_id INTEGER, code TEXT, allowed BOOLEAN, ...)
    """
    sql = text("""
        INSERT OR IGNORE INTO department_permissions (department_id, code, allowed)
        VALUES (:d, :c, :a)
    """)
    depts = Department.query.all()
    for dep in depts:
        for code in PERMISSIONS:
            db.session.execute(sql, {"d": dep.id, "c": code, "a": False})
    db.session.commit()

def main():
    app = create_app()
    with app.app_context():
        if schema_is_new():
            print("↪ Detected NEW department_permissions schema (permission column). Seeding…")
            seed_new_schema()
        else:
            print("↪ Detected LEGACY department_permissions schema (code/allowed). Seeding…")
            seed_legacy_schema()
        print("✅ Done.")

if __name__ == "__main__":
    sys.exit(main())
