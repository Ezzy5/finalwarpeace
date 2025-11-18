# app/dev_schema.py
from __future__ import annotations
from typing import Dict, Set, Optional

from sqlalchemy import text, Table, Column, Integer, String, Text as SA_Text, Boolean, DateTime, Float, JSON
from sqlalchemy.sql.schema import Index
from app.extensions import db


# -------- SQLite DDL helpers --------

_SQLITE_TYPE = {
    Integer: "INTEGER",
    Boolean: "INTEGER",   # SQLite booleans are ints (0/1)
    DateTime: "DATETIME",
    Float: "REAL",
    SA_Text: "TEXT",
    String: "VARCHAR",
    JSON: "TEXT",         # stored as TEXT; SQLite has json1 but type affinity is TEXT
}

def _sqlite_coltype(col: Column) -> str:
    t = type(col.type)
    if t in _SQLITE_TYPE:
        base = _SQLITE_TYPE[t]
        if isinstance(col.type, String) and col.type.length:
            return f"VARCHAR({int(col.type.length)})"
        return base
    # Fallback
    return "TEXT"


def _default_sql_for(col: Column) -> Optional[str]:
    """
    A pragmatic default to allow ALTER TABLE ADD COLUMN on existing rows when column is NOT NULL.
    Only used if column.nullable is False AND no server_default is present.
    """
    if col.server_default is not None:
        return None  # SQLite will use it
    if col.nullable:
        return None

    # Choose a safe default by type
    if isinstance(col.type, (Integer, Boolean, Float)):
        return "0"
    if isinstance(col.type, DateTime):
        return "'1970-01-01 00:00:00'"
    if isinstance(col.type, JSON):
        return "'{}'"
    # String/Text and everything else
    return "''"


def _existing_columns_sqlite(table_name: str) -> Set[str]:
    rows = db.session.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
    # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
    return {row[1] for row in rows}


def _ensure_indexes_sqlite(table: Table):
    # Create simple single-column indexes where defined with index=True
    for col in table.columns:
        if getattr(col, "index", False):
            idx_name = f"ix_{table.name}_{col.name}"
            db.session.execute(
                text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table.name}" ("{col.name}")')
            )
    # Create explicit Index() objects declared on the table
    for idx in table.indexes:  # type: Index
        try:
            cols = ", ".join([f'"{c.name}"' for c in idx.expressions])
            db.session.execute(
                text(f'CREATE INDEX IF NOT EXISTS "{idx.name}" ON "{table.name}" ({cols})')
            )
        except Exception:
            # Best-effort; skip complex expressions
            pass


def _add_missing_columns_sqlite(table: Table, table_cols: Set[str]):
    for col in table.columns:
        if col.name in table_cols:
            continue
        # Do not try to add PK or FK constraints here; just add the column
        coltype = _sqlite_coltype(col)
        default_sql = _default_sql_for(col)
        default_clause = f" DEFAULT {default_sql}" if default_sql is not None else ""
        notnull_clause = "" if col.nullable else " NOT NULL"

        ddl = (
            f'ALTER TABLE "{table.name}" '
            f'ADD COLUMN "{col.name}" {coltype}{notnull_clause}{default_clause}'
        )
        db.session.execute(text(ddl))
        table_cols.add(col.name)


def ensure_sqlite_schema(metadata=None) -> None:
    """
    Idempotent: creates all tables from metadata if missing,
    then adds any missing columns with safe defaults,
    and creates basic indexes. Dev-only; never needed on Postgres.
    """
    eng = db.engine
    if eng.dialect.name != "sqlite":
        return

    if metadata is None:
        metadata = db.metadata

    # 1) Create any missing tables first (no migrations)
    metadata.create_all(bind=eng)

    # 2) For each table, add missing columns and ensure indexes
    for table in list(metadata.tables.values()):  # type: Table
        name = table.name
        if not name or name.startswith("sqlite_"):
            continue
        cols = _existing_columns_sqlite(name)
        _add_missing_columns_sqlite(table, cols)
        _ensure_indexes_sqlite(table)

    db.session.commit()
