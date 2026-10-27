# Diseno y Blueprint de Ejecucion del Piloto End-to-End: Livestock Manager
## Infraestructura Autonoma de Desarrollo de Software

**Proyecto de Referencia:** Livestock Manager (PWA offline-first, Android Capacitor 7, Windows Tauri)  
**Entorno de Ejecucion:** Software Factory Hibrida Local (Windows 11 + WSL2 Ubuntu)  
**Objetivo del Piloto:** Validar la orquestacion completa de requerimientos de mision critica, aplicando el marco AI-GRC sobre un modulo normativo real.  

---

## 1. Alcance Funcional del Caso Piloto

Para validar la infraestructura en condiciones reales de exigencia tecnica y regulatoria, se ha seleccionado el siguiente modulo de mision critica:

### Epica Seleccionada: "Bloqueo Preventivo de Venta de Leche bajo Tratamiento Sanitario y Trazabilidad SIGGAN"
* **Contexto de Dominio:** En explotaciones con produccion lactea activa, si un animal recibe un tratamiento farmacologico veterinario con periodo de supresion sanitario activo, el sistema debe impedir de manera determinista la inclusion de su produccion en cualquier albaran de entrega a central lechera (Reglamento UE 37/2010 y RD 787/2023).
* **Impacto:** Seguridad alimentaria, prevencion de sanciones de la Administracion y cumplimiento de la calificacion sanitaria de la finca.

---

## 2. Matriz de Configuracion de la Infraestructura para el Piloto

La Software Factory debe configurarse con los siguientes parametros especificos en su Model Gateway y motor de ejecucion:

```text
                        CONFIGURACION DEL PILOTO
+-------------------------------------------------------------------------+
| Proveedor Principal de Inferencia: FCC Proxy (127.0.0.1:8082)           |
| Modelo Asignado: kilo/kilo-auto/free (o endpoint local homologado)      |
| Directorio de Trabajo: C:\Users\yo\repo\AutonomousDev                   |
| Sistema de Aislamiento: Git Worktree (.worktrees/task-livestock-pilot)  |
| Clasificacion de Datos de la Tarea: restricted                          |
+-------------------------------------------------------------------------+
```

### Allowlist de Herramientas para el Sandbox del Piloto
Se amplian los comandos autorizados en `config/policies.yaml` para permitir la verificacion de componentes JavaScript/Node y Python:
- `git`: `status`, `diff`, `log`, `branch`, `worktree`, `add`, `commit`
- `pytest`: Ejecucion de suites de validacion del orquestador y backend
- `python3`: Interprete controlado para scripts de dominio y pruebas
- `node` / `npx`: `playwright test`, `eslint` (para suites de frontend de Livestock Manager)
- `ruff`: `check`, `format`

---

## 3. Protocolo de Ejecucion End-to-End (Paso a Paso)

```text
 [BACKLOG] Incepcion por Project Manager (Creacion de Tarjeta)
    |
    v
 [READY] Analisis de Requerimientos y Validacion Regulatoria AI-GRC
    |
    v
 [PLANNING] Diseno Arquitectonico y Plan de Archivos Afectados
    |
    v
 [IN_PROGRESS] Aislamiento en Git Worktree e Implementacion de Codigo
    |
    v
 [TESTING] Ejecucion de Pruebas de QA en Sandbox Automatizado
    |
    v
 [REVIEW] Escaneo de Secretos, Auditoria de Seguridad y Diff
    |
    v
 [DONE] Barrera Obligatoria de Aprobacion Humana Registrada en SQLite
```

### Paso 1: Incepcion de la Tarea (`BACKLOG`)
* **Agente:** `agent_pm` (Project Manager)
* **Accion:** Se emite la tarjeta con el siguiente payload:
  ```json
  {
    "title": "Bloqueo preventivo de entrega de leche en periodo de supresion",
    "description": "Implementar validacion en el servicio de albaranes para rechazar entregas cuando existan tratamientos antibioticos activos con tiempo de espera pendiente segun RD 787/2023.",
    "priority": "critical",
    "data_classification": "restricted"
  }
  ```
* **Resultado:** Tarea registrada en SQLite con estado inicial `BACKLOG`.

### Paso 2: Analisis y Definicion de Criterios (`BACKLOG → READY`)
* **Agentes:** `agent_analyst` y `agent_compliance`
* **Accion:** Se generan criterios de aceptacion evaluables y no ambiguos:
  1. *Criterio 1:* Si un animal tiene un registro en `sanitarios_ganado` con fecha actual menor a `fecha_fin_supresion`, la funcion `validarEntregaLeche` debe retornar error `422 Unprocessable Entity`.
  2. *Criterio 2:* El mensaje de rechazo debe detallar el crotal del animal, el principio activo y la fecha exacta en que finaliza la supresion.
  3. *Criterio 3:* El evento de intento de entrega bloqueada debe persistirse inmutablemente en el log de trazabilidad sanitaria.
* **Resultado:** Transicion validada a `READY`.

### Paso 3: Diseno de Arquitectura Tecnica (`READY → PLANNING`)
* **Agente:** `agent_architect`
* **Accion:** Inspecciona el arbol de codigo y emite el plan tecnico:
  - Archivos afectados: `js/sanidad.js`, `js/comercializacion.js`, `tests/unit/test-lacteo-sanidad.js`.
  - Contrato de interfaz: Metodo `SanidadService.verificarPeriodoEspera(animalId, tipo='leche')`.
  - Evaluacion de riesgos: Rendimiento en explotaciones con mas de 500 animales en ordeno; uso de indices locales sobre la base de datos IndexedDB/SQLite.
* **Resultado:** Transicion validada a `PLANNING`.

### Paso 4: Implementacion Aislada (`PLANNING → IN_PROGRESS`)
* **Agentes:** `agent_dev_backend` y `agent_dev_android`
* **Accion:**
  - El motor `WorktreeManager` despliega el entorno fisico aislado en `.worktrees/task-livestock-pilot` sobre la rama `feat/task-livestock-pilot`.
  - Se implementa la logica defensiva en el archivo de dominio.
  - Se genera el commit bajo estandares convencionales: `feat(sanidad): bloqueo automatico de entrega lactea con periodo de espera activo`.
* **Resultado:** Transicion validada a `IN_PROGRESS`.

### Paso 5: Verificacion de Calidad en Sandbox (`IN_PROGRESS → TESTING`)
* **Agente:** `agent_qa_devops`
* **Accion:**
  - Invocacion del comando de pruebas en el sandbox: `pytest tests/unit/test_execution_and_git.py`.
  - Captura del tiempo de ejecucion, codigo de salida (`exit_code = 0`) y volumen de salida dentro de la cuota de 1 MB.
  - Comprobacion de cobertura de los casos limite (animales con tratamientos vencidos vs activos).
* **Resultado:** Transicion validada a `TESTING`.

### Paso 6: Escaneo de Seguridad y Auditoria (`TESTING → REVIEW`)
* **Agentes:** `agent_security` y `agent_reviewer`
* **Accion:**
  - `SecretScanner` analiza las lineas modificadas (`git diff master...HEAD`) verificando ausencia de tokens, claves o contraseñas.
  - El revisor audita que no se hayan introducido llamadas a endpoints externos no autorizados.
  - El orquestador detiene el flujo automatico en estado `REVIEW`.
* **Resultado:** Transicion validada a `REVIEW`. La tarea aguarda decision humana.

### Paso 7: Barrera de Aprobacion Humana y Cierre (`REVIEW → DONE`)
* **Autoridad:** Operador Humano / Lead Ganadero
* **Accion:** Tras verificar la evidencia de tests y el diff en el tablero, el operador ejecuta:
  ```json
  {
    "approver": "responsable_tecnico_ganadero",
    "decision": "APPROVED",
    "comments": "Validada la logica de supresion sanitaria conforme a normativa SIGGAN. Aprobado para integracion."
  }
  ```
* **Resultado:** Transicion validada a `DONE`, registro inmutable en `audit_logs` y desmontaje limpio del worktree temporal.

---

## 4. Metricas e Indicadores de Rendimiento del Piloto (KPIs)

Para evaluar el exito de este piloto, la plataforma monitoriza:
1. **Tasa de Cumplimiento Regulatorio:** 100% de criterios de aceptacion normativos satisfechos sin intervencion manual en el codigo.
2. **Eficacia de la Barrera de Seguridad:** Cero fugas de credenciales en diffs y cero llamadas de red no autorizadas para datos clasificados como `restricted`.
3. **Latencia del Ciclo Completo:** Tiempo total transcurrido desde la creacion en `BACKLOG` hasta la disposicion en `REVIEW` inferior a 3 minutos utilizando el proxy local `fcc-server`.
4. **Trazabilidad Inmutable:** Disponibilidad del registro completo de eventos y auditoria en SQLite respaldable mediante `.backup`.
