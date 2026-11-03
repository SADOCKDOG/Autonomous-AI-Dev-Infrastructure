# Componentes y Separación de Identidades — Software Factory

**Fase:** D2-A (documentación). **Estado:** Documentado.

## 1. Identidades reconocidas

| Identidad | Tipo | Responsabilidad | Credenciales / Secretos |
|---|---|---|---|
| Propietario humano | Humana | Autoridad máxima; firma FIDO2/OpenSSH + SSHSIG; decisiones de integración | Llave FIDO2/OpenSSH física (ed25519-sk, verify-required); no generada por el sistema |
| Agente de desarrollo | Proceso IA (OpenCode/Codex/Claude/DeveloperAgent) | Desarrollo/preparación; nunca ejecuta integración privilegiada | Sin credencial App Dev; acceso solo al canal DOI |
| Dev Operations Intermediary (DOI) | Servicio local | Ejecuta operaciones permitidas (allowlist) | Token IAT / instalación App Dev; clave de custodia protegida; ACL; auditoría |
| App Dev | GitHub App (técnica) | Identidad de desarrollo; capacidades contents/PRs | Instalación, JWT/IAT; custodia protegida |
| App Exec | GitHub App (técnica) | Executor de integración (merge validado) | Token IAT; requiere autorización FIDO + SHA |
| Admin propietario | Cuenta humana (SADOCKDOG) | Break-glass | No para agentes |

## 2. Separación exigida

- El agente **no** posee credencial App Dev.
- El DOI posee la capacidad de operación y la valida.
- El propietario es la única autoridad de integración privilegiada.
- App Dev y App Exec son identidades distintas y separadas; la integración requiere App Exec con autorización propia.

## 3. Responsabilidades por capacidad

| Capacidad | Propietario | DOI | App Dev | App Exec | Agente |
|---|---|---|---|---|---|
| Preparación rama dev / push / PR | No (delegada al DOI) | Sí (allowlist) | Custodia | No | Canal → DOI |
| Merge / integración | **Sí** (FIDO) | No | No | Sí (validación FIDO+SHA) | Prohibido |

## 4. Referencias
- `docs/security/OWNER_AUTHORIZATION.md`
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
- `docs/architecture/TRUST_BOUNDARIES.md`
