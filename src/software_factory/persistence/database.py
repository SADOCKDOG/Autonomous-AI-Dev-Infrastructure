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


def init_db(db_path: Path | None = None) -> Path:
    """Inicializa la base de datos creando las tablas si no existen."""
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
