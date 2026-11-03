# P1-A3 — Acceptance Test Matrix del Dev Operations Intermediary

**Fase:** Fase 1 — P1-A3
**Base:** P1-A2, informe correctivo P1-A, evaluación propietario.

**Nota de diseño:** los resultados esperados («Permitido», «Denegado», «Fail-closed») son resultados esperados derivados del diseño y de los requisitos (P1-A2/P1-A3). No constituyen resultados de pruebas ejecutadas. Estado de la fase: **Sin implementación**.

## 1. Criterios de aceptación de P1-A3 → pruebas

| Criterio de aceptación P1-A3 | Prueba asociada | Tipo | Resultado esperado |
|---|---|---|---|
| Ningún requisito crítico solo prohibición operativa | REQ-DOI-002/003 + matriz | Design/test | Denegar por default |
| Cada amenaza tiene mitigación + prueba | T-01..T-08 | Threat→test | Denegar/fail-closed |
| App Dev no puede integrar | N-01..N-04, SEC-05..07 | Negative/bypass | Denegado |
| App Dev no puede escribir rama protegida | SEC-08, REQ-DOI-008 | Isolation/neg | Denegado |
| No existe camino alternativo a credenciales | SEC-01/02/03/04/16 | Isolation/bypass | Denegado |
| Fallos → denegar, nunca permitir | SEC-11 | Fail-closed | Denegar |

## 2. Pruebas positivas

| ID | Prueba | Resultado |
|---|---|---|
| P-01 | Crear rama dev + push | Permitido |
| P-02 | Crear/actualizar PR | Permitido |
| P-03 | Consultar checks | Permitido |

## 3. Pruebas negativas / bypass / aislamiento

| ID | Prueba | Resultado |
|---|---|---|
| N-01 | Merge REST | Denegado |
| N-02 | Merge async | Denegado (design) |
| N-03 | GraphQL merge | Denegado (design) |
| N-04 | `gh pr merge` | Denegado |
| B-01 | Agente sin credencial App Dev | Fail-closed |
| B-02 | Bypass intermediario | Fail-closed |
| ISO-01 | Aislamiento DOI vs agente | Denegar acceso |
| SEC-01..15 | Seguridad (Fase 3) | Denegado / denegar |

## 4. Estado

Entregable de cierre de requisitos. Sin implementación.
