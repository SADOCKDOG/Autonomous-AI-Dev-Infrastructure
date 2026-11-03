# P1-A3 — GitHub Endpoint Matrix del Dev Operations Intermediary

**Fase:** Fase 1 — P1-A3
**Base:** P1-A2, informe correctivo y evaluación propietario.

## 1. Matriz de endpoints GitHub

| ID | Método + Ruta | Operación | Permitido para DOI/App Dev | Permiso requerido | Estado |
|----|---|---|---|---|---|
| G-01 | GET /repos/{o}/{r}/branches | Listar ramas | Permitido | contents/read | Diseñado |
| G-02 | GET /repos/{o}/{r}/commits/{ref} | Commit | Permitido | contents/read | Diseñado |
| G-03 | GET /repos/{o}/{r}/contents/{path} | Contenido | Permitido | contents/read | Diseñado |
| G-04 | POST /repos/{o}/{r}/git/refs | Crear ref (rama dev) | Permitido | contents/write | Diseñado |
| G-05 | PUT /repos/{o}/{r}/contents/{path} | Subir contenido | Permitido | contents/write | Diseñado |
| G-06 | GET /repos/{o}/{r}/pulls | PRs | Permitido | pulls/read | Diseñado |
| G-07 | POST /repos/{o}/{r}/pulls | Crear PR | Permitido | pulls/write | Diseñado |
| G-08 | GET /repos/{o}/{r}/commits/{ref}/check-runs | Checks | Permitido | checks/read | Diseñado |
| G-09 | PUT /repos/{o}/{r}/pulls/{n}/merge | **Merge (prohibido)** | **Denegado** | pulls/write (no asignado a DOI) | **Corregido** |
| G-10 | PUT /repos/{o}/{r}/pulls/{n}/merge-async | **Merge async (prohibido)** | **Denegado** | pulls/write (no asignado) | **Pendiente verificación** |
| G-11 | GraphQL mergePullRequest | **Merge (prohibido)** | **Denegado** | pull_requests (diseño) | **Pendiente verificación** |
| G-12 | PUT branch protection / Rulesets | Denegado | administration/none | Denegado |

## 2. Operaciones Git directas y comandos gh

- Push de rama dev vía API (refs/contents): permitido para DOI/App Dev.
- `gh pr merge`: fuera del alcance del DOI (agente) → denegado/fail-closed.
- Merge local de rama → push a base: fuera de allowlist → denegado.

## 3. Estado

- Merge REST: Correcto (denegado).
- Merge async: Pendiente verificación documental; denegado por diseño.
- GraphQL: Pendiente verificación; denegado por diseño.
- `gh pr merge`: Correcto (fuera de alcance).
