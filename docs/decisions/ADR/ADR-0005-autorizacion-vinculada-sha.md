# ADR-0005 — Autorización vinculada a SHA exacto

**Estado:** Aprobado (documental). **Fecha:** 2026-11-03 (sesión D2-A).

## Contexto
Autorizaciones amplias eran riesgosas.

## Decisión
Autorización ligada a repo, PR, head/base SHA, alcance y diff; revalidación inmediata; consumo atómico; replay protection.

## Consecuencias
- Autorización por operación; segunda firma para owner-only.

## Referencias
- `docs/security/OWNER_AUTHORIZATION.md`
- `docs/governance/AUTHORIZATION_POLICY.md`
