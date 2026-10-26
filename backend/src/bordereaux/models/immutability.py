"""Append-only / immutable table enforcement, at two layers:

1. **ORM guard** - a ``before_flush`` hook rejects any UPDATE or DELETE of an
   instance whose class sets ``__append_only__ = True``. This catches mistakes
   in application code with a clear error before any SQL is emitted.
2. **Database triggers** (SQLite) - ``BEFORE UPDATE`` / ``BEFORE DELETE``
   triggers that ``RAISE(ABORT)``, so even raw SQL cannot mutate the rows.
   Created by ``Base.metadata.create_all`` (via the DDL hook below) and by the
   Alembic migrations (which inline the same SQL).
   On PostgreSQL the equivalent is ``REVOKE UPDATE, DELETE`` (SECURITY_AND_AUDIT.md §5.3).
"""

from __future__ import annotations

from sqlalchemy import DDL, Table, event
from sqlalchemy.orm import Session

from bordereaux.core.exceptions import ConstraintViolationError


class AppendOnlyViolation(ConstraintViolationError):
    code = "APPEND_ONLY_VIOLATION"
    status_code = 409
    default_message = "This record is immutable and cannot be modified or deleted"


def sqlite_trigger_statements(table_name: str) -> list[str]:
    """SQL for the append-only triggers on ``table_name`` (also used verbatim in migrations)."""
    return [
        f"CREATE TRIGGER trg_{table_name}_no_update BEFORE UPDATE ON {table_name} "
        f"BEGIN SELECT RAISE(ABORT, '{table_name} is append-only'); END",
        f"CREATE TRIGGER trg_{table_name}_no_delete BEFORE DELETE ON {table_name} "
        f"BEGIN SELECT RAISE(ABORT, '{table_name} is append-only'); END",
    ]


def register_append_only_table(table: Table) -> None:
    for stmt in sqlite_trigger_statements(table.name):
        event.listen(table, "after_create", DDL(stmt).execute_if(dialect="sqlite"))


@event.listens_for(Session, "before_flush")
def _reject_append_only_mutations(session: Session, _flush_context, _instances) -> None:
    for obj in session.deleted:
        if getattr(type(obj), "__append_only__", False):
            raise AppendOnlyViolation(f"{type(obj).__tablename__} rows cannot be deleted")
    for obj in session.dirty:
        if getattr(type(obj), "__append_only__", False) and session.is_modified(obj, include_collections=False):
            raise AppendOnlyViolation(f"{type(obj).__tablename__} rows cannot be updated")
