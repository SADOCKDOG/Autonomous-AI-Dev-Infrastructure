# Índice de la Serie P1-A3 — Dev Operations Intermediary (DOI)

**Fase:** F1 — P1-A3; Fase D2-A (incorporación a la fuente de verdad documental).
**Estado:** Documental (Cerrada como requisitos). No implica implementación.

## 1. Propósito
Indexar y relacionar la serie documental del DOI:
- P1-A — Diseño inicial del intermediario.
- P1-A — Corrección aceptada con reservas (merge ≠ bloqueo de integración).
- P1-A2 — Especificación técnica del DOI.
- P1-A3 — Requisitos y matriz de aceptación.

## 2. Documentos de la serie

| Documento | Contenido | Estado |
|---|---|---|
| `P1-A3_DOI_Requirements.md` | Requisitos técnicos REQ-DOI-001…010 + criterios de aceptación | Cerrada (F1) |
| `P1-A3_Threat_Model.md` | Modelo de amenazas T-01…T-08, límites de confianza, riesgos | Cerrado (F1) |
| `P1-A3_GitHub_Endpoint_Matrix.md` | Matriz G-01…G-12 (permitidos/denegados; merge REST corrigido; async/GraphQL pendientes) | Cerrada (F1) |
| `P1-A3_API_Contract.md` | Contrato API local del DOI (identidad, authz, repo, ramas, validación, límites, fail-closed) | Cerrada (F1) |
| `P1-A3_Acceptance_Test_Matrix.md` | Pruebas P-01…P-03, N-01…N-05, B-01/B-02, ISO-01, SEC-01…15 | Cerrada (F1) |

## 3. Relación entre documentos
- Threat Model alimenta Requirements (mitigación ↔ prueba) y Acceptance Matrix (verificación).
- Requirements define el contrato que Acceptance prueba.
- Endpoint Matrix define superficie GitHub que API Contract y Acceptance consumen.
- La corrección P1-A (merge REST como permitido técnicamente) se refleja en el Endpoint Matrix y en los requisitos de DOI.

## 4. Copias verificadas
- Los cinco documentos fueron copiados íntegros desde su origen en `SADOCKDOG/LIVESTOCK-MANAGER` (raíz) al directorio `docs/specifications/doi/` del repositorio Factory, sin modificar contenido.
- Verificación por hash SHA-256 (Fase D2-A): origen == copia (sin diferencias registradas).

## 5. Referencias
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
- `docs/governance/AUTHORIZATION_POLICY.md`
