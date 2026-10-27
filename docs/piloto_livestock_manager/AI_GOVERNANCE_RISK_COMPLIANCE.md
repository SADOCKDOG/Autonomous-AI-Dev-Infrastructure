# Marco de Gobierno, Riesgos y Cumplimiento de Inteligencia Artificial (AI-GRC)
## Proyecto Piloto: Livestock Manager en la Software Factory Hibrida Local

**Version:** 1.0  
**Fecha:** 27 de octubre de 2026  
**Ambito:** Operacion de Agentes de Inteligencia Artificial en Entornos de Mision Critica Ganadera y Regulatoria  
**Autoridad:** Direccion de Ingenieria y Oficina de Cumplimiento Normativo (AI-GRC)  

---

## 1. Mision y Fundamentos del Marco AI-GRC

La implementacion de sistemas de software complejos mediante agentes de inteligencia artificial no puede depender unicamente de capacidades de generacion de codigo. En entornos regulados como el sector ganadero e industrial alimentario (sujetos a normativas como el Reglamento Europeo de Inteligencia Artificial - AI Act, RD 787/2023 de trazabilidad ganadera, RD 479/2004 del REGA, Reg. UE 1069/2009 SANDACH y RGPD/LOPD-GDD), se exige una funcion estructurada de **Gobierno, Riesgos y Cumplimiento de la IA (AI Governance, Risk & Compliance - AI-GRC)**.

El objetivo del marco AI-GRC en esta infraestructura es:
1. **Identificar y censar cada agente:** Saber con precision que agentes intervienen, con que modelos, bajo que versiones de prompt y para que competencias especificas.
2. **Gobernar el flujo de datos:** Clasificar de manera determinista la informacion para evitar la fuga de datos confidenciales o sensibles (coordenadas de fincas, datos sanitarios, NIFs ganaderos) hacia proveedores no locales.
3. **Definir niveles de autonomia:** Acotar que decisiones puede tomar un agente sin intervencion y cuales exigen validacion cruzada o aprobacion humana obligatoria.
4. **Evaluar y mitigar riesgos tecnicos:** Prevenir alucinaciones en plazos sanitarios, evitar la relajacion de controles de seguridad y bloquear comandos destructivos.
5. **Garantizar la trazabilidad y auditoria:** Registrar de forma inmutable cada transicion, diff de codigo, ejecucion de pruebas y decision humana en registros de auditoria locales.

---

## 2. Taxonomia y Registro de Agentes Especializados

Para el ecosistema de Livestock Manager, el equipo de agentes se divide en cuatro capas funcionales:

```text
                       CAPA DE DIRECCION Y GOBIERNO
     +--------------------------------------------------------------+
     | [Project Manager] <----> [Compliance & Regulatory Officer]   |
     +------------------------------┬-------------------------------+
                                    |
     +------------------------------+-------------------------------+
     |                                                              |
     v                                                              v
CAPA DE ARQUITECTURA Y DISENO                      CAPA DE AUDITORIA Y SEGURIDAD
+---------------------------------------+          +-----------------------------+
| [System Architect & UI/UX Director]   |          | [Security & Privacy Auditor]|
+-------------------┬-------------------+          +--------------┬--------------+
                    |                                             |
                    v                                             v
       CAPA DE INGENIERIA Y DESARROLLO                CAPA DE CALIDAD Y DEVOPS
+---------------------------------------+          +-----------------------------+
| [Backend & Data Engineer]             |          | [QA Automation Engineer]    |
| [Frontend & PWA Developer]            |          | [DevOps & Release Engineer] |
| [Android / Capacitor Specialist]      |          +--------------┬--------------+
| [Windows / Tauri Native Specialist]   |                         |
+---------------------------------------+                         |
                                                                  v
                                                     CAPA DE SOPORTE Y DOCS
                                                   +-----------------------------+
                                                   | [Technical Writer & Support]|
                                                   +-----------------------------+
```

### Definicion de Responsabilidades y Competencias

| Identificador de Agente | Rol Funcional | Alcance Permitido | Limite Estricto / Accion Prohibida |
|---|---|---|---|
| `agent_pm` | Project Manager | Descomposicion de epicas, creacion de tareas Kanban, priorizacion y asignacion. | No redacta codigo ejecutable ni modifica configuraciones del sistema. |
| `agent_compliance` | Oficial de Cumplimiento Normativo | Validacion contra SIGGAN, BADIGEX, RD 787/2023, SANDACH y AI Act. | No puede anular controles de seguridad ni relajar validaciones regulatorias. |
| `agent_architect` | Arquitecto de Plataforma | Especificacion tecnica, diseno de esquemas de datos, diseno UI/UX neón y contratos API. | No aprueba sus propios cambios ni realiza commits en ramas principales. |
| `agent_dev_backend` | Desarrollador Backend | Logica de dominio, servicios de exportacion oficial, SQLite/IndexedDB y workers de soporte. | Limitado al directorio del componente y worktree asignado. |
| `agent_dev_android` | Especialista Android / Capacitor | Integracion de plugins Capacitor 7, sincronizacion offline, camara y lectores RFID. | Prohibido modificar manifiestos de permisos sin aprobacion humana. |
| `agent_dev_windows` | Especialista Windows / Tauri | Modulos de escritorio Tauri, empaquetado MSIX, acceso a APIs de Windows y soporte local. | Prohibido alterar certificados de firma o dependencias nativas C++/Rust sin sandbox. |
| `agent_qa_devops` | Ingeniero de QA y Automatizacion | Diseno y ejecucion de suites Playwright, pruebas unitarias y empaquetado de release. | No puede marcar tests en bypass ni omitir errores de ejecucion. |
| `agent_security` | Especialista de Seguridad | Auditoria de secretos, analisis estatico, analisis de dependencias y politicas de sandbox. | Bloquea inmediatamente cualquier pipeline si detecta vulnerabilidades criticas. |
| `agent_docs_support` | Documentacion y Soporte | Generacion de guias de usuario oficiales (HTML/Markdown), changelogs y triage de incidencias. | No modifica logica de negocio ni esquemas de bases de datos. |

---

## 3. Niveles de Autonomia y Barreras de Control

El marco define cinco niveles formales de autonomia operativa:

```text
Nivel 0: Solo Informativo (Generacion de informes, lectura y diagnostico sin cambios de estado)
   |
Nivel 1: Recomendador Asistido (Propuesta de planes, criterios de aceptacion y diseno de diffs)
   |
Nivel 2: Ejecutor Supervisado (Creacion de worktrees, edicion en ramas feat/, ejecucion de tests en sandbox)
   |
Nivel 3: Autonomia Acotada (Resolucion automatica de linters y refactorizaciones menores en sandbox)
   |
Nivel 4: Accion de Alto Impacto (Merges a main, releases, cambios normativos, modificacion de periodos de espera)
   ==> REQUIERE AUTORIZACION HUMANA DETERMINISTA (BARRERA OBLIGATORIA)
```

### Reglas de Bloqueo Innegociables
1. **Regla de Doble Verificacion Sanitaria:** Cualquier logica vinculada a **periodos de supresion de medicamentos veterinarios** (tiempo de espera en carne y leche) debe ser validada obligatoriamente por el agente `agent_compliance` y ratificada por un operador humano antes de incorporarse al codigo de produccion.
2. **Regla de Integridad de Trazabilidad Ganadera:** El borrado fisico de registros animales en produccion esta terminantemente prohibido; toda baja debe ser una anulacion logica con registro inmutable del motivo (muerte, sacrificio, venta, SANDACH).
3. **Regla de Cero Alucinacion en Exportaciones Oficiales:** Las estructuras de exportacion para SIGGAN/BADIGEX no pueden inferirse estadisticamente; deben contrastarse contra las expresiones regulares y esquemas XSD oficiales configurados en la plataforma.

---

## 4. Matriz de Clasificacion y Fronteras de Datos

| Categoria de Informacion | Ejemplos en Livestock Manager | Clasificacion | Politica de Enrutamiento de Inferencia |
|---|---|---|---|
| **Identificadores Ganaderos Sensibles** | Codigos REGA, numero de identificacion animal (crotal/DIB), claves ADSG | `local_only` | Inferencia en modelo local o proxy FCC local. Prohibido envio a nubes publicas no homologadas. |
| **Datos Fiscales y Personales** | NIF/CIF de compradores, contratos comerciales lácteos, cuentas bancarias | `local_only` | Inferencia estrictamente en localhost. Redaccion automatica en logs. |
| **Prescripciones y Sanidad** | Libro de tratamientos, sustancias activas, periodos de supresion sanitaria | `restricted` | Requiere consentimiento expreso del operador humano previo al procesamiento. |
| **Codigo Fuente y Logica de Dominio** | Algoritmos de ordenacion, calculos de carga ganadera (UGM), componentes CSS/JS | `approved_remote` | Inferencia autorizada en proveedores remotos aprobados (Azure AI Foundry / FCC). |
| **Especificaciones y Documentacion** | Manuales de usuario, plantillas de diseño neón, guías de comercializacion | `approved_remote` | Inferencia remota estándar. |

---

## 5. Gestion de Incidentes y Deriva de IA (AI Incident Management)

Se definen tres tipos de incidentes criticos asociados al comportamiento de los agentes:

1. **Incidente de Alucinacion Normativa (Severity 1):** Un agente propone o implementa una regla que contradice la normativa vigente (ejemplo: reducir el plazo legal de notificacion REGA de 7 a 10 dias).
   - *Accion de contencion:* Bloqueo automatico de la tarea (`status = BLOCKED`), alerta al responsable humano y reversion del worktree.
2. **Incidente de Filtracion de Datos (Severity 1):** Intento de enviar una carga util que contenga claves privadas, credenciales o registros marcados como `local_only` hacia una API externa.
   - *Accion de contencion:* Intercepcion en la capa del `ModelPolicyEngine`, levantamiento de `PolicyViolationError` y registro en `audit_logs`.
3. **Incidente de Degeneracion de Codigo o Bucle (Severity 2):** Un agente desarrollador no logra superar las pruebas tras superar el limite maximo de iteraciones (configurado en 3 intentos).
   - *Accion de contencion:* Detencion del flujo, congelacion del worktree y generacion de ticket de intervencion para el equipo humano.
