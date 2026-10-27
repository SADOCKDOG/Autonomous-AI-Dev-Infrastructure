"""Pruebas unitarias de la consola de escritorio para Windows."""

import sys
import sqlite3
from pathlib import Path

try:
    import pytest
    pytest.importorskip("tkinter")
except ImportError:
    pytest = None

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from desktop_console.app import DB_PATH, init_local_db


def test_desktop_console_init_and_db(tmp_path):
    test_db = tmp_path / "factory.db"
    init_local_db(test_db)

    with sqlite3.connect(test_db) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cursor.fetchall()}
        assert "tasks" in tables
        assert "task_events" in tables
        assert "audit_logs" in tables
        assert "incidents" in tables


def test_desktop_console_headless_export(tmp_path, monkeypatch):
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        r.destroy()
    except Exception:
        pytest.skip("Entorno sin servidor grafico (display) para Tkinter")

    from desktop_console.app import DesktopConsoleApp

    test_db = tmp_path / "factory.db"
    init_local_db(test_db)
    monkeypatch.setattr("desktop_console.app.DB_PATH", test_db)

    with sqlite3.connect(test_db) as conn:
        conn.execute(
            """
            INSERT INTO tasks (id, title, description, status, priority, data_classification)
            VALUES ('TASK-TEST-01', 'Tarea de Prueba Consola', 'Descripcion', 'REVIEW', 'high', 'approved_remote')
            """
        )
        conn.execute(
            """
            INSERT INTO incidents (id, task_id, title, description, severity, category, status, reported_by)
            VALUES ('INC-TEST-01', 'TASK-TEST-01', 'Incidencia de Prueba', 'Detalle', 'high', 'policy_violation', 'open', 'system')
            """
        )

    app = DesktopConsoleApp()
    app.withdraw()
    app.update()

    app.export_audit_report(show_dialog=False)

    reports_dir = ROOT_DIR / "reports"
    reports = list(reports_dir.glob("informe_auditoria_*.md"))
    assert len(reports) > 0, "Debe haberse generado al menos un informe de auditoria"

    app.destroy()
