# ADR-0002 — Separación App Dev / App Exec

**Estado:** Aprobado (documental). **Fecha:** 2026-11-03 (sesión D2-A).

## Contexto
Un permiso amplio (`contents: write`, `pulls: write`) técnicamente permite integración; separar capacidades evitaba ambigüedad.

## Decisión
App Dev se limita a operaciones de desarrollo; App Exec se reserva para integración validada por propietario.

## Consecuencias
- Intermediario restrictivo.
- Merge solo vía App Exec + FIDO + SHA.

## Referencias
- `docs/architecture/COMPONENTS_AND_IDENTITIES.md`
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
