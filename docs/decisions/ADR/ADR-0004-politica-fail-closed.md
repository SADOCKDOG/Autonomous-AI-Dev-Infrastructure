# ADR-0004 — Política fail-closed en integración

**Estado:** Aprobado (documental). **Fecha:** 2026-11-03 (sesión D2-A).

## Contexto
Ante fallos de validación/autorización no existía postura clara.

## Decisión
Toda capacidad no validada o fuera de allowlist → denegación. Sin fallback de integración.

## Consecuencias
- DONE solo tras merge confirmado.
- `MERGE_UNKNOWN` terminal.

## Referencias
- `docs/governance/AUTHORIZATION_POLICY.md`
