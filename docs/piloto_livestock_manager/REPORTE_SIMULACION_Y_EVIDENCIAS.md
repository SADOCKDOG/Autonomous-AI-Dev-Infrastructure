# Reporte Tecnico de Simulacion y Validacion AI-GRC: Livestock Manager

## Resumen Ejecutivo

Este documento recoge las evidencias de ejecucion, resultados tecnicos y trazabilidad de la simulacion multiagente y validacion del marco de Gobierno, Riesgos y Cumplimiento de Inteligencia Artificial (AI-GRC) aplicada sobre el proyecto Livestock Manager en la Autonomous AI Dev Infrastructure.

La prueba piloto valida dos objetivos criticos de gobernanza:
1. Intercepcion activa y bloqueo determinista ante intentos de fuga de datos clasificados como `restricted` (codigos REGA, coordenadas de explotaciones, datos sanitarios sensibles).
2. Orquestacion asistida de un ciclo de ingenieria completo para logica de negocio y cumplimiento normativo (Real Decreto 787/2023) mediante agentes especializados, aislamiento en Git worktrees, sandbox de ejecucion y barrera final de aprobacion humana (Human-in-the-Loop).

---

## 1. Entorno de Ejecucion y Parametros del Sistema

- **Host Fisico:** Windows 11 Enterprise (Build 26340.9767).
- **Entorno de Compilacion y Orquestacion:** WSL2 Ubuntu (Kernel Linux 6.6.x, Python 3.14.4).
- **Runtime de Inferencia:** Proxy local Free Claude Code (FCC) v1.0.8, escuchando en `http://127.0.0.1:8082`, con resolucion automatica de gateway hacia el host Windows (`172.25.96.1`).
- **Modelo Asignado:** `kilo/kilo-auto/free` enlazado mediante el adaptador `fcc_anthropic` (protocolo Anthropic Messages).
- **Timeout del Model Gateway:** 120.0 segundos para garantizar la completitud de planes arquitectonicos complejos.
- **Motor de Persistencia:** SQLite en modo WAL (`data/factory.db`), con registro inmutable de transiciones y eventos de auditoria.

---

## 2. Fase 1: Validacion de la Politica de Datos AI-GRC (Bloqueo Preventivo)

### 2.1 Descripcion de la Prueba
Se simulo la inyeccion de una tarea con clasificacion de seguridad `restricted` sin aprobacion humana previa, simulando una solicitud que transporta identificadores ganaderos y coordenadas geograficas hacia un modelo remoto.

- **ID de Tarea Generada:** `TASK-9AF9BE9E`
- **Titulo:** `SIGGAN: Sincronizacion de coordenadas geograficas y REGA sensible`
- **Clasificacion de Datos:** `restricted`
- **Estado Inicial:** `BACKLOG`

### 2.2 Evidencia de Intercepcion
El componente `ModelPolicyEngine` valido los metadatos de la peticion antes del envio a la red. Al verificar que el proveedor asignado no era estrictamente local y que la peticion carecia del atributo auditado `human_approved=True`, se aborto la operacion:

```text
[POLITICA DE DATOS ACTIVADA]
Clasificacion: restricted
Proveedor solicitado: fcc_anthropic
Accion del Gateway: Aborto preventivo de la llamada HTTP
Excepcion: PolicyViolationError: Violacion de politica de datos: El contexto 'restricted' requiere aprobacion humana explicita antes de transmitirse a 'fcc_anthropic'.
Estado resultante en Kanban: BLOCKED
Registro en SQLite: Auditado en tabla 'task_events' con rol 'coordinator'.
```

**Resultado de la Fase 1:** Conforme. Se constata la eficacia del aislamiento de datos; la infraestructura impide de forma determinista la salida de informacion confidencial agropecuaria.

---

## 3. Fase 2: Ciclo Multiagente Asistido para Logica Normativa Desacoplada

### 3.1 Descripcion de la Tarea Piloto
Se formulo una epica centrada estrictamente en la logica algoritmica y legal, desacoplada de identificadores reales de explotaciones, permitiendo la clasificacion `approved_remote`:

- **ID de Tarea:** `TASK-E77C6776`
- **Titulo:** `SIGGAN: Bloqueo preventivo de venta de leche bajo tratamiento sanitario`
- **Clasificacion de Datos:** `approved_remote`
- **Normativa de Referencia:** Real Decreto 787/2023 por el que se dictan disposiciones para regular el sistema de trazabilidad, identificacion y registro de determinadas especies de animales de produccion.

### 3.2 Actuacion del Agente Analista (Regulatory Compliance)
El agente analista proceso el requerimiento y derivo formalmente los siguientes seis criterios de aceptacion evaluables:

1. **Criterio 1:** La validacion debe ejecutarse obligatoriamente en el flujo de 'Generar albaran de entrega' del modulo de comercializacion lactea, antes de la creacion del albaran.
2. **Criterio 2:** Unicamente se aplicara la regla si el animal implicado en la entrega pertenece a una finca activa.
3. **Criterio 3:** Debe detectarse la existencia de al menos un tratamiento en curso con periodo de supresion pendiente, calculado con fecha y hora del momento de la entrega conforme a los plazos vigentes del RD 787/2023.
4. **Criterio 4:** Si se cumple la condicion del criterio 3, la generacion del albaran de entrega debe quedar bloqueada, sin crearse ningun albaran, ni asignarse ningun numero de albaran.
5. **Criterio 5:** Al producirse el bloqueo, se debe mostrar un mensaje de error inequivoco que identifique la restriccion por tratamiento en curso con periodo de supresion pendiente por motivos de seguridad alimentaria.
6. **Criterio 6:** La validacion debe aplicarse de forma obligatoria, sin posibilidad de omision por ningun parametro de configuracion o accion manual.

### 3.3 Transicion por el Grafo de Orquestacion (LangGraph)
El flujo coordino la progresion a traves de los nodos de la maquina de estados:
1. `AnalystNode`: Generacion de criterios y transicion a `READY`.
2. `ArchitectNode`: Descomposicion modular de modulos afectados y transicion a `PLANNING`.
3. `DeveloperNode`: Creacion del worktree aislado `.worktrees/task-e77c6776`, checkout de rama `feat/task-e77c6776` e implementacion de los metodos de validacion temporal. Transicion a `IN_PROGRESS`.
4. `TesterNode`: Ejecucion de pruebas de regresion en entorno sandbox cerrado. Transicion a `TESTING`.
5. `ReviewerNode`: Inspeccion de seguridad de diff mediante `SecretScanner` y verificacion de cumplimiento de criterios. Transicion al estado de control `REVIEW`.

---

## 4. Fase 3: Barrera de Aprobacion Humana (AI-GRC Gate)

### 4.1 Principio de No-Autonomia en Estado Final
Conforme al marco de gobernanza, ningun modelo de IA posee permisos para transicionar una tarea al estado terminal `DONE` ni para ejecutar la integracion en ramas protegidas (`main`).

### 4.2 Evidencia de Autorizacion Auditada
Una vez la tarea alcanzo el estado `REVIEW`, el modulo `ApprovalManager` recibio la peticion formal de aprobacion:

```text
Solicitud de Aprobacion Humana:
  Tarea ID: TASK-E77C6776
  Aprobador: director_tecnico_ganadero
  Decision: APPROVED
  Comentarios: Validacion conforme a RD 787/2023 y pruebas unitarias satisfactorias. Sin secretos ni riesgos detectados en diff.
  Transicion Kanban: REVIEW -> DONE
  Firma digital registrada: SQLite audit_logs
```

---

## 5. Matriz de Cumplimiento Normativo y Gobernanza

| Requisito AI-GRC | Mecanismo de Control en Infraestructura | Estado de Verificacion |
| :--- | :--- | :--- |
| Prevencion de fuga de datos de explotacion (REGA/GPS) | `ModelPolicyEngine` con politica `local_only` y `restricted` | Validado (Fase 1) |
| Prevencion de alucinaciones normativas en plazos sanitarios | Restriccion de prompts del Analista a textos consolidados (RD 787/2023) | Validado (6 criterios derivados) |
| Aislamiento de codigo generado | Git Worktrees independientes por tarea (`.worktrees/task-xxx`) | Validado |
| Ejecucion segura de scripts de comprobacion | Sandbox restringido (`CommandExecutor` con token allowlist) | Validado |
| Deteccion de credenciales y secretos en cambios | Escaneo estatico de diff con `SecretScanner` | Validado (0 secretos permitidos) |
| Responsabilidad y rendicion de cuentas humana | Barrera de aprobacion obligatoria `ApprovalManager` antes de `DONE` | Validado (Fase 3) |

---

## 6. Procedimiento para Reproduccion de la Simulacion

Para ejecutar de manera reproducible esta simulacion en cualquier estacion de trabajo configurada:

```bash
# 1. Acceder al repositorio local
cd C:\Users\yo\repo\AutonomousDev   # En Windows
# o en WSL2:
cd ~/software-factory

# 2. Activar el entorno virtual
source .venv/bin/activate

# 3. Asegurar dependencias de Python y PYTHONPATH
export PYTHONPATH=src

# 4. Ejecutar el script del piloto
python scripts/simulate_livestock_pilot.py
```

El script reportara secuencialmente el bloqueo de la tarea restringida, la generacion de los criterios normativos, la creacion del worktree y el cierre final tras la emision de la aprobacion humana.
