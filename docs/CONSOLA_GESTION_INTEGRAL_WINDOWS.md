# Consola de Gestion Integral de Escritorio para Windows
## Software Factory Control Center · Sdog Farm Software Factory (`sadogfarm.onmicrosoft.com`)

**Ambito:** Consola Nativa de Escritorio para Operadores y Responsables de Cumplimiento AI-GRC  
**Version:** 1.0  
**Fecha:** 27 de octubre de 2026  
**Repositorio GitHub Dedicado:** [Console-AI-Dev-Infrastructure](https://github.com/SADOCKDOG/Console-AI-Dev-Infrastructure)  
**Ruta Local:** `C:\Users\yo\repo\AutonomousDevConsole`  
**Lanzador Rapido:** [run_console.bat](../../run_console.bat)  

---

## 1. Descripcion General y Arquitectura

La **Consola de Gestion Integral de Escritorio para Windows** es una aplicacion de grado empresarial disenada para centralizar en una sola interfaz grafica la monitorizacion de servicios, la gestion de proyectos y tareas Kanban, el control de incidencias normativas y la emision de informes de auditoria forense.

La aplicacion se ejecuta de forma nativa en el host Windows 11 sin requerir dependencias externas complejas, aprovechando el runtime de Python 3.14 y los componentes graficos del sistema.

```text
+-----------------------------------------------------------------------------------------+
|                  CONSOLA DE GESTION INTEGRAL · CONTROL CENTER (WINDOWS)                 |
+-----------------------------------------------------------------------------------------+
| [SERVICIOS & SALUD]   [PROYECTOS & KANBAN]   [GESTOR INCIDENCIAS]   [AUDITORIA & EVENTOS]
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  1. PANEL DE SERVICIOS           2. TABLERO KANBAN             3. GESTOR DE INCIDENCIAS |
|  - FCC Local Server (8082)       - Visualizador por estados     - Tareas bloqueadas GRC |
|  - FastAPI Backend (8000)        - Creacion de nuevas tareas    - Alertas SecretScanner |
|  - SQLite WAL (factory.db)       - Aprobacion humana (REVIEW)   - Workflow de cierre    |
|  - Microsoft Foundry Sdog Farm   - Disparo de ciclo multiagente - Resolucion auditada   |
|  - Sandbox & Worktrees           - Expediente tecnico integral                          |
|                                                                                         |
|  4. REGISTRO Y AUDITORIA                                                                |
|  - Stream inmutable de 'task_events' y 'audit_logs'                                     |
|  - Generador y exportador de Informes de Cumplimiento AI-GRC en Markdown                |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Modulos Funcionales de la Consola

### Modulo 1: Monitorizacion y Control de Servicios
- **Supervision en Tiempo Real:**
  - **Free Claude Code (FCC Server):** Sondeo activo del puerto loopback `8082` e inspeccion del catalogo de 4.405 modelos.
  - **Backend FastAPI:** Comprobacion de salud del puerto `8000` y disponibilidad de endpoints REST.
  - **Persistencia SQLite:** Integridad del fichero `data/factory.db` y modo Write-Ahead Logging (WAL).
  - **Microsoft Foundry Sdog Farm:** Conexion y enrutamiento hacia el tenant `sadogfarm.onmicrosoft.com` bajo el EU Data Boundary.
  - **Motor Sandbox y Worktrees:** Verificacion de binarios autorizados (`git`, `python3`, `node`, `npm`, `npx`, `cargo`).
- **Acciones Directas:**
  - Boton de arranque y parada del servidor FastAPI en subproceso de Windows.
  - Test de conectividad individual y masivo con medicion de latencias en milisegundos.
  - Consola de logs y telemetria en tiempo real.

### Modulo 2: Gestion de Estados y Proyectos Kanban
- **Visualizacion y Filtrado:**
  - Selector de proyecto (`Livestock Manager`, `Infrastructure Core`, `Sdog Farm Software Factory`).
  - Filtro por estado operativo (`BACKLOG`, `READY`, `PLANNING`, `IN_PROGRESS`, `TESTING`, `REVIEW`, `DONE`, `BLOCKED`).
- **Expediente Tecnico:**
  - Inspeccion del plan formulado por el Arquitecto, criterios normativos de aceptacion, clasificacion de datos (`local_only`, `approved_remote`, `restricted`), rama Git y worktree asignado.
- **Acciones de Gobernanza:**
  - **Boton "+ Nueva Tarea":** Dialogo asistido con clasificacion de datos obligatoria.
  - **Boton "Aprobacion Humana (AI-GRC)":** Permite al Director Tecnico o Veterinario revisar el diff y emitir la decision formal para promover tareas de `REVIEW` a `DONE`.
  - **Boton "Ejecutar Ciclo Multiagente":** Dispara la ejecucion orquestada en segundo plano sin congelar la interfaz grafica.

### Modulo 3: Gestor de Incidencias Operacionales y AI-GRC
- **Deteccion Automatica:**
  - Cada vez que una tarea queda bloqueada por intento de fuga de datos sensibles o deteccion de secretos en el diff, el sistema registra una incidencia con severidad `critical` o `high`.
- **Registro Manual:**
  - Permite a los supervisores documentar incidentes normativos o anomalías técnicas.
- **Ciclo de Resolucion:**
  - Estados: `open` -> `analyzing` -> `resolved` -> `closed`.
  - Dialogo modal para registrar notas de resolucion tecnica y firma digital del operador.

### Modulo 4: Registro de Eventos e Informes de Auditoria
- **Visor Forense:**
  - Visualizacion de la secuencia cronologica inmutable de transiciones de agentes (`task_events`) y acciones protegidas (`audit_logs`).
- **Exportador Formal de Informes:**
  - Genera informes de auditoria en [reports/](../../reports/) en formato Markdown conteniendo métricas, tareas por estado, incidencias resueltas y firmas humanas registradas.

---

## 3. Modo de Empleo y Ejecucion

### Opcion A: Lanzador por Lotes (Doble Clic)
Hacer doble clic en el archivo [run_console.bat](../../run_console.bat) ubicado en la raiz del repositorio `C:\Users\yo\repo\AutonomousDev`.

### Opcion B: Linea de Comandos (PowerShell / CMD)
```powershell
cd C:\Users\yo\repo\AutonomousDev
python desktop_console\app.py
```
