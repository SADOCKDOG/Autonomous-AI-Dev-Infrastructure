# Autorización de integración de propietario único

## Estado de la documentación y de la implementación

| Fase / Entrega | Contenido | Estado |
|---|---|---|
| F1 | Diseño aprobado documentalmente: FIDO2/OpenSSH (ed25519-sk, `verify-required`, flags `UP`/`UV`), payload canónico (versión, `authorization_id`, signer/key ID, repo, PR, `head_sha`, base, digest, alcance `MERGE`, decisión, fecha UTC, caducidad ≤15 min, nonce), un solo uso (`BEGIN IMMEDIATE`), segundo factor para ejecución owner-only, `MergeExecutor` separado. | **Aprobado (documental)** |
| F2 | Implementación local en repositorios Factory/Console: flujo fail-closed; `OWNER_AUTH_ENABLED=false`; sin handle FIDO; sin executor; sin check GitHub; sin branch protection. | **Local. No operativo** |
| F3–F5 | Validaciones; check `Owner authorization`; branch protection; instalación App Dev (P1-B no autorizado); activación. | **Pendiente** |

**Distinción obligatoria:** la existencia de código local **no equivale** a una autorización operativa, a un sistema validado o a una capacidad disponible en producción. La documentación debe mantener esta distinción.

## Firma del propietario

- La clave privada debe permanecer en una llave FIDO2/OpenSSH compatible; el archivo `OWNER_AUTH_FIDO_KEY_HANDLE` es solo el handle OpenSSH y no contiene la clave privada.
- El alta debe ser manual por el propietario sobre una llave física, generada con verificación de usuario obligatoria (por ejemplo OpenSSH `ed25519-sk` con `verify-required`). El código no genera, importa, exporta ni copia ninguna clave.
- No se generó la llave en Fase 2. El broker Python todavía vive en los repositorios locales y ejecuta bajo la cuenta interactiva actual; antes de tratarlo como trusted, Fase 4 debe instalar/proteger el signer fuera de árboles escribibles por agentes y verificar ACL/código firmado.
- La clave se debe registrar con verificación de usuario obligatoria (PIN/UV). El verificador inspecciona la firma SSHSIG y rechaza firmas sin flags de presencia (`UP`) y verificación (`UV`).
- El Console muestra repo, PR, HEAD/base SHA, alcance y diff disponible; exige escribir el sufijo del SHA. Un broker visible muestra además el payload canónico exacto antes de invocar `ssh-keygen`. La firma se valida contra el hash canónico servido por el backend.
- El archivo público `allowed_signers` no es secreto, pero debe instalarse bajo `ProgramData/SdogFarm/OwnerAuthorization` con ACL de escritura limitada al propietario/instalador confiable. El backend rechaza un trust file ubicado dentro de los repositorios.
- Configuración mínima pendiente para activación: `OWNER_AUTH_ENABLED`, `OWNER_AUTH_ALLOWED_SIGNERS_PATH`, `OWNER_AUTH_REPOSITORIES`, `OWNER_AUTH_SIGNER_IDENTITY`, `OWNER_AUTH_SIGNER_KEY_ID`, `OWNER_AUTH_GITHUB_LOGIN`, `OWNER_AUTH_CHECK_APP_ID`, `OWNER_AUTH_REQUIRED_CHECK_CONTEXTS`, `OWNER_AUTH_REQUIRED_CHECK_APP_IDS_JSON` y `OWNER_AUTH_CHECK_GROUPS_JSON`. Los grupos `product_tests`, `analysis` y `codeql` son obligatorios. No incluir material privado en `.env`, SQLite, repositorios, GitHub Actions Secrets accesibles a agentes o prompts.

## Protocolo y estado

El payload firmado contiene versión, `authorization_id`, signer/key ID, repo, PR, `head_sha`, base_ref/base_sha, digest del manifiesto de archivos, alcance `MERGE`, decisión, fecha UTC, caducidad de hasta 15 minutos y nonce único. El alcance puede autorizar al propietario a ejecutar interactivamente o delegar expresamente el merge de esa PR al agente.

El registro es de un solo uso. `BEGIN IMMEDIATE` reclama atómicamente la autorización; revocación, expiración, cambios de SHA/diff, replay o concurrencia impiden continuar. Para ejecución owner-only se exige una segunda firma FIDO fresca. El merge requiere un `MergeExecutor` separado y usa SHA HEAD como precondición; no llama `gh pr merge`, no usa `--admin` ni fallback. No existe todavía una implementación/configuración GitHub App para ese executor, así que el merge se rechaza sin consumir la autorización. Un resultado remoto incierto queda terminal `MERGE_UNKNOWN` para reconciliación humana; no se reintenta con la misma autorización.

El estado `DONE` se asigna únicamente después de que GitHub confirme el merge y se almacena el `merge_sha`. No se sincronizan repositorios ni se borran worktrees, ramas o evidencias.

## GitHub y límites de activación

Branch Protection debe seguir exigiendo PR, enforce admins, bloqueo de force-push/borrado y cero approvals de terceros. Debe requerir contextos estables para tests de producto, análisis, CodeQL y `Owner authorization`; todos deben estar vinculados a GitHub App IDs de confianza. El servicio falla cerrado ante checks ausentes, desconocidos, pendientes o no satisfactorios, y ante rulesets activos que aún no pueda verificar íntegramentamente.

La autorización firmada no sustituye la separación de credenciales: la CLI `gh` actualmente autenticada como propietario no distingue propietario de agente. Antes de activar, los agentes deben dejar de disponer de una credencial con permisos de merge directo. La bandera `allow_agent_execution` expresa delegación del propietario, pero todavía no está enlazada a una GitHub App/identidad de agente distinta; no debe activarse hasta que lo esté.

Un workflow confiable de GitHub que emita el check `Owner authorization` y un `MergeExecutor` respaldado por una GitHub App aún no están implementados. También quedan pendientes el aislamiento de credenciales de merge, las ACL reales del trust file, el alta de la llave FIDO y la validación del flujo en un repositorio de prueba. No se deben abrir los gates de producción hasta completarlos.

## Consolidación D2-A

- Documento consolidado en `docs/OWNER_AUTHORIZATION.md` durante la fase D2-A (consolidación documental del repositorio Factory).
- Se mantiene la distinción estricta entre: **diseño aprobado**, **implementación local existente**, **pruebas ejecutadas**, **validaciones pendientes**, **capacidades no disponibles en producción** y **decisiones que requieren autorización posterior**.
- No se presentó como implementado ni validado aquello que solo existió como diseño, código local o propuesta.
- No se incluyeron secretos, tokens ni datos sensibles.
