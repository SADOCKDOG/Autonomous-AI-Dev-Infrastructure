# Arquitectura del sistema — Livestock Manager

> Manual de tecnicos para desarrolladores. Describe como encajan las piezas y
> por que. Es conocimiento para entender el funcionamiento logico, no una guia
> de usuario: no explica pantallas, explica fronteras, contratos y riesgos.
>
> Fuente: codigo en `livestock-desktop`, `livestock-pwa-msix`, `livestock-manager-support-api`
> y la configuracion de Cloudflare / Microsoft Store / Entra.

## Que es el producto

Livestock Manager es la app de gestion ganadera de SdogFarm Software Factory.
Gestiona los animales de una explotacion y los registros y guias que exige la
normativa (SIGGAN, crotal/especie, etc.). Lo sustantivo del producto es el dato
ganadero: es lo que el usuario no puede permitirse perder.

Se distribuye en dos plataformas de pago, sobre un mismo nucleo web:

- **Escritorio (Windows):** app empaquetada con **Tauri 2** y distribuida en la
  **Microsoft Store** como producto premium. Es la plataforma con mas uso y la
  unica con licencia verificada contra la Store.
- **Movil (Android):** app con **Capacitor** (WebView), mismo frontend, con su
  propia identidad y sus propios historiales.

Ademas hay una **PWA** (`livestock-pwa-msix`) servida desde GitHub Pages
(`https://sadockdog.github.io/livestock-pwa-msix/`) que se usa como demo y como
fuente de la base de conocimiento (guia de usuario en `manual/`).

Una misma explotacion puede tener historiales distintos en escritorio y en
movil. El sistema **no unifica historiales entre plataformas**: eso es una
limitacion conocida del producto, no un fallo.

## Las piezas

```
+----------------+        +----------------+        +----------------+
|  Desktop (Tauri)|        | Android (Capa) |        |    PWA (Pages) |
| frontend + Rust |        |  WebView + app |        |    sw.js + UI  |
+--------+-------+        +--------+-------+        +--------+-------+
         |                           |                        |
         | HTTPS (JWT)               | HTTPS (JWT)            | HTTPS (JWT)
         +---------------------------+------------------------+
                                    |
                         +----------v-----------+
                         |  Cloudflare Worker   |
                         | livestock-manager-   |
                         | support-api-produc-  |
                         | tion                 |
                         +----+------+------+---+
                              |      |      |
                    KV  +-----+      |      +----+  GitHub (issues)
                   (TICKETS_KV)      |           (repo soporte)
                                     |
                              Workers AI  (llama-3.3-70b)
```

La pieza central es el **Worker de soporte** (`livestock-manager-support-api`),
desplegado en produccion como `livestock-manager-support-api-production` en
`https://livestock-manager-support-api-production.livestock-desktop.workers.dev`.
Es un Worker de Cloudflare hecho con **Hono** y **jose**, sin base de datos
relacional: el estado vive en **KV** (`TICKETS_KV`).

No hay un backend de "la app" separado del de soporte. El Worker hace solo dos
cosas:

1. **Verificar la compra y emitir una sesion** (`/auth/*`) para saber quien es.
2. **Recibir incidencias, estructurarlas con IA y crear issues en GitHub**
   (`/tickets/*`, `/webhooks/*`).

La decision de no tener backend de datos es deliberada: el frontend trabaja
localmente (Tauri usa el filesystem, la PWA usa IndexedDB) y solo sale a la red
para soporte.

## Licencias y cadena de identidad

La compra se valida contra la **Microsoft Store** mediante la API de compras del
servicio, usando una clave firmada para ese servicio (`IDX10205`). Hay **dos
Store IDs** de complemento y hay que no confundirlos:

- El **complemento de soporte** (lo que compra el soporte): `9P4577W3B0D2`.
- El **de la app principal**: `9P104KJR294Z`. Confundirlos rompe la compra.

La identidad del usuario en el escritorio se resuelve por una cadena
**Entra ID → Store**: el permiso de la Store vive en **Partner Center**, y la
app y el inquilino se sustituyeron el 2026-09-20. Cambios aqui requieren tocar
el registro de la app en Entra y los permisos en Partner Center.

> Los secretos (clave privada, client secret, tokens) **nunca** van en el repo ni
> en `wrangler.toml`: se cargan como secretos de Cloudflare o variables de
> entorno. Una var vacia con el mismo nombre que un secreto pisa al secreto
> (causo un incidente el 2026-08-28).

## Frontend: como se conecta al Worker

Los clientes llaman al Worker por HTTPS con un **JWT** en la cabecera
`Authorization: Bearer <token>`. La URL base se define en dos sitios del
escritorio:

- `livestock-desktop/frontend/js/services/support-api.js`
- `livestock-desktop/frontend/js/services/soporte-store.js`

Ambos usan el mismo patron: `window.SUPPORT_API_BASE` si existe, si no el Worker
de produccion. Esto permite apuntar a otro entorno (por ejemplo el de `wrangler
dev`) sin tocar el codigo, y es sobre lo que se apoyan las pruebas de escritorio
en local.

### Origenes permitidos (CORS)

El Worker limita CORS a una lista blanca. Si se anade un origen (otro dominio de
Pages, un subdominio de Tauri en otra plataforma), hay que anadirlo en
`src/index.ts` (`ORIGENES`). Origenes actuales:

- `https://localhost`, `capacitor://localhost` (Android/Capacitor)
- `http://localhost:8080`, `http://localhost:8088` (dev)
- `https://sadockdog.github.io` (PWA)
- `tauri://localhost`, `http://tauri.localhost`, `https://tauri.localhost`
  (escritorio)

## Por que GitHub para el soporte

El Worker crea issues en el repo `SADOCKDOG/livestock-manager-support-tickets`.
El mantenedor lee y responde en GitHub; el usuario ve las respuestas en la app.
El Worker de soporte **nunca** genera commits, ramas ni pull requests: solo
crea y comenta issues. La GitHub App esta instalada solo con permiso
`Issues: write`. Cualquier ampliacion de ese host se decide fuera del codigo.

## El papel de la IA

El Worker usa **Workers AI** (llamada a `env.AI`, modelo
`@cf/meta/llama-3.3-70b-instruct-fp8-fast` para las tareas de estructura
mientras el 8b se inventa campos). La IA **no diagnostica ni propone parches**:
estructura el reporte y redacta respuestas de soporte. Lo que aventura como
causa va como hipotesis, separada, en un comentario del issue.

La IA corre dentro de Cloudflare, sin clave ni saldo externos. A cambio el
modelo redacta peor que uno de pago, por eso hay siempre borrador de reserva y
un acuse fijo cuando el modelo falla.

## Despliegue y versiones

- **Worker:** `npx wrangler deploy --env production` desde
  `livestock-manager-support-api`. Produce la version `...-production`.
- **Escritorio:** 
  - Para probar localmente: `npm run tauri dev` o `npm run build:msix` (genera MSIX sin firmar)
  - Para versiones de prueba/vuelo: El MSIX firmado debe subirse **manualmente vía Partner Center Portal**, no mediante CLI
    - El CLI de Microsoft Store solo sirve para crear nuevos productos, no para subir versiones existentes
    - Si Partner Center rechaza reconstruir con la misma version y contenido distinto (error de "package already exists"), hay dos opciones:
      1. Subir el paquete MSIX ya generado (recomendado para vuelos)
      2. Incrementar el numero de version y subir como nueva version
  - **Numeracion de version:** El MSIX toma la version de 4 lugares que deben estar sincronizados:
    - `frontend/js/app-version.js`: `version` y `versionCode` (avanza 1 por version de app)
    - `src-tauri/Cargo.toml`: `version`
    - `src-tauri/Cargo.lock`: `version` (actualizado automaticamente)
    - `src-tauri/tauri.conf.json`: `version`
  - El comando `npm run build:msix` ejecuta `npm run sync` primero, que:
    - Copia cambios del maestro al desktop (respeta preservedList)
    - **Aborta si el maestro no está en rama `master` o `desktop-mvp`**
    - Por eso es necesario estar en la rama correcta antes de build:msix
- **PWA:** publicada en GitHub Pages desde `livestock-pwa-msix`.

Los tres despliegues son independientes: no hay un monorepo que los versione
juntos.

## Relación maestro ↔ desktop

- **No hay monorepo:** Los repositorios `LIVESTOCK-MANAGER` (maestro) y `livestock-desktop` son independientes
- **Flujo de trabajo maestro → desktop:**
  - El maestro (`LIVESTOCK-MANAGER`) contiene el frontend web compartido
  - El comando `npm run sync` copia cambios desde el maestro al desktop:
    - `rsync -av --exclude-from=preservedList.txt LIVESTOCK-MANAGER/frontend/ livestock-desktop/frontend/`
    - El archivo `preservedList.txt` protege ficheros propios del desktop que no deben sobrescribirse:
      - `soporte-store.js` (contiene Store ID de Microsoft Store)
      - `index.html` (puede tener personalizaciones de desktop)
      - `app-version.js` (version específica del desktop)
      - Otros ficheros de configuración de Tauri
  - Por eso `soporte-store.js` **no existe en el maestro** - es exclusivo del desktop y protegido por el sync
- **Flujos de desarrollo independientes:**
  - El maestro tiene su propio ciclo de ramas/PRs para mejoras del frontend web
  - El desktop tiene su propio ciclo para ajustes de Tauri/nativo
  - El contenido de Soporte llegó al maestro mediante PRs específicas del equipo de soporte, no mediante sincronizacion desde desktop

## Riesgos y reglas de oro

- **El dato del usuario es lo mas valioso.** Las degradaciones se eligen a
  proposito: ante la duda, el mensaje del usuario llega siempre al equipo, y si
  algo falla lo que se pierde es comodidad, no datos.
- **Actualizar el tope de mensajes** (`MAX_MENSAJES_PER_DAY`) es temporal para
  pruebas, y se debe volver a `10` al terminar.
- **La escalada a humano** pasa a la tercera vez que el usuario dice que sigue
  sin funcionar; despues la maquina no decide.
- **No commitees claves ni tokens.** Ver la seccion de identidad.