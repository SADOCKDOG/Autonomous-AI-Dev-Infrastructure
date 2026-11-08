# Owner Authorization — recuperación y auditoría estática

- **Fecha:** 2026-11-08
- **Estado:** informe local, sin commit ni publicación
- **Base documental:** `dfb8083bc2e027ba18c401d9829854b473508f66` (merge D2-A, PR #3)
- **Rama de informe:** `docs/owner-auth-recovery-audit-2026-11-08`

## 1. Alcance y método

Este documento consolida la recuperación del prototipo Owner Authorization y una inspección estática de los clones Factory y Console recuperados. Se inspeccionaron HEAD, estado Git, manifiestos y rutas críticas de autorización, merge, persistencia, firma y UI. **No se modificó código, no se ejecutaron pruebas, no se creó commit ni se hizo push.** No se leyeron `.env`, valores de configuración efectivos, bases de datos ni material de credenciales.

La auditoría solo evalúa lo observado en el código local. La existencia de un módulo o una prueba no demuestra despliegue, aprobación, validación operativa o disponibilidad en producción.

## 2. Evidencia de recuperación

Los repositorios recuperados son copias locales detached; no son ramas publicadas:

| Repositorio | HEAD | Padre | Estado observado |
|---|---|---|---|
| Factory | `0199deeba11757077c96885029a948105b0b466f` | `dfb8083bc2e027ba18c401d9829854b473508f66` | 8 archivos modificados sin commit: 6 Owner Authorization y 2 del piloto ganadero. |
| Console | `6e65f0a8e39ebbd282e540041c487cdc9f5e0bdd` | `156fdd06f2ba4f55a6a1ca18986749659686b690` | Árbol de trabajo limpio. |

Los archivos modificados del piloto son `scripts/simulate_livestock_pilot.py` y `tests/integration/test_pilot_livestock_manager.py`. Se conservaron intactos y **quedan fuera de cualquier entrega Owner Authorization**.

### Paquetes e integridad

- Archivo de referencia `COPIA DE LAS 2 y 19`: manifiesto sellado, 1.873/1.873 entradas verificadas; SHA-256 del manifiesto `072F60691737E07E9DFC8ADD5137713941C55085540B0820288F28B11810B3D2`.
- Copias de trabajo recuperadas: 294/294 entradas verificadas; SHA-256 del manifiesto `B5FFA7024421A3BA55E2FA92EFFA8CAEB3766096A515EBC1657DB0026E7601FF`.
- Rescate del 2026-11-06: 39/39 entradas; SHA-256 del manifiesto `C288F8EE15705FDE0BF8950EEDFFDFA16CF7FCD4AE7A5202EE850EAB305C86D3`.
- Los 12 archivos supervivientes y los 13 vectores del rescate coinciden byte por byte con la referencia. La referencia conserva además los clones Git completos y el resto de la implementación.
- `owner-auth-copy-manifest.json` (SHA-256 `90CFA235720B8D0EDDF36B1E7A312D64A8AF24CA7C5947CE69D85B140F9B0C2A`) registra una etapa anterior del overlay: 8/25 hashes coinciden con el árbol actual y 17/25 difieren tras las tandas posteriores. No es un manifiesto de hash del estado final.
- `COPIA DE LAS 2 y 15` y `COPIA DE LAS 2 y 19` coinciden en HEAD y estado de código observado, pero difieren en los dos `.git/index`; no son idénticas byte por byte.
- La ruta archivística profunda ocasiona `Filename too long` al ejecutar algunas operaciones Git en Windows. Las copias de trabajo están en una ruta corta bajo `C:\Users\yo\repo`; sus objetos de commit son legibles. No usar `%TEMP%` como espacio de trabajo.

## 3. Hallazgos estáticos

**Convención de evidencia:** las rutas y líneas siguientes son relativas a los clones Owner Auth recuperados (`Factory`, HEAD `0199deeb…`; `Console`, HEAD `6e65f0a8…`), no al árbol base de este informe (`dfb8083…`). Los SHA-256 de los archivos auditados están en la tabla “Referencias de código” al final de esta sección; el manifiesto de copias de trabajo tiene SHA-256 `B5FFA7024421A3BA55E2FA92EFFA8CAEB3766096A515EBC1657DB0026E7601FF`.

### H1 — Bloqueo operativo: Owner Authorization continúa desactivado

`Factory/src/software_factory/settings.py:31–49`: `OWNER_AUTH_ENABLED` vale `false` por defecto; token, allowlist y App no están provisionados ni validados en este expediente. Es fail-closed, pero significa que el flujo no está operativo.

### H2 — Alto: el control de ACL no acredita aislamiento de credenciales

`Factory/src/software_factory/git/github_pr.py:55–75`, `Factory/src/software_factory/api/owner_authorization.py:30–48` y `Console/console/owner_auth_client.py:24–41`: la comprobación `os.access(..., W_OK)` consulta los derechos efectivos del proceso; no demuestra que los agentes u otros principales no puedan leer o modificar los secretos ni valida ACL por principal.

`Factory/src/software_factory/git/github_pr.py:78–131`: el executor valida el formato y envía el token, pero no comprueba identidad de instalación/App, repositorio de instalación ni permisos mínimos. No se verificaron una GitHub App instalada, principal separado, DPAPI ni ACL real. Antes de activación se requiere una frontera de custodia independiente y verificable.

### H3 — Medio: vista previa no usa el App ID de protección

`Factory/src/software_factory/api/owner_authorization.py:147–159` crea `GitHubPRClient` con `owner_auth_check_app_id`, pero `Factory/src/software_factory/api/owner_authorization.py:172–180` crea otro cliente sin ese argumento. `Factory/src/software_factory/git/github_pr.py:384–404` exige el App ID para declarar válida la protección. La vista previa puede mostrar un estado falso; el servicio de preparación revalida en backend, por lo que el hallazgo es de vista/flujo, no evidencia de bypass. Requiere prueba de regresión antes de corregir.

### H4 — Alto: inicialización de SQLite oculta fallos y no hay migraciones versionadas

`Factory/src/software_factory/persistence/database.py:115–130` suprime cualquier `sqlite3.OperationalError`, incluso fallos distintos de “ya inicializada” o bloqueo. No hay versión de esquema ni migración explícita. Debe fallar cerrado si el esquema requerido no queda instalado y migrar bases anteriores antes de activar Owner Authorization.

### H5 — Medio: resolución de base de datos compartida no confirmada

`Factory/src/software_factory/settings.py:77–86` resuelve SQLite desde Factory. `Console/console/config.py:46–72` busca `FACTORY_DB_PATH`, `settings.json`, una ruta adyacente llamada `AutonomousDev` o su DB local. En los clones aislados con nombres/rutas diferentes, los valores por defecto pueden seleccionar bases distintas. No se leyó configuración efectiva ni se verificó una base compartida.

### H6 — Medio: estado `MERGE_UNKNOWN` es seguro pero puede quedar sin resolución

`Factory/src/software_factory/orchestration/owner_authorization.py:705–783` no reintenta el PUT y solo consume la autorización si una lectura fresca de GitHub confirma el merge del HEAD firmado. Si la PR sigue abierta o cerrada sin merge, permanece bloqueada; no hay una resolución auditada para ese caso. Es un freno seguro, pero requiere runbook y mecanismo de resolución autorizada antes de uso operativo.

### H7 — Medio: validación ECDSA sintética; no hay evidencia FIDO real

`Factory/src/software_factory/security/owner_authorization.py:264–321` exige algoritmo FIDO y flags UP/UV, pero `Factory/tests/unit/test_owner_signature_format.py:16–35` construye bytes sintéticos y no acredita verificación OpenSSH/FIDO real. `ssh-keygen -Y verify`, hardware FIDO y presencia/verificación de usuario no se validaron en esta ronda.

### H8 — Medio: GitHub CLI sigue siendo la fuente de lectura

`Factory/src/software_factory/git/github_pr.py:200–260` usa `gh api` para leer PR, permisos, protección y checks. El merge usa un executor separado, lo cual es positivo, pero la identidad/credencial que ejecuta `gh` no está aislada ni validada aquí. No compartir una sesión administrativa con agentes; definir una identidad de lectura de mínimo privilegio o un intermediario protegido.

### Referencias de código y SHA-256

Los archivos siguientes pertenecen a los clones de evidencia separados; no están presentes en el commit base de este informe. SHA-256 fijado al estado auditado:

| Repo / ruta relativa | SHA-256 |
|---|---|
| Factory `src/software_factory/settings.py` | `DA3B99EA21FC94EB69CC59EF006292DD54F15154D050BFF0D642457B3425B6CD` |
| Factory `src/software_factory/git/github_pr.py` | `C29F7E3DDEA8C692174C75581C9501501DA132375D0C7772484B799EFA765228` |
| Factory `src/software_factory/api/owner_authorization.py` | `AF9A3AA35A732BD08A15526228E827E48DCA83A65AD131F44DF189E7D6A6A21C` |
| Factory `src/software_factory/orchestration/owner_authorization.py` | `81F84ECEFDB94C1AC0A21553764D0B4BB0D676AF951A99A7AD745EE3EACD80A6` |
| Factory `src/software_factory/security/owner_authorization.py` | `D168631A96EF825305FE1DFBDCBF6CCF142351D21B8FA19E4E72D624D104D3FE` |
| Factory `src/software_factory/persistence/database.py` | `DE266AA63DE123A12327EEBB93411DFED4109E929BC1A39B5056758AF0239901` |
| Factory `src/software_factory/api/kanban.py` | `767BF00EFA1041DF54B04F2ABE22D6E95E7739BE6586D3DD3B377D8B05C8A81F` |
| Factory `src/software_factory/kanban/service.py` | `50CD06218B5DEF863B5AEDE7DAB4DA59F4B8DB713D03B343DFAB91147F364050` |
| Factory `tests/unit/test_owner_signature_format.py` | `86FAA706AC1C6F73CA0D038EA9F9317C459D471CEC145AFF50276EAEDA93CA4C` |
| Console `console/app.py` | `7CF8029CDBA19CB15095E2DBDF81C6FB8623C18BB8488DB0CF79878BD44A7CF7` |
| Console `console/config.py` | `A3523C5050F0B4B6B3650422C10FEE129B26154668D751D26A9CD3EC4B3474F1` |
| Console `console/owner_auth_client.py` | `9E417493AD57F80F1B21A288370F3F13BB86E300DF2C2046EDA22155B6D4A40A` |

## 4. Controles locales positivos observados

Las siguientes referencias corresponden a los clones de evidencia descritos en §3 y se identifican por la tabla de SHA-256; no son enlaces al commit base de este informe.

- Factory `src/software_factory/orchestration/owner_authorization.py:101–212`: exige allowlist de repositorios, firma, SHA/base/diff y checks configurados antes de autorizar.
- Factory `src/software_factory/git/github_pr.py:342–404`: reglas de rulesets no evaluables fallan cerradas. En `:92–131`, el merge exige SHA y el código no usa `--admin` ni limpieza local.
- Factory `src/software_factory/kanban/service.py:112–120`: bloquea la transición Kanban ordinaria a `DONE`. En `src/software_factory/api/kanban.py:74–80`, el endpoint sin firma devuelve 410. En `src/software_factory/orchestration/owner_authorization.py:545–598`, `DONE` se registra solo tras confirmación de merge y se documenta si la tarea cambió de estado.
- El código recuperado de Console (`console/app.py:2267–2349`) dirige la promoción por Owner Authorization y rechaza `skip_confirm=True`; no se encontraron en sus archivos Python las rutas `gh pr merge --admin`, `reset --hard` o limpieza de worktrees. Esta copia es local y no está integrada en la Console publicada.

## 5. Pruebas, integración y estados externos

- **No se ejecutaron tests** en esta auditoría. La cifra histórica `55 passed` permanece **declarada, no verificada**.
- Las pruebas existentes usan mocks/simulaciones; no prueban GitHub App instalada, permisos reales, FIDO físico, ACL efectiva, branch protection real ni staging.
- D2-A, D2-B y D2-C fueron documentación fusionada, no implementación/validación. Los estados de PR, reviews, checks y branch protection citados en el expediente se verificaron en noviembre de 2026; reconsultar GitHub antes de cualquier operación externa.
- PR #204 de LIVESTOCK-MANAGER es independiente de Owner Authorization; su estado OPEN se observó el 2026-11-05, no se revalidó en esta auditoría.

### 5.1 Estado documental externo (corte de lectura: 2026-11-05)

Estos estados son históricos al corte indicado; deben reconsultarse antes de cualquier operación externa. Las seis PR D2-A/B/C estaban fusionadas, pero no se registraban reviews. Esto acredita integración documental, no aprobación técnica, validación operativa ni activación.

| Repo / PR | Estado y merge SHA | Cambios reportados | Observación al corte |
|---|---|---:|---|
| Factory #3 | MERGED · `dfb8083bc2e027ba18c401d9829854b473508f66` · 2026-11-03 21:57:26Z | 21 archivos, +692/−1 | 0 reviews; `test-and-compliance` falló. D2A-02/03 quedaron parciales: 3/5 documentos P1-A3 idénticos; Threat Model y Acceptance Matrix fueron editados. |
| Console #1 | MERGED · `156fdd06f2ba4f55a6a1ca18986749659686b690` · 23:10:10Z | 3 archivos, +112/−6 | 0 reviews; documentación describe el gap de la base revisada, sin validar código. |
| LIVESTOCK-MANAGER #206 | MERGED · `7d72dc5e5ba8946f8876691cbbb4a8ee056c8259` · 23:10:26Z | 1 archivo, +9/−1 | 0 reviews; PR documental D2-C. |
| livestock-desktop #16 | MERGED · `c7c10608ace292bc2a15055ba7457eb3d79757bc` · 23:10:41Z | 1 archivo, +13/−0 | 0 reviews; PR documental D2-C. |
| livestock-pwa-msix #54 | MERGED · `4b67d3a639ec5329e0ef848c6b9316e9f3fa723d` · 23:10:58Z | 1 archivo, +8/−0 | 0 reviews; PR documental D2-C. |
| livestock-manager-support-api #14 | MERGED · `95b0e9e9c1364a772d3a531e85cc0a6cb453b7dc` · 23:11:14Z | 1 archivo, +15/−1 | 0 reviews; permisos reales de la GitHub App quedaron no verificados. |

Según la inspección de protección de ramas incluida en ese expediente, Factory `main` y Console `main` no tenían branch protection; LIVESTOCK-MANAGER `master` tenía protección pero cero aprobaciones requeridas y no tenía checks requeridos. No se revalidó ese estado el 2026-11-08. LIVESTOCK-MANAGER PR #204 (AuditService v2, distinta de la tarea de auditoría #203) se reportaba OPEN, HEAD `e4e7cfff04f2f648ec124527b232df689830bca6`, sin reviews; tampoco se revalidó hoy.

## 6. Siguiente plan recomendado

1. Mantener `OWNER_AUTH_ENABLED=false`; no usar el flujo para merges reales.
2. Corregir `review_context()` y añadir prueba de regresión local.
3. Diseñar/probar una custodia de credenciales que valide ACL por principal y una identidad GitHub App de mínimo privilegio, sin `gh auth` compartida con agentes.
4. Versionar/migrar SQLite y fallar al arrancar si el esquema requerido no está disponible; confirmar la misma DB para Factory/Console en una configuración autorizada.
5. Especificar resolución auditada para `MERGE_UNKNOWN` sin reintento automático y validar SSHSIG con vectores OpenSSH reales.
6. Solo tras revisión y autorización separadas: probar con FIDO hardware, GitHub App de staging, ACL efectiva, checks/branch protection y staging.
7. Presentar diffs y pruebas al propietario; commit, push, PR, merge, permisos o activación requieren autorizaciones independientes.

**Conclusión:** hay un prototipo local recuperado con controles fail-closed útiles, pero no está listo para producción/integración. Este documento es un informe local; no acredita aprobación del propietario, no activa capacidades y no modifica el código.
