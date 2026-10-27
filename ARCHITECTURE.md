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

## 6. Taxonomia y Coordinacion Multiagente (Equipo de 9 Agentes)
El sistema soporta una organizacion profesional completa dividida en 4 capas funcionales:
1. **Capa de Direccion y Gobierno:** `agent_pm` (Project Manager) y `agent_compliance` (Oficial de Cumplimiento Normativo / Auditor Legal).
2. **Capa de Arquitectura y Diseno:** `agent_architect` (Arquitecto de Plataforma y Director UI/UX Bento Grid).
3. **Capa de Desarrollo Especializado:** `agent_dev_frontend` (Full-Stack / PWA), `agent_dev_android` (Capacitor 7), `agent_dev_windows` (Tauri v2 / Rust) y `agent_dev_backend` (Cloudflare Workers).
4. **Capa de Calidad, Seguridad y Soporte:** `agent_qa_devops` (QA Automation y Sandbox), `agent_security` (Auditor de Secretos y Privacidad) y `agent_docs_support` (Documentador Tecnico y Soporte).

Para la especificacion completa de responsabilidades y flujo de transiciones, consultar [docs/ORQUESTACION_Y_SUPERVISION_MULTIAGENTE.md](docs/ORQUESTACION_Y_SUPERVISION_MULTIAGENTE.md).

## 7. Pasarela Cloud Gobernada (Microsoft Foundry en Sdog Farm)
La infraestructura soporta inferencia empresarial auditada mediante Microsoft Azure AI Foundry bajo el tenant `sadogfarm.onmicrosoft.com`:
- Autenticacion OAuth 2.0 con Microsoft Entra ID (Service Principal y gestion de tokens JWT).
- Soberania territorial bajo el marco del EU Data Boundary (regiones `spaincentral` y `westeurope`).
- Mapeo de despliegues: `sdogfarm-gpt4o` (arquitectura y revision), `sdogfarm-phi4` (analisis y desarrollo) y `sdogfarm-gpt4o-mini` (pruebas y documentacion).
- Configuracion declarativa: [config/azure_foundry_sdogfarm.yaml](config/azure_foundry_sdogfarm.yaml) y guia tecnica en [docs/INTEGRACION_MICROSOFT_FOUNDRY_SDOGFARM.md](docs/INTEGRACION_MICROSOFT_FOUNDRY_SDOGFARM.md).

## 8. Consola de Gestion Integral de Escritorio (Windows Desktop)
La supervision operativa y el gobierno AI-GRC disponen de una aplicacion grafica nativa para Windows 11 mantenida en el repositorio dedicado:
- **Repositorio GitHub:** [Console-AI-Dev-Infrastructure](https://github.com/SADOCKDOG/Console-AI-Dev-Infrastructure)
- **Repositorio Local:** `C:\Users\yo\repo\AutonomousDevConsole`
- **Capacidades:** Telemetria en tiempo real de servicios (:8082, :8000, SQLite WAL, Foundry), tablero Kanban con aprobacion humana obligatoria, gestor de incidencias normativas y exportador forense de auditoria en Markdown.
- **Documentacion y Manual:** [docs/CONSOLA_GESTION_INTEGRAL_WINDOWS.md](docs/CONSOLA_GESTION_INTEGRAL_WINDOWS.md).
