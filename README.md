# Autonomous AI Dev Infrastructure: Software Factory Hibrida Local

## Resumen Ejecutivo y Arquitectura

Infraestructura de ingenieria de software autonoma y coordinacion multiagente hibrida local (Windows 11 + WSL2 Ubuntu). Proporciona un entorno determinista y desacoplado para la descomposicion, planificacion, ejecucion, prueba y auditoria de requerimientos de software a traves de agentes de inteligencia artificial y un tablero Kanban.

El nucleo de control, logica de negocio, persistencia y ejecucion residen exclusivamente en la infraestructura local del operador. La inferencia es provista de forma agnostica mediante un Model Gateway interno con soporte para proxy local Free Claude Code (FCC), Azure AI Foundry y preparacion para runtimes locales aislados.

---

## 1. Principios Rectores y Diseno Tecnico

1. **Soberania y Control Local:** El orquestador, la base de datos de estado, los registros de auditoria y los entornos de compilacion se ejecutan en local. Ningun proveedor externo gobierna el flujo de trabajo.
2. **Abstraccion del Proveedor de Inferencia:** El orquestador no depende de APIs propietarias especificas. El Model Gateway tipado normaliza las interfaces hacia protocolos estandar (OpenAI Responses y Anthropic Messages).
3. **Fronteras y Clasificacion de Datos:**
   - `local_only`: Prohibe de forma determinista cualquier transmision de contexto hacia proveedores o redes externas.
   - `approved_remote`: Permite el consumo de endpoints remotos autorizados explicitamente.
   - `restricted`: Requiere intervencion y autorizacion humana expresa previa al despacho de la peticion.
4. **Aislamiento Físico por Tarea:** Cada unidad de trabajo se compila y ejecuta en una rama dedicada y un directorio Git Worktree aislado (`.worktrees/task-xxx`).
5. **Sandbox de Ejecucion con Lista de Permisos:** Se prohíben llamadas arbitrarias de shell. Solo se autorizan binarios y subcomandos validados por token (`git`, `pytest`, `python3`, `ruff`), con tiempos limite estrictos y cuotas de salida.
6. **Barrera Obligatoria de Aprobacion Humana:** Ningun agente autonomo dispone de privilegios para efectuar operaciones destructivas, `git merge`, `git push` o transicionar tareas al estado final `DONE` sin aprobacion humana auditada.

---

## 2. Topologia de Componentes

```text
                         HOST WINDOWS 11
+-----------------------------------------------------------------+
| Free Claude Code (FCC Server) en loopback: 127.0.0.1:8082       |
| Runtime de Inferencia Local (4405 modelos / tier sin coste)     |
+--------------------------------┬--------------------------------+
                                 | Resolucion automatica de red
                         WSL2 (UBUNTU EXT4)
+--------------------------------▼--------------------------------+
| Backend FastAPI (127.0.0.1:8000)                                |
|                                                                 |
|   Kanban Service <---> SQLite WAL (tasks, events, audit_logs)   |
|                                                                 |
|   Orquestador Multiagente (LangGraph StateGraph)                |
|     - Analista    (Interpretacion y Criterios de Aceptacion)    |
|     - Arquitecto  (Plan Tecnico y Archivos Afectados)           |
|     - Desarrollador (Implementacion en Worktree)                |
|     - QA Tester   (Ejecucion de Pruebas en Sandbox)             |
|     - Revisor     (Escaneo de Secretos y Auditoria de Diff)     |
|                                                                 |
|   Motor de Seguridad y Politicas                                |
|     - SecretScanner (Analisis de patrones de credenciales)      |
|     - CommandExecutor (Validacion de allowlist y timeout)       |
|     - ApprovalManager (Barrera de aprobacion humana)            |
|                                                                 |
|   Model Gateway Interno                                         |
|     - FCCAnthropicProvider (Proxy localhost /v1/messages)       |
|     - FCCResponsesProvider (Proxy localhost /v1/responses)      |
|     - AzureFoundryProvider (Modo directo / Mock seguro)         |
|     - FoundryLocalProvider (Deshabilitado / 0 descargas)        |
|                                                                 |
|   Motor de Git Worktrees (.worktrees/task-xxx)                  |
+-----------------------------------------------------------------+
```

---

## 3. Estructura del Repositorio

```text
Autonomous-AI-Dev-Infrastructure/
├── .github/
│   └── workflows/
│       └── ci.yml
├── README.md
├── ARCHITECTURE.md
├── SECURITY.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── config/
│   ├── models.example.yaml
│   ├── agents.yaml
│   ├── policies.yaml
│   └── azure_foundry_sdogfarm.yaml
├── docs/
│   ├── runbook.md
│   ├── especificacion_arquitectura_v1_1.md
│   ├── reporte_ejecucion_hitos.md
│   ├── INTEGRACION_MICROSOFT_FOUNDRY_SDOGFARM.md
│   └── piloto_livestock_manager/
│       ├── AI_GOVERNANCE_RISK_COMPLIANCE.md
│       ├── PILOT_BLUEPRINT_LIVESTOCK_MANAGER.md
│       ├── CONFIG_LIVESTOCK_MANAGER.yaml
│       ├── DATA_CONTRACT_LIVESTOCK.json
│       └── REPORTE_SIMULACION_Y_EVIDENCIAS.md
├── src/software_factory/
│   ├── __init__.py
│   ├── settings.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── health.py
│   │   └── kanban.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── kanban/
│   │   ├── __init__.py
│   │   ├── schema.py
│   │   └── service.py
│   ├── model_gateway/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── policy.py
│   │   ├── registry.py
│   │   ├── fcc_provider.py
│   │   ├── azure_foundry.py
│   │   └── foundry_local.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── analyst.py
│   │   ├── architect.py
│   │   ├── developer.py
│   │   ├── tester.py
│   │   └── reviewer.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── graph.py
│   │   └── approval.py
│   ├── execution/
│   │   ├── __init__.py
│   │   └── sandbox.py
│   ├── security/
│   │   ├── __init__.py
│   │   └── secret_scanner.py
│   └── git/
│       ├── __init__.py
│       └── worktree.py
├── scripts/
│   ├── verify_live_fcc.py
│   ├── verify_live_orchestration.py
│   └── simulate_livestock_pilot.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_health.py
    │   ├── test_settings.py
    │   ├── test_kanban_persistence.py
    │   ├── test_model_gateway.py
    │   ├── test_execution_and_git.py
    │   ├── test_orchestration.py
    │   └── test_multi_agent_flow.py
    └── integration/
        └── test_acceptance.py
```

---

## 4. Ciclo de Vida de una Tarea (Kanban)

El flujo operativo se rige por transiciones formales:

$$\text{BACKLOG} \longrightarrow \text{READY} \longrightarrow \text{PLANNING} \longrightarrow \text{IN\_PROGRESS} \longrightarrow \text{TESTING} \longrightarrow \text{REVIEW} \longrightarrow \text{DONE}$$

1. **BACKLOG:** Registro inicial del requerimiento mediante API REST o tablero.
2. **READY:** El Agente Analista descompone la solicitud y define criterios de aceptacion evaluables. La transicion exige al menos un criterio no vacio.
3. **PLANNING:** El Agente Arquitecto formula el plan tecnico de modificacion, archivos impactados y riesgos.
4. **IN_PROGRESS:** El Agente Desarrollador inicializa el worktree aislado (`feat/task-xxx`) e implementa los cambios.
5. **TESTING:** El Agente Tester ejecuta la suite de pruebas bajo el sandbox seguro, capturando stdout/stderr y codigos de retorno.
6. **REVIEW:** El Agente Revisor escanea el diff en busca de credenciales/secretos y valida el cumplimiento tecnico. La ejecucion automatica se detiene en este estado.
7. **DONE:** Promocion exclusiva mediante decision explícita de un aprobador humano (`ApprovalManager`).

---

## 5. Bateria de Verificacion Automatizada

El repositorio cuenta con 39 pruebas automatizadas estructuradas:
- **Unitarias (31 tests):** Validacion de esquemas, persistencia SQLite, resolucion de proveedores, aislamiento Git, allowlist de sandbox (incluyendo soporte Node/Playwright/Cargo para Livestock Manager), escaneo de secretos, autenticacion Microsoft Foundry (Entra ID sadogfarm.onmicrosoft.com) y logica de agentes.
- **Integracion y Aceptacion (8 tests):** Modo degradado ante caidas de proveedores, aislamiento estricto `local_only`, recuperacion tras reinicio, auditoria libre de secretos, flujo end-to-end con aprobacion humana y verificacion de politicas de gobernanza AI-GRC para el piloto Livestock Manager.

Ejecucion de pruebas:
```bash
cd ~/software-factory
source .venv/bin/activate
export PYTHONPATH=src
pytest -v
```

---

## 6. Manual Operativo

Para instrucciones de instalacion, inicio de servicios, politicas de respaldo en caliente, parada de emergencia y configuracion de proveedores remotos, consultar [docs/runbook.md](docs/runbook.md).

---

## 7. Piloto Tecnico y Gobernanza AI-GRC (Livestock Manager)

La infraestructura ha sido validada mediante un piloto integral end-to-end basado en el proyecto agropecuario **Livestock Manager** (PWA offline-first con Capacitor en Android, Tauri en Windows y backend Cloudflare).

Este piloto establece e implementa de manera estricta una funcion de **Gobierno, Riesgos y Cumplimiento de Inteligencia Artificial (AI-GRC)**:

1. **Marco de AI-GRC y Taxonomia:**
   - Define el rol, alcance y límites operacionales de 9 agentes especializados (Project Manager, Full-Stack Capacitor, Tauri Desktop, Backend, QA/DevOps, Auditor de Seguridad, Oficial de Cumplimiento Normativo, Documentador y Soporte).
   - Clasificacion formal de 5 niveles de autonomia (L1 a L5), prohibiendo la promocion desasistida a produccion o ramas protegidas.
   - Especificacion completa: [docs/piloto_livestock_manager/AI_GOVERNANCE_RISK_COMPLIANCE.md](docs/piloto_livestock_manager/AI_GOVERNANCE_RISK_COMPLIANCE.md).

2. **Blueprint de Ejecucion del Piloto:**
   - Diseno de la epica piloto: Bloqueo preventivo de venta de leche bajo tratamiento sanitario segun el Real Decreto 787/2023.
   - Trazabilidad determinista por estados Kanban (`BACKLOG` -> `READY` -> `PLANNING` -> `IN_PROGRESS` -> `TESTING` -> `REVIEW` -> `DONE`).
   - Documento tecnico: [docs/piloto_livestock_manager/PILOT_BLUEPRINT_LIVESTOCK_MANAGER.md](docs/piloto_livestock_manager/PILOT_BLUEPRINT_LIVESTOCK_MANAGER.md).

3. **Configuracion Declarativa de la Factoria:**
   - Asignacion de modelos, allowlist de binarios sandbox (`node`, `npm`, `npx`, `pytest`, `cargo`), parametros de red y politicas de retencion.
   - Fichero: [docs/piloto_livestock_manager/CONFIG_LIVESTOCK_MANAGER.yaml](docs/piloto_livestock_manager/CONFIG_LIVESTOCK_MANAGER.yaml).

4. **Simulacion y Evidencias de Validacion:**
   - **Intercepcion de Fuga de Datos:** Bloqueo automatico a nivel de gateway ante solicitudes con clasificacion `restricted` (datos de explotacion REGA y coordenadas GPS).
   - **Ciclo Multiagente Normativo:** Derivacion automatica de 6 criterios de aceptacion rigurosos de seguridad alimentaria sin intervencion manual.
   - **Barrera de Aprobacion Humana:** Transicion controlada a `DONE` tras autorizacion formal auditada del Director Tecnico.
   - Informe de ejecucion y trazas: [docs/piloto_livestock_manager/REPORTE_SIMULACION_Y_EVIDENCIAS.md](docs/piloto_livestock_manager/REPORTE_SIMULACION_Y_EVIDENCIAS.md).
   - Script ejecutable: [scripts/simulate_livestock_pilot.py](scripts/simulate_livestock_pilot.py).

5. **Integracion con Microsoft Azure AI Foundry (Sdog Farm Software Factory):**
   - Conector tipado con soporte para Microsoft Entra ID (`sadogfarm.onmicrosoft.com`), gestion de tokens OAuth 2.0 y mapeo de despliegues (`sdogfarm-gpt4o`, `sdogfarm-phi4`, `sdogfarm-gpt4o-mini`).
   - Guia tecnica: [docs/INTEGRACION_MICROSOFT_FOUNDRY_SDOGFARM.md](docs/INTEGRACION_MICROSOFT_FOUNDRY_SDOGFARM.md).
   - Configuracion declarativa: [config/azure_foundry_sdogfarm.yaml](config/azure_foundry_sdogfarm.yaml).
