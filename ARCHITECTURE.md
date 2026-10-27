# Documento de Arquitectura Técnica

## Principio de Diseño
La orquestación y el control residen 100% en el entorno local (WSL2 Ubuntu). El orquestador es agnóstico al proveedor de inferencia a través de la abstracción del **Model Gateway**.

## Diagrama de Capas
```text
                         WSL2 (Ubuntu)
┌──────────────────────────────────────────────────────────────┐
│ FastAPI API (/health, /api/v1/tasks)                         │
│                                                              │
│  Kanban Service ── SQLite (tasks, events, audit_logs)        │
│                                                              │
│  Orchestration (LangGraph / State Machine)                   │
│         │                                                    │
│  Policy & Security Engine (Allowlist, Data Classification)   │
│         │                                                    │
│  Internal Model Gateway                                      │
│    ├── FCC Adapter (Proxy 127.0.0.1:8082 - Activo en pruebas)│
│    ├── Azure Foundry Adapter (Directo - En espera créditos)  │
│    └── Foundry Local Adapter (Local - Deshabilitado en Hito 1│
│                                                              │
│  Git Worktree Isolation Engine (feat/task-xxx)               │
└──────────────────────────────────────────────────────────────┘
```
