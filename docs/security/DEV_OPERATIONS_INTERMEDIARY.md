# Dev Operations Intermediary (DOI) — Especificación Consolidada

**Fase:** D2-A (documentación) — consolidación de P1-A, corrección P1-A, P1-A2 y P1-A3.
**Estado:** Documental / diseñada. No implementado operativamente.

## 1. Contexto y linaje
1. **P1-A (diseño):** App Dev con `contents: Read & write` y `pull_requests: Read & write`; operativamente prohibido el merge.
2. **Informe correctivo P1-A (aceptado con reservas):** el bloqueo operativo del merge no equivale a bloqueo técnico; el endpoint merge queda alcanzable con `pulls: write`. Corrección: Dev Operations Intermediary con allowlist positiva.
3. **P1-A2 (especificación técnica):** DOI con API local de operaciones permitidas, allowlist, validación de contexto, custodia, auditoría, recuperación.
4. **P1-A3 (cierre de requisitos):** requisitos REQ-DOI-*, amenazas T-*, endpoints G-*, contrato API, matriz de aceptación.

## 2. Arquitectura
- Agente → (canal local autenticado) → DOI → GitHub.
- DOI: allowlist + validación (repo/contexto/SHA/PR) + fail-closed; custodia credenciales; auditoría; sin proxy genérico.

## 3. Operaciones permitidas (allowlist, diseño)
- Lectura: branches, commits, contents, PRs, checks, diffs.
- Escritura controlada: creación rama dev, push (contents), creación PR, actualización PR.

## 4. Operaciones prohibidas (deben permanecer fuera de la superficie operativa del DOI)
- `PUT /repos/{o}/{r}/pulls/{n}/merge` — prohibido (corregido).
- `PUT /repos/{o}/{r}/pulls/{n}/merge-async` — prohibido por diseño (pendiente verificación documental).
- Mutación GraphQL `mergePullRequest` — prohibida por diseño (pendiente verificación documental).
- `gh pr merge` — fuera de alcance del DOI (agente) → denegado.
- Operaciones administrativas, secrets, etc.

## 5. Validación y fail-closed
- Revalidación repo/contexto/SHA/PR por operación.
- Negativos: cualquier operación no en allowlist → denegada.
- Ausencia de DOI/allowlist/token → denegación.

## 6. Custodia
- Clave privada, JWT/IAT, DPAPI/ACL, aislamiento memoria/args/env/temporales: diseñado; DPAPI/ACL propuestos, no validados operativamente.

## 7. Riesgos residuales y decisiones pendientes
- `contents: write` (riesgo residual) → mitigación: branch protection + restricciones.
- merge-async/GraphQL: pendiente verificación → deny-by-default.
- Custodia DPAPI/ACL: no probada → pendiente.
- Recuperación: incompleta en P1-A → pendiente.

## 8. Referencias
- `docs/specifications/doi/INDEX.md`
- `docs/specifications/doi/P1-A3_*.md`
- `docs/security/OWNER_AUTHORIZATION.md`
