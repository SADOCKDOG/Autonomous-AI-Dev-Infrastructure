# Límites de Confianza — Software Factory

**Proyecto:** Autonomous AI Software Factory
**Fase:** D2-A (documentación) — sobre bases F1/P1-A3 y diseño DOI
**Estado:** Documentado (D2-A). No implica implementación operativa.

## 1. Objetivo

Establecer, de forma explícita y auditable, los límites de confianza que rigen la interacción entre el agente de desarrollo, el intermediario de operaciones Dev (DOI), el propietario (humano/FIDO) y el executor de integración (App Exec).

## 2. Actores y niveles de confianza

| Actor | Rol | Nivel de confianza | Base de decisión |
|---|---|---|---|
| Propietario humano | Autoridad máxima | Alta | FIDO2/OpenSSH con verificación de usuario (UV) + SSHSIG |
| Agente de desarrollo | Ejecución de trabajo | **Baja** para operaciones privilegiadas | Canal local → DOI; sin credencial App Dev |
| Dev Operations Intermediary (DOI) | Ejecución de operaciones permitidas | Alta (controlado) | Allowlist positiva, validación de contexto, fail-closed |
| App Dev | Identidad técnica GitHub | Media/Alta (técnicamente capaz) | Custodia protegida; nunca accesible directamente al agente |
| App Exec | Executor de integración | Alta | Requiere autorización FIDO fresca + SHA exacto + segundo factor |
| Admin propietario (break-glass) | Emergencia | Muy alta | No para agentes; separado de las demás identidades |

## 3. Fronteras

### 3.1 Propietario → Integración (App Exec → GitHub)
- La única ruta que permite merge/integración.
- Requiere: firma FIDO del propietario, payload canónico (repo/PR/head/base/SHA/diff/alcance), registro de un solo uso, caducidad, segundo factor para ejecución owner-only, validación de SHA HEAD previo, `merge_sha` post-merge.
- No existe fallback: sin autorización válida → denegar.

### 3.2 Propietario → DOI (operaciones de desarrollo)
- El propietario autoriza operaciones de preparación (rama dev, push, PR) vía DOI.
- El DOI ejecuta con allowlist y token IAT; nunca emite merge.

### 3.3 Agente → DOI
- Canal local autenticado.
- El agente no posee credencial App Dev; no accede a llave privada, tokens IAT, ni sesión admin.
- El DOI no ofrece proxy HTTP genérico: API específica con allowlist.

### 3.4 Admin propietario (break-glass)
- No confiable para agentes; uso excepcional humano.

## 4. Política fail-closed
- Ausencia de intermediario / allowlist / token → denegación.
- Cualquier operación fuera de allowlist → denegación.
- Fallos en validación → denegación.

## 5. Referencias
- `docs/security/OWNER_AUTHORIZATION.md`
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
- `docs/specifications/doi/…`
- `docs/governance/AUTHORIZATION_POLICY.md`
- `SECURITY.md`
