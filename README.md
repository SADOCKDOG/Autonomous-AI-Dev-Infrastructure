# Software Factory Híbrida Local

Plataforma de desarrollo y orquestación multiagente híbrida local (Windows 11 + WSL2 Ubuntu) con Model Gateway agnóstico, soporte para proxy local Free Claude Code (FCC) y Azure AI Foundry.

## Arquitectura y Componentes
- **Backend:** Python 3.14 + FastAPI (enlazado exclusivamente a `127.0.0.1:8000`).
- **Persistencia:** SQLite (`data/factory.db`) con soporte para eventos y registro de auditoría.
- **Kanban:** Gestión de tareas interna (`BACKLOG → READY → PLANNING → IN_PROGRESS → TESTING → REVIEW → DONE`).
- **Inferencia:**
  - **FCC Proxy:** `http://127.0.0.1:8082` (proveedor activo para pruebas iniciales).
  - **Azure AI Foundry:** Integración directa por adaptador (configurable cuando haya créditos).
  - **Microsoft Foundry Local:** En evaluación documental (sin descargas de modelos en esta fase).

## Puesta en Marcha (WSL2)

```bash
cd ~/software-factory
source .venv/bin/activate
export PYTHONPATH=src

# Ejecución de pruebas
pytest

# Arrancar backend
python -m software_factory.api.main
```
