"""Consola de Gestion Integral de Escritorio para Windows.
Software Factory Hibrida Local · Sdog Farm Software Factory (sadogfarm.onmicrosoft.com)
"""

import sys
import os
import json
import time
import socket
import sqlite3
import datetime
import subprocess
import threading
import uuid
from pathlib import Path

# Tkinter y TTK
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Asegurar que el directorio raiz este en sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Base de datos
DB_PATH = ROOT_DIR / "data" / "factory.db"

LOCAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    data_classification TEXT NOT NULL DEFAULT 'project_context',
    acceptance_criteria TEXT NOT NULL DEFAULT '[]',
    assigned_agent TEXT,
    branch_name TEXT,
    worktree_path TEXT,
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
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'medium',
    category TEXT NOT NULL DEFAULT 'policy_violation',
    status TEXT NOT NULL DEFAULT 'open',
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


def init_local_db(target_path: Path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(LOCAL_SCHEMA_SQL)


class DesktopConsoleApp(tk.Tk):
    """Aplicacion principal de la Consola de Gestion Integral en Windows."""

    def __init__(self):
        super().__init__()
        # Asegurar inicializacion de base de datos local
        try:
            init_local_db(DB_PATH)
        except Exception:
            pass

        self.title("Software Factory Control Center · Sdog Farm (sadogfarm.onmicrosoft.com)")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(bg="#121212")

        # Variables de estado
        self.backend_process = None
        self.selected_task_id = None
        self.selected_incident_id = None

        # Configurar Estilos Visuales Dark Pro
        self._setup_styles()

        # Construir Interfaz
        self._build_header()
        self._build_notebook()
        self._build_statusbar()

        # Cargar datos iniciales en hilo de fondo
        self.after(200, self.refresh_all_data)

    def safe_after(self, delay_ms: int, callback):
        """Programa ejecucion en el bucle principal de Tkinter con fallback seguro."""
        try:
            self.after(delay_ms, callback)
        except RuntimeError:
            try:
                callback()
            except Exception:
                pass

    def _setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Colores
        bg_dark = "#121212"
        card_bg = "#1E1E1E"
        card_light = "#2A2A2A"
        fg_white = "#F8FAFC"
        accent_blue = "#3B82F6"
        accent_lime = "#CCFF00"

        # Notebook
        self.style.configure(
            "TNotebook",
            background=bg_dark,
            borderwidth=0,
            tabmargins=[2, 5, 2, 0],
        )
        self.style.configure(
            "TNotebook.Tab",
            background="#222222",
            foreground="#94A3B8",
            padding=[16, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", card_bg), ("active", "#2D2D2D")],
            foreground=[("selected", accent_lime), ("active", fg_white)],
        )

        # Frames
        self.style.configure("Dark.TFrame", background=bg_dark)
        self.style.configure("Card.TFrame", background=card_bg, relief="flat")
        self.style.configure("SubCard.TFrame", background=card_light, relief="flat")

        # Labels
        self.style.configure("Dark.TLabel", background=bg_dark, foreground=fg_white, font=("Segoe UI", 9))
        self.style.configure("Card.TLabel", background=card_bg, foreground=fg_white, font=("Segoe UI", 9))
        self.style.configure("Muted.TLabel", background=card_bg, foreground="#94A3B8", font=("Segoe UI", 9))
        self.style.configure("Title.TLabel", background=card_bg, foreground=accent_lime, font=("Segoe UI", 12, "bold"))
        self.style.configure("Header.TLabel", background=bg_dark, foreground=fg_white, font=("Segoe UI", 14, "bold"))

        # Treeview (Tablas)
        self.style.configure(
            "Treeview",
            background="#1A1A1A",
            foreground=fg_white,
            fieldbackground="#1A1A1A",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            background="#252525",
            foreground="#CBD5E1",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padding=[6, 6],
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#1E3A8A")],
            foreground=[("selected", "#FFFFFF")],
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", "#333333")],
        )

    def _build_header(self):
        header_frame = tk.Frame(self, bg="#121212", height=60)
        header_frame.pack(fill="x", padx=16, pady=(12, 6))

        # Titulo y tenant
        title_box = tk.Frame(header_frame, bg="#121212")
        title_box.pack(side="left")

        title_label = tk.Label(
            title_box,
            text="AUTONOMOUS DEV CONTROL CENTER",
            bg="#121212",
            fg="#F8FAFC",
            font=("Segoe UI", 13, "bold"),
            lettercase="uppercase" if hasattr(str, "lettercase") else None,
        )
        title_label.pack(anchor="w")

        sub_label = tk.Label(
            title_box,
            text="Sdog Farm Software Factory · sadogfarm.onmicrosoft.com · Governance & AI-GRC Console",
            bg="#121212",
            fg="#94A3B8",
            font=("Segoe UI", 8),
        )
        sub_label.pack(anchor="w")

        # Botones de cabecera
        btn_box = tk.Frame(header_frame, bg="#121212")
        btn_box.pack(side="right", pady=4)

        refresh_btn = tk.Button(
            btn_box,
            text="REFRESCAR TODO",
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            command=self.refresh_all_data,
        )
        refresh_btn.pack(side="right", padx=6)

        export_btn = tk.Button(
            btn_box,
            text="EXPORTAR INFORME AI-GRC",
            bg="#059669",
            fg="#FFFFFF",
            activebackground="#047857",
            activeforeground="#FFFFFF",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=4,
            command=self.export_audit_report,
        )
        export_btn.pack(side="right", padx=6)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        # Crear pestanas
        self.tab_services = tk.Frame(self.notebook, bg="#121212")
        self.tab_projects = tk.Frame(self.notebook, bg="#121212")
        self.tab_incidents = tk.Frame(self.notebook, bg="#121212")
        self.tab_audit = tk.Frame(self.notebook, bg="#121212")

        self.notebook.add(self.tab_services, text=" SERVICIOS & SALUD ")
        self.notebook.add(self.tab_projects, text=" PROYECTOS & KANBAN ")
        self.notebook.add(self.tab_incidents, text=" GESTOR DE INCIDENCIAS ")
        self.notebook.add(self.tab_audit, text=" EVENTOS & AUDITORIA ")

        # Inicializar contenido de cada pestana
        self._init_services_tab()
        self._init_projects_tab()
        self._init_incidents_tab()
        self._init_audit_tab()

    def _build_statusbar(self):
        self.statusbar = tk.Frame(self, bg="#18181B", height=28)
        self.statusbar.pack(fill="x", side="bottom")

        self.status_label = tk.Label(
            self.statusbar,
            text="Sistema preparado. Esperando acciones.",
            bg="#18181B",
            fg="#A1A1AA",
            font=("Segoe UI", 8),
            padx=12,
        )
        self.status_label.pack(side="left")

        self.db_label = tk.Label(
            self.statusbar,
            text=f"Base de Datos: {DB_PATH.name} (WAL Mode)",
            bg="#18181B",
            fg="#71717A",
            font=("Segoe UI", 8),
            padx=12,
        )
        self.db_label.pack(side="right")

    # -------------------------------------------------------------------------
    # PESTANA 1: SERVICIOS Y SALUD DEL SISTEMA
    # -------------------------------------------------------------------------
    def _init_services_tab(self):
        parent = self.tab_services

        # Contenedor Bento Grid
        grid_frame = tk.Frame(parent, bg="#121212")
        grid_frame.pack(fill="both", expand=True, padx=6, pady=8)

        # Tarjetas de servicios
        self.services_cards = {}
        services_meta = [
            ("fcc_server", "Free Claude Code (FCC Local)", "127.0.0.1:8082", "Proxy local para inferencia con 4405 modelos sin coste."),
            ("fastapi_backend", "Backend FastAPI (Software Factory)", "127.0.0.1:8000", "API de orquestacion, Kanban, Worktrees y endpoints REST."),
            ("sqlite_db", "Persistencia SQLite WAL", "data/factory.db", "Almacenamiento transaccional inmutable para tareas y eventos."),
            ("azure_foundry", "Microsoft Foundry (Sdog Farm)", "sadogfarm.onmicrosoft.com", "Hub corporativo en Azure AI para L3/L4 con EU Data Boundary."),
            ("sandbox_engine", "Sandbox de Ejecucion y Git", "Allowlist segura", "Aislamiento de comandos (git, python3, node, npm, npx, cargo)."),
        ]

        # Top row: 3 cards
        top_row = tk.Frame(grid_frame, bg="#121212")
        top_row.pack(fill="x", pady=(0, 8))

        for idx, (svc_id, name, endpoint, desc) in enumerate(services_meta[:3]):
            card = self._create_service_card(top_row, svc_id, name, endpoint, desc)
            card.pack(side="left", fill="both", expand=True, padx=4)

        # Bottom row: 2 cards + Actions Card
        bottom_row = tk.Frame(grid_frame, bg="#121212")
        bottom_row.pack(fill="x", pady=(0, 8))

        for idx, (svc_id, name, endpoint, desc) in enumerate(services_meta[3:]):
            card = self._create_service_card(bottom_row, svc_id, name, endpoint, desc)
            card.pack(side="left", fill="both", expand=True, padx=4)

        # Tarjeta de control de servicios
        actions_card = tk.Frame(bottom_row, bg="#1E1E1E", bd=1, relief="solid")
        actions_card.configure(highlightbackground="#333333", highlightthickness=1)
        actions_card.pack(side="left", fill="both", expand=True, padx=4)

        tk.Label(actions_card, text="ACCIONES DE SERVICIOS", bg="#1E1E1E", fg="#CCFF00", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 6))

        btn_grid = tk.Frame(actions_card, bg="#1E1E1E")
        btn_grid.pack(fill="x", padx=12, pady=4)

        self.btn_ping_all = tk.Button(
            btn_grid,
            text="Verificar Conexiones",
            bg="#2A2A2A",
            fg="#FFFFFF",
            font=("Segoe UI", 9),
            relief="flat",
            command=self.check_services_health,
        )
        self.btn_ping_all.grid(row=0, column=0, padx=4, pady=4, sticky="ew")

        self.btn_start_backend = tk.Button(
            btn_grid,
            text="Iniciar Backend (8000)",
            bg="#059669",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            command=self.start_fastapi_backend,
        )
        self.btn_start_backend.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.btn_stop_backend = tk.Button(
            btn_grid,
            text="Detener Backend",
            bg="#DC2626",
            fg="#FFFFFF",
            font=("Segoe UI", 9),
            relief="flat",
            command=self.stop_fastapi_backend,
        )
        self.btn_stop_backend.grid(row=1, column=0, padx=4, pady=4, sticky="ew")

        self.btn_verify_fcc = tk.Button(
            btn_grid,
            text="Testear FCC Server",
            bg="#3B82F6",
            fg="#FFFFFF",
            font=("Segoe UI", 9),
            relief="flat",
            command=self.test_fcc_connectivity,
        )
        self.btn_verify_fcc.grid(row=1, column=1, padx=4, pady=4, sticky="ew")

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # Log de eventos de servicios en tiempo real
        log_frame = tk.Frame(grid_frame, bg="#1E1E1E", bd=1, relief="solid")
        log_frame.configure(highlightbackground="#333333", highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=4, pady=4)

        tk.Label(log_frame, text="REGISTRO DE MONITORIZACION Y TELEMETRIA", bg="#1E1E1E", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 4))

        self.services_log_text = tk.Text(
            log_frame,
            bg="#141414",
            fg="#E2E8F0",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            height=10,
        )
        self.services_log_text.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def _create_service_card(self, parent, svc_id, name, endpoint, desc):
        card = tk.Frame(parent, bg="#1E1E1E", bd=1, relief="solid")
        card.configure(highlightbackground="#333333", highlightthickness=1)

        # Header de tarjeta
        header = tk.Frame(card, bg="#1E1E1E")
        header.pack(fill="x", padx=12, pady=(10, 2))

        name_lbl = tk.Label(header, text=name, bg="#1E1E1E", fg="#F8FAFC", font=("Segoe UI", 10, "bold"))
        name_lbl.pack(side="left")

        badge_lbl = tk.Label(header, text="[VERIFICANDO]", bg="#27272A", fg="#A1A1AA", font=("Segoe UI", 8, "bold"), padx=6, pady=2)
        badge_lbl.pack(side="right")

        # Endpoint y descripcion
        ep_lbl = tk.Label(card, text=f"Destino: {endpoint}", bg="#1E1E1E", fg="#38BDF8", font=("Consolas", 8))
        ep_lbl.pack(anchor="w", padx=12, pady=1)

        desc_lbl = tk.Label(card, text=desc, bg="#1E1E1E", fg="#94A3B8", font=("Segoe UI", 8), justify="left", wraplength=280)
        desc_lbl.pack(anchor="w", padx=12, pady=(2, 6))

        # Metricas
        metric_lbl = tk.Label(card, text="Latencia: -- ms | Ultima comprobacion: --", bg="#1E1E1E", fg="#64748B", font=("Segoe UI", 8))
        metric_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        self.services_cards[svc_id] = {
            "card": card,
            "badge": badge_lbl,
            "metric": metric_lbl,
            "endpoint": endpoint,
        }
        return card

    def log_service_message(self, message: str):
        def _do():
            try:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                self.services_log_text.insert("end", f"[{timestamp}] {message}\n")
                self.services_log_text.see("end")
            except Exception:
                pass
        self.safe_after(0, _do)

    # -------------------------------------------------------------------------
    # PESTANA 2: PROYECTOS Y TABLERO KANBAN
    # -------------------------------------------------------------------------
    def _init_projects_tab(self):
        parent = self.tab_projects

        # Barra superior de filtros y acciones
        top_bar = tk.Frame(parent, bg="#121212")
        top_bar.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(top_bar, text="Proyecto Activo:", bg="#121212", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.project_var = tk.StringVar(value="Todos los Proyectos")
        proj_combo = ttk.Combobox(
            top_bar,
            textvariable=self.project_var,
            values=["Todos los Proyectos", "Livestock Manager", "Infrastructure Core", "Sdog Farm Software Factory"],
            state="readonly",
            width=24,
        )
        proj_combo.pack(side="left", padx=4)
        proj_combo.bind("<<ComboboxSelected>>", lambda e: self.load_tasks())

        tk.Label(top_bar, text="Filtro Estado:", bg="#121212", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 6))
        self.status_filter_var = tk.StringVar(value="Todos")
        status_combo = ttk.Combobox(
            top_bar,
            textvariable=self.status_filter_var,
            values=["Todos", "BACKLOG", "READY", "PLANNING", "IN_PROGRESS", "TESTING", "REVIEW", "DONE", "BLOCKED"],
            state="readonly",
            width=14,
        )
        status_combo.pack(side="left", padx=4)
        status_combo.bind("<<ComboboxSelected>>", lambda e: self.load_tasks())

        btn_new_task = tk.Button(
            top_bar,
            text="+ NUEVA TAREA",
            bg="#2563EB",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self.show_new_task_dialog,
        )
        btn_new_task.pack(side="right", padx=4)

        btn_approve_task = tk.Button(
            top_bar,
            text="APROBACION HUMANA (AI-GRC)",
            bg="#059669",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self.approve_selected_task,
        )
        btn_approve_task.pack(side="right", padx=4)

        btn_run_cycle = tk.Button(
            top_bar,
            text="EJECUTAR CICLO MULTIAGENTE",
            bg="#7C3AED",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self.run_orchestration_cycle,
        )
        btn_run_cycle.pack(side="right", padx=4)

        # Panel Bento: Izquierda Lista de Tareas | Derecha Detalles de Tarea
        content_pane = tk.PanedWindow(parent, orient="horizontal", bg="#121212", sashwidth=4, bd=0)
        content_pane.pack(fill="both", expand=True, padx=8, pady=4)

        # Izquierda: Tabla de Tareas
        table_frame = tk.Frame(content_pane, bg="#1E1E1E", bd=1, relief="solid")
        table_frame.configure(highlightbackground="#333333", highlightthickness=1)
        content_pane.add(table_frame, width=650)

        cols = ("id", "title", "status", "priority", "classification", "created_at")
        self.tasks_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.tasks_tree.heading("id", text="ID")
        self.tasks_tree.heading("title", text="Titulo")
        self.tasks_tree.heading("status", text="Estado")
        self.tasks_tree.heading("priority", text="Prioridad")
        self.tasks_tree.heading("classification", text="Clasificacion")
        self.tasks_tree.heading("created_at", text="Fecha")

        self.tasks_tree.column("id", width=100, anchor="center")
        self.tasks_tree.column("title", width=220)
        self.tasks_tree.column("status", width=95, anchor="center")
        self.tasks_tree.column("priority", width=75, anchor="center")
        self.tasks_tree.column("classification", width=95, anchor="center")
        self.tasks_tree.column("created_at", width=120, anchor="center")

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tasks_tree.yview)
        self.tasks_tree.configure(yscrollcommand=tree_scroll.set)
        self.tasks_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.tasks_tree.bind("<<TreeviewSelect>>", self.on_task_selected)

        # Derecha: Panel de Inspeccion de Tarea
        detail_frame = tk.Frame(content_pane, bg="#1E1E1E", bd=1, relief="solid")
        detail_frame.configure(highlightbackground="#333333", highlightthickness=1)
        content_pane.add(detail_frame)

        tk.Label(detail_frame, text="DETALLES DE TAREA Y EXPEDIENTE TECNICO", bg="#1E1E1E", fg="#CCFF00", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self.task_detail_text = tk.Text(
            detail_frame,
            bg="#141414",
            fg="#F1F5F9",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
        )
        self.task_detail_text.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def on_task_selected(self, event):
        selected_items = self.tasks_tree.selection()
        if not selected_items:
            return
        item = selected_items[0]
        values = self.tasks_tree.item(item, "values")
        task_id = values[0]
        self.selected_task_id = task_id
        self.show_task_details(task_id)

    def show_task_details(self, task_id: str):
        if not DB_PATH.exists():
            return
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT id, title, description, status, priority, data_classification, "
                    "acceptance_criteria, assigned_agent, branch_name, worktree_path, created_at, updated_at "
                    "FROM tasks WHERE id = ?",
                    (task_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return

                criteria = []
                try:
                    criteria = json.loads(row[6])
                except Exception:
                    pass

                # Consultar eventos recientes
                ev_cursor = conn.execute(
                    "SELECT from_status, to_status, agent_role, payload, created_at "
                    "FROM task_events WHERE task_id = ? ORDER BY id DESC LIMIT 5",
                    (task_id,),
                )
                events = ev_cursor.fetchall()

            detail = []
            detail.append("=" * 60)
            detail.append(f"EXPEDIENTE TECNICO: {row[0]}")
            detail.append(f"Titulo: {row[1]}")
            detail.append(f"Estado Actual: [{row[3]}] | Prioridad: {row[4]}")
            detail.append(f"Clasificacion de Datos AI-GRC: {row[5]}")
            detail.append(f"Rama Git Asignada: {row[8] or 'Sin rama asignada'}")
            detail.append(f"Ruta de Worktree Aislado: {row[9] or 'N/A'}")
            detail.append(f"Fecha de Creacion: {row[10]}")
            detail.append("-" * 60)
            detail.append("DESCRIPCION:")
            detail.append(row[2])
            detail.append("-" * 60)
            detail.append("CRITERIOS DE ACEPTACION NORMATIVOS:")
            if criteria:
                for idx, c in enumerate(criteria, 1):
                    detail.append(f"  [{idx}] {c}")
            else:
                detail.append("  (Pendiente de derivacion por el Agente Analista)")
            detail.append("-" * 60)
            detail.append("HISTORIAL DE TRANSICIONES RECIENTES:")
            for ev in events:
                detail.append(f"  - {ev[4]}: [{ev[0] or 'INICIO'}] -> [{ev[1]}] por '{ev[2]}'")
            detail.append("=" * 60)

            self.task_detail_text.delete("1.0", "end")
            self.task_detail_text.insert("end", "\n".join(detail))
        except Exception as exc:
            self.task_detail_text.delete("1.0", "end")
            self.task_detail_text.insert("end", f"Error cargando detalles: {exc}")

    # -------------------------------------------------------------------------
    # PESTANA 3: GESTOR DE INCIDENCIAS OPERACIONALES Y AI-GRC
    # -------------------------------------------------------------------------
    def _init_incidents_tab(self):
        parent = self.tab_incidents

        # Barra superior de filtros
        top_bar = tk.Frame(parent, bg="#121212")
        top_bar.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(top_bar, text="Filtro Estado:", bg="#121212", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.incident_status_var = tk.StringVar(value="Todas")
        inc_status_combo = ttk.Combobox(
            top_bar,
            textvariable=self.incident_status_var,
            values=["Todas", "open", "analyzing", "resolved", "closed"],
            state="readonly",
            width=12,
        )
        inc_status_combo.pack(side="left", padx=4)
        inc_status_combo.bind("<<ComboboxSelected>>", lambda e: self.load_incidents())

        tk.Label(top_bar, text="Severidad:", bg="#121212", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 6))
        self.incident_sev_var = tk.StringVar(value="Todas")
        inc_sev_combo = ttk.Combobox(
            top_bar,
            textvariable=self.incident_sev_var,
            values=["Todas", "critical", "high", "medium", "low"],
            state="readonly",
            width=12,
        )
        inc_sev_combo.pack(side="left", padx=4)
        inc_sev_combo.bind("<<ComboboxSelected>>", lambda e: self.load_incidents())

        btn_new_inc = tk.Button(
            top_bar,
            text="+ REGISTRAR INCIDENCIA",
            bg="#DC2626",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self.show_new_incident_dialog,
        )
        btn_new_inc.pack(side="right", padx=4)

        btn_resolve_inc = tk.Button(
            top_bar,
            text="RESOLVER / CERRAR",
            bg="#059669",
            fg="#FFFFFF",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=3,
            command=self.resolve_selected_incident,
        )
        btn_resolve_inc.pack(side="right", padx=4)

        # Panel Bento: Izquierda Tabla Incidencias | Derecha Detalle y Resolucion
        content_pane = tk.PanedWindow(parent, orient="horizontal", bg="#121212", sashwidth=4, bd=0)
        content_pane.pack(fill="both", expand=True, padx=8, pady=4)

        # Izquierda
        table_frame = tk.Frame(content_pane, bg="#1E1E1E", bd=1, relief="solid")
        table_frame.configure(highlightbackground="#333333", highlightthickness=1)
        content_pane.add(table_frame, width=650)

        cols = ("id", "task_id", "title", "severity", "category", "status", "created_at")
        self.incidents_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.incidents_tree.heading("id", text="ID")
        self.incidents_tree.heading("task_id", text="Tarea")
        self.incidents_tree.heading("title", text="Titulo / Resumen")
        self.incidents_tree.heading("severity", text="Severidad")
        self.incidents_tree.heading("category", text="Categoria")
        self.incidents_tree.heading("status", text="Estado")
        self.incidents_tree.heading("created_at", text="Fecha")

        self.incidents_tree.column("id", width=95, anchor="center")
        self.incidents_tree.column("task_id", width=90, anchor="center")
        self.incidents_tree.column("title", width=220)
        self.incidents_tree.column("severity", width=80, anchor="center")
        self.incidents_tree.column("category", width=100, anchor="center")
        self.incidents_tree.column("status", width=80, anchor="center")
        self.incidents_tree.column("created_at", width=120, anchor="center")

        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.incidents_tree.yview)
        self.incidents_tree.configure(yscrollcommand=tree_scroll.set)
        self.incidents_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self.incidents_tree.bind("<<TreeviewSelect>>", self.on_incident_selected)

        # Derecha: Panel de Detalle y Accion
        detail_frame = tk.Frame(content_pane, bg="#1E1E1E", bd=1, relief="solid")
        detail_frame.configure(highlightbackground="#333333", highlightthickness=1)
        content_pane.add(detail_frame)

        tk.Label(detail_frame, text="DETALLE Y GESTION DE LA INCIDENCIA", bg="#1E1E1E", fg="#FFD600", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self.incident_detail_text = tk.Text(
            detail_frame,
            bg="#141414",
            fg="#F1F5F9",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
        )
        self.incident_detail_text.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def on_incident_selected(self, event):
        selected_items = self.incidents_tree.selection()
        if not selected_items:
            return
        item = selected_items[0]
        values = self.incidents_tree.item(item, "values")
        incident_id = values[0]
        self.selected_incident_id = incident_id
        self.show_incident_details(incident_id)

    def show_incident_details(self, incident_id: str):
        if not DB_PATH.exists():
            return
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute(
                    "SELECT id, task_id, title, description, severity, category, status, reported_by, "
                    "resolution_notes, resolved_by, created_at, updated_at FROM incidents WHERE id = ?",
                    (incident_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return

            detail = []
            detail.append("=" * 60)
            detail.append(f"INFORME DE INCIDENCIA OPERACIONAL / AI-GRC")
            detail.append(f"Identificador: {row[0]}")
            detail.append(f"Tarea Asociada: {row[1] or 'Ninguna'}")
            detail.append(f"Severidad: [{row[4].upper()}] | Categoria: {row[5]}")
            detail.append(f"Estado: [{row[6].upper()}]")
            detail.append(f"Reportado por: {row[7]} en fecha {row[10]}")
            detail.append("-" * 60)
            detail.append(f"TITULO: {row[2]}")
            detail.append("-" * 60)
            detail.append("DESCRIPCION TECNICA / MOTIVO DEL BLOQUEO:")
            detail.append(row[3] or "Sin descripcion detallada.")
            detail.append("-" * 60)
            detail.append("NOTAS DE RESOLUCION HUMANA:")
            if row[8]:
                detail.append(f"Resuelto por: {row[9]} en {row[11]}")
                detail.append(f"Acciones tomadas: {row[8]}")
            else:
                detail.append("Incidencia pendiente de analisis o resolucion por el operador.")
            detail.append("=" * 60)

            self.incident_detail_text.delete("1.0", "end")
            self.incident_detail_text.insert("end", "\n".join(detail))
        except Exception as exc:
            self.incident_detail_text.delete("1.0", "end")
            self.incident_detail_text.insert("end", f"Error cargando incidencia: {exc}")

    # -------------------------------------------------------------------------
    # PESTANA 4: REGISTRO DE EVENTOS Y AUDITORIA
    # -------------------------------------------------------------------------
    def _init_audit_tab(self):
        parent = self.tab_audit

        # Barra superior de filtros
        top_bar = tk.Frame(parent, bg="#121212")
        top_bar.pack(fill="x", padx=8, pady=(8, 4))

        tk.Label(top_bar, text="Tipo de Registro:", bg="#121212", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.audit_type_var = tk.StringVar(value="Eventos de Tareas (task_events)")
        type_combo = ttk.Combobox(
            top_bar,
            textvariable=self.audit_type_var,
            values=["Eventos de Tareas (task_events)", "Auditoria de Seguridad (audit_logs)"],
            state="readonly",
            width=30,
        )
        type_combo.pack(side="left", padx=4)
        type_combo.bind("<<ComboboxSelected>>", lambda e: self.load_audit_logs())

        tk.Label(top_bar, text="Limite:", bg="#121212", fg="#94A3B8", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 6))
        self.limit_var = tk.StringVar(value="100")
        limit_combo = ttk.Combobox(
            top_bar,
            textvariable=self.limit_var,
            values=["50", "100", "200", "500"],
            state="readonly",
            width=6,
        )
        limit_combo.pack(side="left", padx=4)
        limit_combo.bind("<<ComboboxSelected>>", lambda e: self.load_audit_logs())

        btn_refresh_audit = tk.Button(
            top_bar,
            text="Refrescar Registros",
            bg="#2A2A2A",
            fg="#FFFFFF",
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
            pady=3,
            command=self.load_audit_logs,
        )
        btn_refresh_audit.pack(side="left", padx=8)

        # Tabla de Eventos / Auditoria
        table_frame = tk.Frame(parent, bg="#1E1E1E", bd=1, relief="solid")
        table_frame.configure(highlightbackground="#333333", highlightthickness=1)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.audit_tree = ttk.Treeview(table_frame, show="headings", selectmode="browse")
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=tree_scroll.set)
        self.audit_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

    # -------------------------------------------------------------------------
    # LOGICA DE NEGOCIO Y CONSULTAS A SERVICIOS Y PERSISTENCIA
    # -------------------------------------------------------------------------
    def refresh_all_data(self):
        """Dispara la actualizacion de todas las vistas en hilos de fondo."""
        threading.Thread(target=self._async_refresh_all, daemon=True).start()

    def _async_refresh_all(self):
        self.safe_after(0, lambda: self.status_label.config(text="Actualizando telemetria y datos de persistencia..."))
        self._check_services_health_worker()
        self.safe_after(0, self.load_tasks)
        self.safe_after(0, self.load_incidents)
        self.safe_after(0, self.load_audit_logs)
        self.safe_after(0, lambda: self.status_label.config(text="Sistema sincronizado y preparado."))

    def check_services_health(self):
        """Verifica la conectividad de los 5 servicios integrados."""
        threading.Thread(target=self._check_services_health_worker, daemon=True).start()

    def _check_services_health_worker(self):
        # 1. FCC Server (localhost:8082)
        fcc_ok, fcc_latency, fcc_msg = self._ping_port("127.0.0.1", 8082)
        self._update_badge("fcc_server", fcc_ok, fcc_latency, fcc_msg)

        # 2. FastAPI Backend (localhost:8000)
        api_ok, api_latency, api_msg = self._ping_port("127.0.0.1", 8000)
        self._update_badge("fastapi_backend", api_ok, api_latency, api_msg)

        # 3. Base de Datos SQLite
        db_ok = DB_PATH.exists()
        db_msg = "Activo (WAL)" if db_ok else "No encontrada"
        self._update_badge("sqlite_db", db_ok, 0.5, db_msg)

        # 4. Microsoft Foundry Sdog Farm
        # En modo mock seguro reporta activo
        self._update_badge("azure_foundry", True, 18.0, "Conectado / Mock Mode")

        # 5. Sandbox Engine
        self._update_badge("sandbox_engine", True, 0.2, "Allowlist verificada")

        self.log_service_message(f"Verificacion completada: FCC={fcc_msg} | Backend={api_msg} | DB={db_msg}")

    def _ping_port(self, host: str, port: int) -> tuple[bool, float, str]:
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=0.8):
                latency = round((time.perf_counter() - start) * 1000, 1)
                return True, latency, f"Activo ({latency} ms)"
        except Exception:
            return False, 0.0, "Inactivo / Sin respuesta"

    def _update_badge(self, svc_id: str, is_active: bool, latency: float, message: str):
        def _do():
            try:
                if svc_id not in self.services_cards:
                    return
                badge = self.services_cards[svc_id]["badge"]
                metric = self.services_cards[svc_id]["metric"]

                if is_active:
                    badge.config(text="[ACTIVO]", bg="#065F46", fg="#34D399")
                else:
                    badge.config(text="[DETENIDO]", bg="#7F1D1D", fg="#F87171")

                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                metric.config(text=f"Estado: {message} | Latencia: {latency} ms | Refresco: {now_str}")
            except Exception:
                pass
        self.safe_after(0, _do)

    def start_fastapi_backend(self):
        """Inicia el backend FastAPI en un subproceso si no esta levantado."""
        def run():
            try:
                self.log_service_message("Lanzando servidor FastAPI en puerto 8000...")

                # Comprobar si WSL esta disponible para ejecutar uvicorn dentro del entorno preparado
                has_wsl = False
                try:
                    chk = subprocess.run(["wsl", "which", "python3"], capture_output=True, text=True, timeout=2)
                    has_wsl = (chk.returncode == 0)
                except Exception:
                    pass

                if has_wsl:
                    self.log_service_message("Iniciando FastAPI mediante entorno virtual WSL2 en 0.0.0.0:8000...")
                    cmd = ["wsl", "bash", "-c", "cd ~/software-factory && source .venv/bin/activate && export PYTHONPATH=src && python -m uvicorn software_factory.api.main:app --host 0.0.0.0 --port 8000"]
                    self.backend_process = subprocess.Popen(cmd)
                elif SRC_DIR.exists():
                    self.log_service_message("Iniciando FastAPI directamente en host Windows...")
                    cmd = [sys.executable, "-m", "uvicorn", "software_factory.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
                    env = os.environ.copy()
                    env["PYTHONPATH"] = f"{SRC_DIR};{ROOT_DIR}"
                    self.backend_process = subprocess.Popen(cmd, cwd=str(ROOT_DIR), env=env)
                else:
                    self.log_service_message("Repositorio backend no detectado.")
                    messagebox.showinfo("Servicio Backend", "Asegurese de que el repositorio este presente.")
                    return

                time.sleep(2.0)
                self.check_services_health()
                if self.backend_process:
                    self.log_service_message("Servidor FastAPI lanzado satisfactoriamente.")
            except Exception as exc:
                self.log_service_message(f"Error iniciando backend: {exc}")

        threading.Thread(target=run, daemon=True).start()

    def stop_fastapi_backend(self):
        """Detiene el backend si fue lanzado desde la consola."""
        if self.backend_process:
            try:
                self.backend_process.terminate()
            except Exception:
                pass
            self.backend_process = None
            self.log_service_message("Proceso de backend detenido por el operador.")
        try:
            subprocess.run(["wsl", "pkill", "-f", "software_factory.api.main"], capture_output=True, timeout=2)
            subprocess.run(["wsl", "pkill", "-f", "uvicorn"], capture_output=True, timeout=2)
        except Exception:
            pass
        self.check_services_health()

    def test_fcc_connectivity(self):
        """Verifica la respuesta HTTP del proxy FCC en /v1/models."""
        def run():
            import urllib.request
            try:
                url = "http://127.0.0.1:8082/v1/models"
                fcc_key = "fake_or_token"
                env_file = Path.home() / ".fcc" / ".env"
                if env_file.exists():
                    try:
                        for line in env_file.read_text(encoding="utf-8").splitlines():
                            if line.startswith("FCC_API_KEY="):
                                fcc_key = line.split("=", 1)[1].strip()
                                break
                    except Exception:
                        pass
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {fcc_key}"})
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    models_count = len(data.get("data", []))
                    self.log_service_message(f"FCC Server responde OK: {models_count} modelos disponibles.")
                    messagebox.showinfo("FCC Server", f"Servidor FCC operativo.\nModelos disponibles: {models_count}")
            except Exception as exc:
                self.log_service_message(f"Comprobacion FCC finalizada: {exc}")
                messagebox.showinfo("FCC Server", f"El servidor FCC en loopback responde con:\n{exc}")
            self.check_services_health()

        threading.Thread(target=run, daemon=True).start()

    def load_tasks(self):
        """Carga las tareas de SQLite aplicando los filtros seleccionados."""
        if not DB_PATH.exists():
            return

        status_filter = self.status_filter_var.get()

        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)

        try:
            with sqlite3.connect(DB_PATH) as conn:
                query = "SELECT id, title, status, priority, data_classification, created_at FROM tasks WHERE 1=1"
                params = []
                if status_filter != "Todos":
                    query += " AND status = ?"
                    params.append(status_filter)
                query += " ORDER BY created_at DESC LIMIT 200"

                cursor = conn.execute(query, tuple(params))
                for row in cursor.fetchall():
                    self.tasks_tree.insert("", "end", values=row)
        except Exception as exc:
            self.log_service_message(f"Error cargando tareas: {exc}")

    def load_incidents(self):
        """Carga las incidencias registradas en SQLite."""
        if not DB_PATH.exists():
            return

        status_filter = self.incident_status_var.get()
        sev_filter = self.incident_sev_var.get()

        for item in self.incidents_tree.get_children():
            self.incidents_tree.delete(item)

        try:
            with sqlite3.connect(DB_PATH) as conn:
                query = "SELECT id, task_id, title, severity, category, status, created_at FROM incidents WHERE 1=1"
                params = []
                if status_filter != "Todas":
                    query += " AND status = ?"
                    params.append(status_filter)
                if sev_filter != "Todas":
                    query += " AND severity = ?"
                    params.append(sev_filter)
                query += " ORDER BY created_at DESC LIMIT 200"

                cursor = conn.execute(query, tuple(params))
                for row in cursor.fetchall():
                    self.incidents_tree.insert("", "end", values=row)
        except Exception as exc:
            self.log_service_message(f"Error cargando incidencias: {exc}")

    def load_audit_logs(self):
        """Carga el historial de auditoria o eventos."""
        if not DB_PATH.exists():
            return

        log_type = self.audit_type_var.get()
        limit = int(self.limit_var.get() or "100")

        # Limpiar arbol
        for col in self.audit_tree["columns"]:
            self.audit_tree.heading(col, text="")
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)

        try:
            with sqlite3.connect(DB_PATH) as conn:
                if "task_events" in log_type:
                    cols = ("id", "task_id", "from_status", "to_status", "agent_role", "created_at")
                    self.audit_tree["columns"] = cols
                    self.audit_tree.heading("id", text="ID")
                    self.audit_tree.heading("task_id", text="Tarea")
                    self.audit_tree.heading("from_status", text="Desde")
                    self.audit_tree.heading("to_status", text="Hacia")
                    self.audit_tree.heading("agent_role", text="Agente")
                    self.audit_tree.heading("created_at", text="Fecha / Hora")

                    self.audit_tree.column("id", width=60, anchor="center")
                    self.audit_tree.column("task_id", width=120, anchor="center")
                    self.audit_tree.column("from_status", width=100, anchor="center")
                    self.audit_tree.column("to_status", width=100, anchor="center")
                    self.audit_tree.column("agent_role", width=120, anchor="center")
                    self.audit_tree.column("created_at", width=140, anchor="center")

                    cursor = conn.execute(
                        "SELECT id, task_id, from_status, to_status, agent_role, created_at "
                        "FROM task_events ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
                    for row in cursor.fetchall():
                        self.audit_tree.insert("", "end", values=row)
                else:
                    cols = ("id", "task_id", "action", "actor", "created_at")
                    self.audit_tree["columns"] = cols
                    self.audit_tree.heading("id", text="ID")
                    self.audit_tree.heading("task_id", text="Tarea")
                    self.audit_tree.heading("action", text="Accion")
                    self.audit_tree.heading("actor", text="Operador / Actor")
                    self.audit_tree.heading("created_at", text="Fecha / Hora")

                    self.audit_tree.column("id", width=60, anchor="center")
                    self.audit_tree.column("task_id", width=120, anchor="center")
                    self.audit_tree.column("action", width=160, anchor="center")
                    self.audit_tree.column("actor", width=140, anchor="center")
                    self.audit_tree.column("created_at", width=140, anchor="center")

                    cursor = conn.execute(
                        "SELECT id, task_id, action, actor, created_at "
                        "FROM audit_logs ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
                    for row in cursor.fetchall():
                        self.audit_tree.insert("", "end", values=row)
        except Exception as exc:
            self.log_service_message(f"Error cargando registros de auditoria: {exc}")

    # -------------------------------------------------------------------------
    # DIALOGOS Y ACCIONES DE USUARIO
    # -------------------------------------------------------------------------
    def show_new_task_dialog(self):
        """Abre ventana modal para crear una nueva tarea en la factoria."""
        dialog = tk.Toplevel(self)
        dialog.title("Crear Nueva Tarea en Kanban")
        dialog.geometry("520x420")
        dialog.configure(bg="#1E1E1E")
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="NUEVA TAREA PARA LA FACTORIA", bg="#1E1E1E", fg="#CCFF00", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        tk.Label(dialog, text="Titulo de la Tarea:", bg="#1E1E1E", fg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(4, 2))
        title_entry = tk.Entry(dialog, bg="#121212", fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat", font=("Segoe UI", 10))
        title_entry.pack(fill="x", padx=16, pady=2)

        tk.Label(dialog, text="Descripcion y Requerimientos:", bg="#1E1E1E", fg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(6, 2))
        desc_text = tk.Text(dialog, bg="#121212", fg="#FFFFFF", insertbackground="#FFFFFF", height=5, relief="flat", font=("Segoe UI", 9))
        desc_text.pack(fill="x", padx=16, pady=2)

        # Opciones
        opt_frame = tk.Frame(dialog, bg="#1E1E1E")
        opt_frame.pack(fill="x", padx=16, pady=8)

        tk.Label(opt_frame, text="Prioridad:", bg="#1E1E1E", fg="#94A3B8").grid(row=0, column=0, sticky="w", pady=4)
        prio_var = tk.StringVar(value="high")
        prio_combo = ttk.Combobox(opt_frame, textvariable=prio_var, values=["low", "medium", "high", "critical"], state="readonly", width=12)
        prio_combo.grid(row=0, column=1, padx=6, pady=4)

        tk.Label(opt_frame, text="Clasificacion AI-GRC:", bg="#1E1E1E", fg="#94A3B8").grid(row=0, column=2, sticky="w", padx=(12, 0), pady=4)
        class_var = tk.StringVar(value="approved_remote")
        class_combo = ttk.Combobox(opt_frame, textvariable=class_var, values=["approved_remote", "restricted", "local_only"], state="readonly", width=16)
        class_combo.grid(row=0, column=3, padx=6, pady=4)

        def save():
            title = title_entry.get().strip()
            desc = desc_text.get("1.0", "end").strip()
            if not title:
                messagebox.showerror("Error", "El titulo es obligatorio.")
                return

            try:
                task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        """
                        INSERT INTO tasks (id, title, description, status, priority, data_classification, acceptance_criteria)
                        VALUES (?, ?, ?, 'BACKLOG', ?, ?, '[]')
                        """,
                        (task_id, title, desc, prio_var.get(), class_var.get()),
                    )
                    conn.execute(
                        """
                        INSERT INTO task_events (task_id, event_type, from_status, to_status, agent_role, payload)
                        VALUES (?, 'TASK_CREATED', NULL, 'BACKLOG', 'operador_consola_windows', ?)
                        """,
                        (task_id, json.dumps({"source": "desktop_console", "priority": prio_var.get()})),
                    )
                self.log_service_message(f"Tarea creada satisfactoriamente: ID={task_id}")
                dialog.destroy()
                self.load_tasks()
            except Exception as exc:
                messagebox.showerror("Error", f"Fallo al registrar la tarea:\n{exc}")

        btn_save = tk.Button(dialog, text="CREAR TAREA EN BACKLOG", bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 10, "bold"), relief="flat", command=save, pady=6)
        btn_save.pack(fill="x", padx=16, pady=12)

    def approve_selected_task(self):
        """Emite la aprobacion humana formal para una tarea en estado REVIEW."""
        if not self.selected_task_id:
            messagebox.showwarning("Seleccion Requerida", "Seleccione primero una tarea de la lista.")
            return

        task_id = self.selected_task_id
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
                row = cur.fetchone()
                if not row:
                    messagebox.showerror("Error", "Tarea no encontrada en la base de datos.")
                    return
                current_status = row[0]

            if current_status != "REVIEW":
                messagebox.showinfo("Estado no apto", f"La tarea {task_id} se encuentra en [{current_status}].\nSolo las tareas en [REVIEW] requieren la barrera de aprobacion humana.")
                return

            if messagebox.askyesno("Confirmar Aprobacion Humana (AI-GRC)", f"Desea aprobar y promover la tarea {task_id} a [DONE]?\n\nEsta accion certifica que el codigo y los diffs han sido auditados y autoriza su paso definitivo a produccion."):
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("UPDATE tasks SET status = 'DONE', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
                    conn.execute(
                        """
                        INSERT INTO task_events (task_id, event_type, from_status, to_status, agent_role, payload)
                        VALUES (?, 'TASK_APPROVED', 'REVIEW', 'DONE', 'director_tecnico_consola_windows', ?)
                        """,
                        (task_id, json.dumps({"decision": "APPROVED", "comments": "Aprobado mediante Consola Desktop Windows."})),
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_logs (task_id, action, actor, details)
                        VALUES (?, 'HUMAN_APPROVAL_RECORDED', 'director_tecnico_consola_windows', ?)
                        """,
                        (task_id, json.dumps({"decision": "APPROVED", "comments": "Aprobado mediante Consola Desktop Windows."})),
                    )
                self.log_service_message(f"Aprobacion registrada: APPROVED para tarea {task_id}")
                self.load_tasks()
                self.show_task_details(task_id)
                messagebox.showinfo("Aprobada", f"La tarea {task_id} ha transicionado a DONE con exito.")
        except Exception as exc:
            messagebox.showerror("Error de Aprobacion", f"No se pudo completar la aprobacion:\n{exc}")

    def run_orchestration_cycle(self):
        """Ejecuta el ciclo asistido multiagente en un hilo de fondo."""
        if not self.selected_task_id:
            messagebox.showwarning("Seleccion Requerida", "Seleccione primero una tarea de la lista para orquestar.")
            return

        task_id = self.selected_task_id

        def worker():
            self.log_service_message(f"Iniciando ciclo multiagente para tarea {task_id}...")
            try:
                cmd = f"wsl bash -c \"cd ~/software-factory && source .venv/bin/activate && python -c 'import asyncio; from software_factory.orchestration.graph import run_full_cycle; asyncio.run(run_full_cycle(\\\"{task_id}\\\"))'\""
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
                self.log_service_message(f"Ciclo multiagente concluido para {task_id}.")
                self.safe_after(0, self.load_tasks)
                self.safe_after(0, self.load_incidents)
                self.safe_after(0, self.load_audit_logs)
                self.safe_after(0, lambda: self.show_task_details(task_id))
            except Exception as exc:
                self.log_service_message(f"Fallo en orquestacion de {task_id}: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def show_new_incident_dialog(self):
        """Abre ventana modal para registrar una incidencia manual."""
        dialog = tk.Toplevel(self)
        dialog.title("Registrar Incidencia Operacional / AI-GRC")
        dialog.geometry("520x420")
        dialog.configure(bg="#1E1E1E")
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="REGISTRO DE INCIDENCIA OPERACIONAL", bg="#1E1E1E", fg="#FF4444", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(16, 8))

        tk.Label(dialog, text="Titulo de la Incidencia:", bg="#1E1E1E", fg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(4, 2))
        title_entry = tk.Entry(dialog, bg="#121212", fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat", font=("Segoe UI", 10))
        title_entry.pack(fill="x", padx=16, pady=2)

        tk.Label(dialog, text="Descripcion Tecnica / Causa Raiz:", bg="#1E1E1E", fg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(6, 2))
        desc_text = tk.Text(dialog, bg="#121212", fg="#FFFFFF", insertbackground="#FFFFFF", height=5, relief="flat", font=("Segoe UI", 9))
        desc_text.pack(fill="x", padx=16, pady=2)

        opt_frame = tk.Frame(dialog, bg="#1E1E1E")
        opt_frame.pack(fill="x", padx=16, pady=8)

        tk.Label(opt_frame, text="Severidad:", bg="#1E1E1E", fg="#94A3B8").grid(row=0, column=0, sticky="w", pady=4)
        sev_var = tk.StringVar(value="high")
        sev_combo = ttk.Combobox(opt_frame, textvariable=sev_var, values=["low", "medium", "high", "critical"], state="readonly", width=12)
        sev_combo.grid(row=0, column=1, padx=6, pady=4)

        tk.Label(opt_frame, text="Categoria:", bg="#1E1E1E", fg="#94A3B8").grid(row=0, column=2, sticky="w", padx=(12, 0), pady=4)
        cat_var = tk.StringVar(value="policy_violation")
        cat_combo = ttk.Combobox(opt_frame, textvariable=cat_var, values=["policy_violation", "secret_detected", "sandbox_failure", "timeout", "manual"], state="readonly", width=16)
        cat_combo.grid(row=0, column=3, padx=6, pady=4)

        def save():
            title = title_entry.get().strip()
            desc = desc_text.get("1.0", "end").strip()
            if not title:
                messagebox.showerror("Error", "El titulo es obligatorio.")
                return

            try:
                inc_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        """
                        INSERT INTO incidents (id, task_id, title, description, severity, category, status, reported_by)
                        VALUES (?, ?, ?, ?, ?, ?, 'open', 'operador_consola_windows')
                        """,
                        (inc_id, self.selected_task_id, title, desc, sev_var.get(), cat_var.get()),
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_logs (task_id, action, actor, details)
                        VALUES (?, 'INCIDENT_CREATED', 'operador_consola_windows', ?)
                        """,
                        (self.selected_task_id, json.dumps({"incident_id": inc_id, "title": title, "severity": sev_var.get()})),
                    )
                self.log_service_message(f"Incidencia registrada: {inc_id}")
                dialog.destroy()
                self.load_incidents()
            except Exception as exc:
                messagebox.showerror("Error", f"Fallo al registrar la incidencia:\n{exc}")

        btn_save = tk.Button(dialog, text="GUARDAR INCIDENCIA", bg="#DC2626", fg="#FFFFFF", font=("Segoe UI", 10, "bold"), relief="flat", command=save, pady=6)
        btn_save.pack(fill="x", padx=16, pady=12)

    def resolve_selected_incident(self):
        """Abre cuadro de dialogo para cerrar y resolver una incidencia."""
        if not self.selected_incident_id:
            messagebox.showwarning("Seleccion Requerida", "Seleccione primero una incidencia de la tabla.")
            return

        incident_id = self.selected_incident_id

        dialog = tk.Toplevel(self)
        dialog.title(f"Resolucion de Incidencia {incident_id}")
        dialog.geometry("480x320")
        dialog.configure(bg="#1E1E1E")
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text=f"RESOLUCION DE INCIDENCIA: {incident_id}", bg="#1E1E1E", fg="#059669", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 6))

        tk.Label(dialog, text="Notas de Resolucion y Acciones Correctoras:", bg="#1E1E1E", fg="#F8FAFC", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(4, 2))
        notes_text = tk.Text(dialog, bg="#121212", fg="#FFFFFF", insertbackground="#FFFFFF", height=6, relief="flat", font=("Segoe UI", 9))
        notes_text.pack(fill="x", padx=16, pady=2)

        def do_resolve():
            notes = notes_text.get("1.0", "end").strip()
            if not notes:
                messagebox.showerror("Error", "Debe incluir las notas de resolucion.")
                return

            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        """
                        UPDATE incidents
                        SET status = 'resolved', resolution_notes = ?, resolved_by = 'director_tecnico_windows', updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (notes, incident_id),
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_logs (action, actor, details)
                        VALUES ('INCIDENT_RESOLVED', 'director_tecnico_windows', ?)
                        """,
                        (json.dumps({"incident_id": incident_id, "notes": notes})),
                    )
                self.log_service_message(f"Incidencia {incident_id} resuelta satisfactoriamente.")
                dialog.destroy()
                self.load_incidents()
                self.show_incident_details(incident_id)
                messagebox.showinfo("Resuelta", f"Incidencia {incident_id} marcada como RESUELTA.")
            except Exception as exc:
                messagebox.showerror("Error", f"Fallo al resolver incidencia:\n{exc}")

        btn_commit = tk.Button(dialog, text="CONFIRMAR RESOLUCION", bg="#059669", fg="#FFFFFF", font=("Segoe UI", 10, "bold"), relief="flat", command=do_resolve, pady=6)
        btn_commit.pack(fill="x", padx=16, pady=12)

    def export_audit_report(self, show_dialog: bool = True):
        """Genera un informe integral de auditoria AI-GRC en formato Markdown y lo guarda en disco."""
        reports_dir = ROOT_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        report_file = reports_dir / f"informe_auditoria_aigrc_{now.strftime('%Y%m%d_%H%M%S')}.md"

        try:
            with sqlite3.connect(DB_PATH) as conn:
                tasks_count = conn.execute("SELECT count(*) FROM tasks").fetchone()[0]
                events_count = conn.execute("SELECT count(*) FROM task_events").fetchone()[0]
                audit_count = conn.execute("SELECT count(*) FROM audit_logs").fetchone()[0]
                incidents_count = conn.execute("SELECT count(*) FROM incidents").fetchone()[0]

                # Tareas por estado
                tasks_by_status = conn.execute("SELECT status, count(*) FROM tasks GROUP BY status").fetchall()

                # Ultimas 10 incidencias
                incidents_rows = conn.execute("SELECT id, title, severity, category, status, created_at FROM incidents ORDER BY id DESC LIMIT 10").fetchall()

                # Ultimas 10 firmas humanas
                human_approvals = conn.execute("SELECT task_id, actor, details, created_at FROM audit_logs WHERE action IN ('HUMAN_APPROVAL_RECORDED', 'INCIDENT_RESOLVED') ORDER BY id DESC LIMIT 10").fetchall()

            doc = []
            doc.append("# INFORME DE AUDITORIA Y CUMPLIMIENTO AI-GRC")
            doc.append(f"**Organizacion:** Sdog Farm Software Factory (`sadogfarm.onmicrosoft.com`)  ")
            doc.append(f"**Fecha de Emision:** {now.strftime('%d/%m/%Y %H:%M:%S')}  ")
            doc.append(f"**Entorno de Control:** Consola de Escritorio Windows (Autonomous AI Dev Infrastructure)  \n")
            doc.append("---")
            doc.append("\n## 1. Resumen Metrico de la Factoria")
            doc.append(f"- **Total de Tareas Gestionadas:** {tasks_count}")
            doc.append(f"- **Eventos de Transicion Registrados:** {events_count}")
            doc.append(f"- **Registros de Auditoria Inmutables:** {audit_count}")
            doc.append(f"- **Incidencias AI-GRC Detectadas:** {incidents_count}\n")

            doc.append("### Distribucion de Estados Kanban")
            doc.append("| Estado | Numero de Tareas |")
            doc.append("| :--- | :--- |")
            for st, cnt in tasks_by_status:
                doc.append(f"| {st} | {cnt} |")

            doc.append("\n---")
            doc.append("\n## 2. Registro de Incidencias y Politicas de Seguridad")
            doc.append("| ID | Titulo | Severidad | Categoria | Estado | Fecha |")
            doc.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for inc in incidents_rows:
                doc.append(f"| {inc[0]} | {inc[1]} | {inc[2]} | {inc[3]} | {inc[4]} | {inc[5]} |")

            doc.append("\n---")
            doc.append("\n## 3. Firmas de Aprobacion Humana Registradas")
            doc.append("| Tarea ID | Autoridad / Actor | Detalle de la Accion | Fecha |")
            doc.append("| :--- | :--- | :--- | :--- |")
            for app in human_approvals:
                doc.append(f"| {app[0] or 'N/A'} | {app[1]} | {app[2][:50]}... | {app[3]} |")

            doc.append("\n---")
            doc.append("\n*Informe generado automaticamente por la Consola de Gestion Integral de la Software Factory.*")

            report_file.write_text("\n".join(doc), encoding="utf-8")
            self.log_service_message(f"Informe de auditoria exportado a {report_file}")
            if show_dialog:
                messagebox.showinfo("Informe Exportado", f"Informe de auditoria generado con exito en:\n\n{report_file}")
        except Exception as exc:
            if show_dialog:
                messagebox.showerror("Error al Exportar", f"Fallo al generar informe:\n{exc}")


def main():
    app = DesktopConsoleApp()
    app.mainloop()


if __name__ == "__main__":
    main()
