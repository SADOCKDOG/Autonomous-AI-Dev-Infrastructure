# ADR-0001 — Autoridad única del propietario

**Estado:** Aprobado como decisión de diseño (documental). **Fecha:** 2026-11-03 (sesión D2-A).

**Alcance:** formalización documental de la decisión de diseño; no constituye validación operativa ni autorización del propietario para activación.

## Contexto
La autorización de integración y operaciones privilegiadas debía concentrarse en una sola fuente de decisión humana.

## Decisión
El propietario humano es la única autoridad; las capacidades técnicas (DOI/App Dev/App Exec) actúan bajo validación firmada.

## Consecuencias
- Fail-closed.
- Sin fallback de integración.
- Pendiente activación operativa (Fase 5 / Fase 4).

## Referencias
- `docs/governance/AUTHORIZATION_POLICY.md`
