# Manual de Operaciones Técnicas (Runbook)
## Software Factory Híbrida Local

Este documento detalla los procedimientos de inicio, operación diaria, backup, parada de emergencia y resolución de incidentes de la fábrica de software.

---

## 1. Puesta en Marcha

### Prerrequisitos
1. **Free Claude Code (FCC):** Mantener el servidor `fcc-server.exe` levantado en Windows (`127.0.0.1:8082`).
2. **Entorno WSL2:** Abrir una terminal en Ubuntu/WSL2.

### Inicio del Backend FastAPI
```bash
cd ~/software-factory
source .venv/bin/activate
export PYTHONPATH=src

# Iniciar servidor en loopback (puerto 8000)
python -m software_factory.api.main
```

### Comprobación de Salud
En una terminal o navegador:
```bash
curl -s http://127.0.0.1:8000/health | jq .
```
Debe retornar:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "development",
  "database": "ok",
  "providers": {
    "fcc_responses": { "status": "healthy" },
    "fcc_anthropic": { "status": "healthy" },
    "azure_foundry": { "status": "healthy" },
    "foundry_local": { "status": "disabled" }
  }
}
```

---

## 2. Flujo Operativo por Tarjeta Kanban

### Crear Tarea
```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Optimizar consultas SQL en persistencia",
    "description": "Indexar por estado y crear consultas paginadas",
    "priority": "medium",
    "data_classification": "approved_remote"
  }'
```

### Ejecutar Ciclo Multiagente Asistido
```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{TASK_ID}/run_full_cycle
```
Los agentes ejecutarán en secuencia:
1. **Analista:** Descompone y genera criterios de aceptación (`BACKLOG → READY`).
2. **Arquitecto:** Formula el plan técnico (`READY → PLANNING`).
3. **Desarrollador:** Crea el worktree aislado (`.worktrees/{task_id}`) e implementa los cambios (`PLANNING → IN_PROGRESS`).
4. **QA / Tester:** Lanza los tests mediante el sandbox con allowlist (`IN_PROGRESS → TESTING`).
5. **Revisor:** Escanea secretos en el diff y evalúa calidad (`TESTING → REVIEW`).

### Barrera de Aprobación Humana
Una vez en estado `REVIEW`, la tarea se detiene esperando autorización explícita:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/{TASK_ID}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approver": "yo",
    "decision": "APPROVED",
    "comments": "Diff revisado, pruebas superadas y sin secretos."
  }'
```

---

## 3. Respaldo y Restauración de Base de Datos

### Copia de Seguridad en Caliente (SQLite WAL)
```bash
cd ~/software-factory
mkdir -p backups
sqlite3 data/factory.db ".backup backups/factory_$(date +%Y%m%d_%H%M%S).db"
```

### Restauración
```bash
# 1. Detener el backend
pkill -f "software_factory.api.main"

# 2. Restaurar archivo de backup
cp backups/factory_YYYYMMDD_HHMMSS.db data/factory.db

# 3. Reiniciar backend
python -m software_factory.api.main
```

---

## 4. Gestión de Git Worktrees y Espacio en Disco

### Listar Worktrees Activos
```bash
cd ~/software-factory
git worktree list
```

### Limpieza de Worktrees Huérfanos
```bash
git worktree prune
```

---

## 5. Activación Futura de Azure AI Foundry

Cuando dispongas de créditos en Azure:
1. Editar `.env` en `~/software-factory/.env`:
   ```dotenv
   AZURE_AI_ENDPOINT=https://tu-proyecto.openai.azure.com/
   AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
   AZURE_CLIENT_SECRET=tu-clave-o-token-entra-id
   ```
2. Modificar `config/models.example.yaml` activando `azure_foundry: enabled: true`.
3. Reiniciar el backend; el adaptador `AzureFoundryProvider` pasará de modo mock a inferencia directa.

---

## 6. Parada de Emergencia

Para detener inmediatamente todos los procesos locales de la fábrica:
```bash
pkill -9 -f "software_factory"
```
En caso de requerir desmontar cualquier worktree bloqueado:
```bash
git worktree remove --force .worktrees/task-xxx
git worktree prune
```
