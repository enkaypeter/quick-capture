"""Lightweight schema migrations for SQLite.

Runs on every app startup. Each migration checks if the change has already
been applied before executing, making them idempotent and safe to re-run.

For the MVP this avoids the overhead of Alembic while keeping production
databases in sync with model changes.
"""

import logging

from app.extensions import db

logger = logging.getLogger(__name__)


def run_migrations():
    """Run all pending migrations against the current database."""
    migrations = [
        _add_ni_number_to_cases,
        _create_case_actions_table,
        _create_audit_logs_table,
    ]

    for migration in migrations:
        try:
            migration()
        except Exception as e:
            logger.error(f"Migration {migration.__name__} failed: {e}")
            raise


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    result = db.session.execute(
        db.text(f"PRAGMA table_info({table})")
    )
    columns = [row[1] for row in result]
    return column in columns


def _table_exists(table: str) -> bool:
    """Check if a table exists in the database."""
    result = db.session.execute(
        db.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table},
    )
    return result.fetchone() is not None


def _add_ni_number_to_cases():
    """Migration: Add ni_number column to cases table."""
    if _column_exists("cases", "ni_number"):
        return

    logger.info("Applying migration: add ni_number to cases")
    db.session.execute(
        db.text("ALTER TABLE cases ADD COLUMN ni_number VARCHAR(20)")
    )
    db.session.commit()


def _create_case_actions_table():
    """Migration: Create case_actions table."""
    if _table_exists("case_actions"):
        return

    logger.info("Applying migration: create case_actions table")
    db.session.execute(db.text("""
        CREATE TABLE case_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            label VARCHAR(200) NOT NULL,
            completed BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
    """))
    db.session.commit()


def _create_audit_logs_table():
    """Migration: Create audit_logs table."""
    if _table_exists("audit_logs"):
        return

    logger.info("Applying migration: create audit_logs table")
    db.session.execute(db.text("""
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action VARCHAR(20) NOT NULL,
            field_name VARCHAR(100) NOT NULL,
            old_value TEXT,
            new_value TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """))
    db.session.commit()
