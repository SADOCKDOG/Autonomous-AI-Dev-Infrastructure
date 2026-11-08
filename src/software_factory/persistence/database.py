"""Capa de persistencia SQLite local."""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from software_factory.settings import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    data_classification TEXT NOT NULL DEFAULT 'project_context',
    acceptance_criteria TEXT NOT NULL DEFAULT '[]', -- JSON array
    assigned_agent TEXT,
    branch_name TEXT,
    worktree_path TEXT,
    target_repo TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    agent_role TEXT,
    payload TEXT NOT NULL DEFAULT '{}', -- JSON object
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}', -- JSON sanitizado sin secretos
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'medium', -- low, medium, high, critical
    category TEXT NOT NULL DEFAULT 'policy_violation', -- policy_violation, secret_detected, sandbox_failure, timeout, manual
    status TEXT NOT NULL DEFAULT 'open', -- open, analyzing, resolved, closed
    reported_by TEXT NOT NULL DEFAULT 'system',
    resolution_notes TEXT DEFAULT '',
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_events_task_id ON task_events(task_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
"""

OWNER_AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Signed authorizations are immutable payloads. Lifecycle changes are recorded
-- as application append-only events; status is a projection updated under BEGIN IMMEDIATE.
-- "Append-only" constrains the application code only; it does not protect the
-- SQLite file against direct filesystem access or modification.
CREATE TABLE IF NOT EXISTS owner_authorizations (
    authorization_id TEXT PRIMARY KEY,
    task_id TEXT,
    repository TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    head_sha TEXT NOT NULL,
    base_ref TEXT NOT NULL,
    base_sha TEXT NOT NULL,
    diff_sha256 TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision = 'AUTHORIZE_MERGE'),
    signer_identity TEXT NOT NULL,
    github_login TEXT NOT NULL,
    key_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'IN_PROGRESS', 'REVOKED', 'INVALIDATED', 'EXPIRED', 'FAILED', 'MERGE_UNKNOWN', 'CONSUMED')),
    merge_sha TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS owner_authorization_events (
    event_id TEXT PRIMARY KEY,
    authorization_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(authorization_id) REFERENCES owner_authorizations(authorization_id)
);

CREATE TABLE IF NOT EXISTS owner_authorization_nonces (
    nonce TEXT PRIMARY KEY,
    authorization_id TEXT NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('REVOKE', 'EXECUTE')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(authorization_id) REFERENCES owner_authorizations(authorization_id)
);

CREATE INDEX IF NOT EXISTS idx_owner_auth_pr ON owner_authorizations(repository, pr_number, state);
CREATE INDEX IF NOT EXISTS idx_owner_auth_events_id ON owner_authorization_events(authorization_id, created_at);
"""

OWNER_AUTH_SCHEMA_VERSION = 1


def init_db(db_path: Path | None = None) -> Path:
    """Inicializa la base de datos creando las tablas base si no existen.

    No crea tablas Owner Auth. Esas tablas se crean con migrate_owner_auth_db().
    """
    target_path = db_path or settings.get_sqlite_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(target_path, timeout=30.0) as conn:
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.executescript(SCHEMA_SQL)
            conn.commit()
    except sqlite3.OperationalError:
        # Base de datos ya inicializada o bloqueada temporalmente por la Consola Desktop
        pass

    return target_path


def migrate_owner_auth_db(db_path: Path | None = None) -> Path:
    """Apply Owner Auth schema migration explicitly; surface errors (fail-closed).

    This is never called by init_db(). Applying it to any environment should be
    treated as a separate authorized operation. Any failure is visible to the
    caller and aborts without leaving a partially active authorization.
    """
    target_path = db_path or settings.get_sqlite_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(target_path, timeout=30.0) as conn:
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.executescript(OWNER_AUTH_SCHEMA_SQL)
            row = conn.execute(
                "SELECT version FROM schema_migrations WHERE version = ?",
                (OWNER_AUTH_SCHEMA_VERSION,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (OWNER_AUTH_SCHEMA_VERSION,),
                )
            conn.commit()
    except sqlite3.Error:
        raise
    return target_path


def get_owner_auth_schema_version(db_path: Path | None = None) -> int | None:
    """Return installed Owner Auth schema version, or None if not migrated."""
    target_path = db_path or settings.get_sqlite_path()
    if not target_path.is_file():
        return None
    try:
        with sqlite3.connect(target_path, timeout=10.0) as conn:
            conn.row_factory = sqlite3.Row
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if table is None:
                return None
            row = conn.execute(
                "SELECT MAX(version) AS version FROM schema_migrations"
            ).fetchone()
            return int(row["version"]) if row and row["version"] is not None else None
    except sqlite3.Error:
        raise


@contextmanager
def get_db(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Generador de conexión con row_factory como sqlite3.Row."""
    target_path = db_path or settings.get_sqlite_path()
    conn = sqlite3.connect(target_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
