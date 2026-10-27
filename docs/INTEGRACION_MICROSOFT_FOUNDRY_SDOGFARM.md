# Integracion Tecnica: Microsoft Azure AI Foundry en Sdog Farm Software Factory

## 1. Identificacion del Tenant y Alcance Corporativo

- **Organizacion:** Sdog Farm Software Factory
- **Tenant de Microsoft Entra ID:** `sadogfarm.onmicrosoft.com`
- **Hub / Proyecto AI Foundry:** `Sdog Farm Software Factory`
- **Jurisdiccion y Soberania:** Union Europea (EU Data Boundary), region recomendada `spaincentral` (Espana Central) o `westeurope` (Europa Occidental).
- **Finalidad:** Proveedor de inferencia en la nube gobernado y auditado para los agentes de la Software Factory autonoma, con soporte de modelos empresariales (`gpt-4o`, `phi-4`, `gpt-4o-mini`).

---

## 2. Arquitectura de Autenticacion y Handshake con Entra ID

La factoria de software implementa dos modalidades de autenticacion tipadas hacia Microsoft Foundry:

### Modalidad A: Credenciales de Servicio (Service Principal / Entra ID App)
Es el metodo estandar recomendado para ejecucion desasistida y pipelines de CI/CD.

1. **Registro de Aplicacion en Entra ID:**
   - Registrar la aplicacion `AutonomousDev-Factory` en el portal de Azure bajo el directorio `sadogfarm.onmicrosoft.com`.
   - Generar un secreto de cliente (`client_secret`).
2. **Asignacion de Roles de Acceso (RBAC):**
   - En el recurso de Azure OpenAI / AI Foundry `Sdog Farm Software Factory`, asignar el rol:
     - `Cognitive Services OpenAI User` (ID de rol: `5e0bd9e1-4314-4fb0-bc5c-08b777a142a0`) a la aplicacion registrada.
3. **Flujo de Intercambio OAuth 2.0:**
   El adaptador `AzureFoundryProvider` solicita un token JWT al endpoint de Entra ID:
   ```http
   POST https://login.microsoftonline.com/sadogfarm.onmicrosoft.com/oauth2/v2.0/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=client_credentials
   &client_id={AZURE_CLIENT_ID}
   &client_secret={AZURE_CLIENT_SECRET}
   &scope=https://cognitiveservices.azure.com/.default
   ```
   El token emitido es cacheado automaticamente con renovacion preventiva 60 segundos antes de su expiracion.

### Modalidad B: Clave de Acceso Directa (API Key)
Permite arranque rapido mediante la directiva `api-key` configurada en el recurso de Cognitive Services:
```http
POST {AZURE_AI_ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version=2024-06-01
api-key: {AZURE_CLIENT_SECRET}
```

---

## 3. Mapeo de Modelos y Asignacion por Rol de Agente

Para optimizar latencias, consumo de cuota (TPM) y costes, los agentes se distribuyen en los despliegues de Azure Foundry conforme al archivo [config/azure_foundry_sdogfarm.yaml](../config/azure_foundry_sdogfarm.yaml):

| Rol de Agente | Despliegue en Foundry | Modelo Base | Justificacion Tecnica |
| :--- | :--- | :--- | :--- |
| **Arquitecto** | `sdogfarm-gpt4o` | GPT-4o | Diseno modular, calculo de dependencias y analisis de riesgos |
| **Revisor de Seguridad** | `sdogfarm-gpt4o` | GPT-4o | Escaneo semantico de vulnerabilidades, compliance y diffs |
| **Analista Normativo** | `sdogfarm-phi4` / `gpt-4o-mini` | Phi-4 / Mini | Descomposicion rapida de requerimientos a criterios |
| **Desarrollador** | `sdogfarm-phi4` / `gpt-4o` | Phi-4 / GPT-4o | Generacion de codigo TypeScript y adaptadores Android/Tauri |
| **Tester Sandbox** | `sdogfarm-gpt4o-mini` | GPT-4o-mini | Evaluacion de salidas de tests y diagnostico de fallos |

---

## 4. Fronteras de Datos y Gobernanza AI-GRC

Conforme al marco [AI_GOVERNANCE_RISK_COMPLIANCE.md](piloto_livestock_manager/AI_GOVERNANCE_RISK_COMPLIANCE.md):

1. **Datos `local_only` (PROHIBICION ESTRICTA):**
   - Coordenadas GPS de explotaciones ganaderas, codigos REGA individuales, certificados digitales de agricultores y claves privadas.
   - El motor `ModelPolicyEngine` intercepta la llamada y arroja `PolicyViolationError` antes de cualquier conexion con Azure Foundry.
2. **Datos `approved_remote` (PERMITIDO):**
   - Logica algoritmica (p.ej. reglas de calculo de tiempos de supresion de leche/carne segun RD 787/2023), esquemas de interfaces TypeScript, pruebas unitarias desacopladas y refactorizaciones de componentes visuales.
3. **EU Data Boundary:**
   - Todo el procesamiento ocurre en centros de datos ubicados dentro de la Union Europea (`spaincentral` / `westeurope`), cumpliendo el Reglamento General de Proteccion de Datos (RGPD) y las exigencias de seguridad alimentaria.

---

## 5. Variables de Entorno de Configuracion (.env)

Para activar el entorno productivo de Microsoft Foundry en Sdog Farm, configurar en `.env`:

```bash
# Microsoft Azure AI Foundry - Sdog Farm Software Factory
AZURE_AI_ENDPOINT=https://sdogfarm-foundry.cognitiveservices.azure.com/
AZURE_AI_MODEL_DEPLOYMENT=sdogfarm-gpt4o
AZURE_TENANT_ID=sadogfarm.onmicrosoft.com
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_SECRET=your_client_secret_or_key_here

# Configuracion de modelos por agente
MODEL_ANALYST=azure-sdogfarm
MODEL_ARCHITECT=azure-sdogfarm
MODEL_DEVELOPER=azure-sdogfarm
MODEL_TESTER=azure-sdogfarm
MODEL_REVIEWER=azure-sdogfarm
```

Si `AZURE_AI_ENDPOINT` no esta definido o no dispone de conexion externa, la factoria entra de forma automatica en **Modo Mock / Degradado**, permitiendo el desarrollo y ejecucion de tests unitarios locales sin bloqueo operativo.
