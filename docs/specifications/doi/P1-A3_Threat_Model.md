# P1-A3 — Threat Model del Dev Operations Intermediary (DOI)

**Fase:** Fase 1 — P1-A3
**Base:** P1-A2 y corrección aceptada con reservas.

## 1. Activos
- Credencial(s) App Dev / IAT.
- Clave privada FIDO propietario.
- Autorizaciones firmadas propietario.
- Integraciones/PRs.
- Branch protection.

## 2. Actores
- Agente (OpenCode/Codex/Claude/DeveloperAgent).
- Servicio DOI.
- Propietario humano (FIDO).
- App Exec.
- Administrador propietario (break-glass).

## 3. Amenazas y mitigaciones

| ID | Amenaza | Mitigación | Prueba |
|----|---|---|---|---|---|
| T-01 | Agente accede a credencial App Dev | Aislamiento (agente sin credencial; DOI custodia) | B-01 |
| T-02 | Agente usa sesión admin SADOCKDOG | No accesible para agentes; break-glass | SEC |
| T-03 | Agente llama GitHub directamente | Canal agent→DOI autenticado; DOI no proxy genérico | B-02 |
| T-04 | Agente ejecuta merge vía App Dev | Merge fuera allowlist; fail-closed | N-01..N-04 |
| T-05 | Agente escribe rama base | Branch protection + restricciones DOI | N-08/SEC-08 |
| T-06 | Bypass intermediario | Fail-closed, deny-by-default | B-xx |
| T-07 | Token expirado/revocado | Valida token/IAT | SEC-12 |
| T-08 | Auditoría insuficiente | Registro sin secretos | P-17/SEC |

## 4. Límites de confianza
- Confianza en agente: baja para operaciones privilegiadas.
- Confianza en DOI: alta (controlado).
- Confianza en FIDO propietario: alta.

## 5. Registro de riesgos y decisiones pendientes
- Riesgo: permisos App Dev (contents/PR write) implican capacidad de merge → mitigación (intermediario + branch protection + App Exec).
- Riesgo: merge-async/GraphQL no verificados documentalmente → decisión pendiente: deny-by-default con verificación futura.
- Riesgo: custodia DPAPI/ACL propuesta no probada → decisión pendiente.

## 6. Estado
Modelo cerrado para P1-A3.
