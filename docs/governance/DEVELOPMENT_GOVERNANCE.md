# Gobernanza del Desarrollo Autónomo — Software Factory

**Fase:** D2-A (documentación). **Estado:** Documentada (basada en diseño previo).

## 1. Principios rectores
1. Soberanía y control local.
2. Abstracción del proveedor de inferencia.
3. Fronteras y clasificación de datos.
4. Aislamiento físico por tarea.
5. Sandbox con lista de permisos.
6. Barrera de aprobación humana.

## 2. Ciclo de vida de una tarea
- Transiciones formales: `BACKLOG → READY → PLANNING → IN_PROGRESS → TESTING → REVIEW → DONE`.

## 3. Aprobación humana
- Ningún agente autónomo ejecuta `git merge`, `git push`, transición a `DONE` sin aprobación humana auditada.

## 4. Evidencia y PR
- Cambios en worktree aislado; revisión de diff; secret scanning; QA.

## 5. Estado actual
- Barrera de aprobación implementada en código local (F2 owner auth).
- Puerta de integración operativa pendiente (Fase 4: branch protection + checks + DOI).

## 6. Referencias
- `docs/OWNER_AUTHORIZATION.md`
- `docs/governance/AUTHORIZATION_POLICY.md`
- `docs/governance/PHASE_HISTORY.md`
