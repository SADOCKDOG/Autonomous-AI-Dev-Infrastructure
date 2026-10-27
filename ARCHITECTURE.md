# Documento de Arquitectura y Diseno de Plataforma

## 1. Mision del Sistema
Proveer una infraestructura hibrida local de desarrollo asistido por IA donde el control, la orquestacion, la persistencia y la ejecucion de herramientas residan en el equipo local del operador, manteniendo el consumo de inferencia desacoplado a traves de adaptadores estandarizados.

## 2. Diagrama de Capas del Sistema

```text
                               CAPA DE USUARIO
                      Navegador / Clientes HTTP / IDE
                                     |
                                     | HTTP localhost:8000
                                     v
                       CAPA DE API Y PERSISTENCIA
               +-------------------------------------------+
               | FastAPI Router (/health, /api/v1/tasks)   |
               |                                           |
               | Kanban Service <-> SQLite WAL Database    |
               +---------------------┬---------------------+
                                     |
                                     v
                        CAPA DE ORQUESTACION
               +-------------------------------------------+
               | LangGraph StateGraph Engine               |
               |                                           |
               | [Analyst] -> [Architect] -> [Developer]  |
               |    ^             |               |        |
               |    |             v               v        |
               | [Blocked] <- [Tester]   <-   [Reviewer]   |
               +---------------------┬---------------------+
                                     |
                                     v
                       CAPA DE SEGURIDAD Y EJECUCION
               +-------------------------------------------+
               | Policy Engine (Data Boundaries)           |
               | Secret Scanner (Diff regex analysis)      |
               | Command Executor (Sandbox / Allowlist)    |
               | Git Worktree Manager (Aislamiento fisico) |
               +---------------------┬---------------------+
                                     |
                                     v
                          CAPA DE MODEL GATEWAY
               +-------------------------------------------+
               | Internal Model Gateway                    |
               |   ├── FCC Anthropic Provider (/messages)  |
               |   ├── FCC Responses Provider (/responses) |
               |   ├── Azure Foundry Provider (Direct/Mock)|
               |   └── Foundry Local Provider (Disabled)   |
               +-------------------------------------------+
```

## 3. Modelo de Datos y Persistencia
Se utiliza SQLite configurado en modo Write-Ahead Logging (WAL) y con cumplimiento estricto de claves foraneas (`PRAGMA foreign_keys = ON`).

- **tasks:** Almacena la entidad principal de trabajo, su estado (`TaskStatus`), prioridad, clasificacion de datos, criterios de aceptacion en formato JSON, rama Git asignada y ruta al worktree.
- **task_events:** Registro cronologico inmutable de cada transicion de estado, agente emisor y payload de contexto.
- **audit_logs:** Registro de auditoria de seguridad de alto nivel, incluyendo decisiones de aprobacion humana, cambios de politicas y ejecucion de acciones protegidas. Los datos se encuentran sanitizados para prevenir la persistencia de credenciales.

## 4. Orquestacion con LangGraph
El flujo de ejecucion se define como un grafo dirigido de estados sobre `FactoryState`:
- Cada nodo representa una fase de ingenieria asignada a un agente especializado con acceso acotado al contexto.
- En caso de excepcion no controlada o fallo de asercion en pruebas de QA, el flujo conmuta al nodo `error_node`, transicionando la tarea a `BLOCKED` y deteniendo el procesamiento.
- El ciclo de ejecucion automatica se detiene indefectiblemente en el nodo `reviewer_node` (estado `REVIEW`), requiriendo que la promocion a `DONE` sea efectuada mediante la API de aprobacion humana.

## 5. Estrategia de Aislamiento y Control de Versiones
Para garantizar la reproducibilidad y evitar condiciones de carrera:
- Cada tarjeta activa despliega un directorio Git Worktree en `.worktrees/task-xxx`.
- Los cambios se confirman exclusivamente en la rama de la tarea (`feat/task-xxx`).
- Tras la revision y aprobacion final, el worktree se desmonta y se ejecuta `git worktree prune` para optimizar el almacenamiento.
