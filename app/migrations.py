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
        _add_role_to_users,
        _add_ni_number_to_cases,
        _add_priority_fields_to_cases,
        _create_case_actions_table,
        _create_case_interactions_table,
        _create_interaction_tags_table,
        _create_follow_up_tasks_table,
        _create_case_attachments_table,
        _create_invite_codes_table,
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


def _add_role_to_users():
    """Migration: Add role column to users table."""
    if _column_exists("users", "role"):
        return

    logger.info("Applying migration: add role to users")
    db.session.execute(
        db.text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'worker'")
    )
    db.session.commit()


def _add_priority_fields_to_cases():
    """Migration: Add case fields required for the viable MVP."""
    columns = {
        "date_of_birth": "VARCHAR(10)",
        "age": "INTEGER",
        "gender": "VARCHAR(50)",
        "physical_description": "TEXT",
        "other_contact": "VARCHAR(200)",
        "consent_status": "VARCHAR(20) NOT NULL DEFAULT 'unknown'",
        "consent_date": "VARCHAR(10)",
        "risk_rating": "VARCHAR(20) NOT NULL DEFAULT 'unknown'",
        "risk_notes": "TEXT",
        "mental_health_notes": "TEXT",
        "current_situation": "VARCHAR(100)",
        "archived_at": "DATETIME",
        "assigned_user_id": "INTEGER",
    }

    for column, ddl_type in columns.items():
        if _column_exists("cases", column):
            continue
        logger.info(f"Applying migration: add {column} to cases")
        db.session.execute(
            db.text(f"ALTER TABLE cases ADD COLUMN {column} {ddl_type}")
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


def _create_case_interactions_table():
    """Migration: Create case_interactions table."""
    if _table_exists("case_interactions"):
        return

    logger.info("Applying migration: create case_interactions table")
    db.session.execute(db.text("""
        CREATE TABLE case_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            note_content TEXT,
            outcome VARCHAR(200),
            location_w3w VARCHAR(200),
            location_lat FLOAT,
            location_lng FLOAT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """))
    db.session.commit()


def _create_interaction_tags_table():
    """Migration: Create interaction_tags table."""
    if _table_exists("interaction_tags"):
        return

    logger.info("Applying migration: create interaction_tags table")
    db.session.execute(db.text("""
        CREATE TABLE interaction_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id INTEGER NOT NULL,
            tag_type VARCHAR(50) NOT NULL,
            label VARCHAR(200) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (interaction_id) REFERENCES case_interactions(id)
        )
    """))
    db.session.commit()


def _create_follow_up_tasks_table():
    """Migration: Create follow_up_tasks table."""
    if _table_exists("follow_up_tasks"):
        return

    logger.info("Applying migration: create follow_up_tasks table")
    db.session.execute(db.text("""
        CREATE TABLE follow_up_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            created_by_user_id INTEGER NOT NULL,
            assigned_user_id INTEGER,
            title VARCHAR(200) NOT NULL,
            due_date VARCHAR(10),
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (case_id) REFERENCES cases(id),
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (assigned_user_id) REFERENCES users(id)
        )
    """))
    db.session.commit()


def _create_case_attachments_table():
    """Migration: Create case_attachments table."""
    if _table_exists("case_attachments"):
        return

    logger.info("Applying migration: create case_attachments table")
    db.session.execute(db.text("""
        CREATE TABLE case_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            interaction_id INTEGER,
            user_id INTEGER NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            stored_path VARCHAR(500) NOT NULL,
            content_type VARCHAR(100),
            size_bytes INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id),
            FOREIGN KEY (interaction_id) REFERENCES case_interactions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """))
    db.session.commit()


def _create_invite_codes_table():
    """Migration: Create invite_codes table."""
    if _table_exists("invite_codes"):
        return

    logger.info("Applying migration: create invite_codes table")
    db.session.execute(db.text("""
        CREATE TABLE invite_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(100) NOT NULL UNIQUE,
            label VARCHAR(200),
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            max_uses INTEGER NOT NULL DEFAULT 1,
            uses INTEGER NOT NULL DEFAULT 0,
            created_by_user_id INTEGER,
            used_by_user_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            used_at DATETIME,
            FOREIGN KEY (created_by_user_id) REFERENCES users(id),
            FOREIGN KEY (used_by_user_id) REFERENCES users(id)
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
