# ADR-0005 — Autorización vinculada a SHA exacto

**Estado:** Aprobado como decisión de diseño (documental). **Fecha:** 2026-11-03 (sesión D2-A).

**Alcance:** formalización documental de la decisión de diseño; no constituye validación operativa ni autorización del propietario para activación.

## Contexto
Autorizaciones amplias eran riesgosas.

## Decisión
Autorización ligada a repo, PR, head/base SHA, alcance y diff; revalidación inmediata; consumo atómico; replay protection.

## Consecuencias
- Autorización por operación; segunda firma para owner-only.

## Referencias
- `docs/OWNER_AUTHORIZATION.md`
- `docs/governance/AUTHORIZATION_POLICY.md`
