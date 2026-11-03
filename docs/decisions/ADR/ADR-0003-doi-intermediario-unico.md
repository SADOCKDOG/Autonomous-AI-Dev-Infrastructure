# ADR-0003 — El DOI es el único intermediario de operaciones Dev

**Estado:** Aprobado (documental). **Fecha:** 2026-11-03 (sesión D2-A).

## Contexto
Bloquear `PUT /merge` no garantiza bloqueo de integración; se requería frontera de operaciones.

## Decisión
Toda operación Dev de agente pasa por DOI con allowlist positiva, validación de contexto y fail-closed.

## Consecuencias
- No se ofrece proxy HTTP genérico.
- Agente sin credencial App Dev; sin ruta alternativa.

## Referencias
- `docs/security/DEV_OPERATIONS_INTERMEDIARY.md`
- `docs/specifications/doi/INDEX.md`
