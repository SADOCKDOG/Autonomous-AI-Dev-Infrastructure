# Política de Autorización — Propietario Único

**Fase:** D2-A (documentación). **Estado:** Documentada.

## 1. Autoridad
- El propietario humano es la única autoridad para aprobar cambios de fase, instalaciones, credenciales, integraciones y operaciones privilegiadas.

## 2. Autorización firmada (F1)
- Payload: versión, authorization_id, signer/key ID, repo, PR, head_sha, base_ref/base_sha, digest, alcance `MERGE`, decisión, fecha UTC, caducidad ≤15 min, nonce.
- Un solo uso (`BEGIN IMMEDIATE`); revocación/expiración/replay/SHA-diff → denegar.
- Para ejecución owner-only: segunda firma FIDO fresca.

## 3. Separación de capacidades
- Propietario → FIDO → App Exec → GitHub (merge validado).
- Propietario → DOI → GitHub (operaciones de desarrollo).
- Agente → DOI (canal local autenticado).

## 4. Alcance y límites
- Operaciones fuera de allowlist → denegar.
- Fail-closed.

## 5. Pendientes operativos
- `OWNER_AUTH_ENABLED`, trust file ACL, firma FIDO, check `Owner authorization`, branch protection, DOI implementación, instalación App Dev, activación.

## 6. Referencias
- `docs/OWNER_AUTHORIZATION.md`
- `docs/architecture/TRUST_BOUNDARIES.md`
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
