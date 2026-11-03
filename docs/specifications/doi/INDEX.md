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
| `P1-A3_Acceptance_Test_Matrix.md` | Pruebas P-01…P-03, N-01…N-04, B-01/B-02, ISO-01, SEC-01…15 | Cerrada (F1) |

## 3. Relación entre documentos
- Threat Model alimenta Requirements (mitigación ↔ prueba) y Acceptance Matrix (verificación).
- Requirements define el contrato que Acceptance prueba.
- Endpoint Matrix define superficie GitHub que API Contract y Acceptance consumen.
- La corrección P1-A (merge REST como permitido técnicamente) se refleja en el Endpoint Matrix y en los requisitos de DOI.

## 4. Copias verificadas
- Los cinco documentos fueron copiados íntegros desde su origen en `SADOCKDOG/LIVESTOCK-MANAGER` (raíz) al directorio `docs/specifications/doi/` del repositorio Factory.
- Verificación por hash SHA-256 (Fase D2-A y correcciones posteriores):
  - `P1-A3_DOI_Requirements.md`: origen == copia → `22E437C99CB832E94FFAE3F5043F43117D911B650CBD25CC7287CC3AE3ADBBE7` == `22E437C99CB832E94FFAE3F5043F43117D911B650CBD25CC7287CC3AE3ADBBE7` (coinciden).
  - `P1-A3_Threat_Model.md`: origen `9B53C0A41A1694CE37CB6FF2D68F076CEBE8800E857D45AFDFD54BABD6EB90F8` ≠ copia `5F0967BCF84883E7B1BF86ABB2148D020F275FB8DBDC93A7CA5A7C79CA57E8D4` (la copia fue corregida en la fase D2-A posterior a la verificación inicial); conflicto registrado, sin modificar el original.
  - `P1-A3_GitHub_Endpoint_Matrix.md`: origen == copia → `16E45F606B22725DB6CF5EE41E9B8F22B2BE8BC32C8B3FC93128F8165894350D` == `16E45F606B22725DB6CF5EE41E9B8F22B2BE8BC32C8B3FC93128F8165894350D` (coinciden).
  - `P1-A3_API_Contract.md`: origen == copia → `BA25D021B1995B86D8EA37B5C261B572C610FB7EFD21F1B719716C3F68A0E1CD` == `BA25D021B1995B86D8EA37B5C261B572C610FB7EFD21F1B719716C3F68A0E1CD` (coinciden).
  - `P1-A3_Acceptance_Test_Matrix.md`: origen `211A4A4F20ADDAEFBDE1F9730051D81256016A1CAECFE9E7B0707FCB89BB596C` ≠ copia `D0BA5CCC55A71FB171E546BBFA89070C712DF423D17243FC5D033A6D3ED59485` (la copia fue corregida en la fase D2-A posterior a la verificación inicial); conflicto registrado, sin modificar el original.

## 5. Referencias
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
- `docs/governance/AUTHORIZATION_POLICY.md`
