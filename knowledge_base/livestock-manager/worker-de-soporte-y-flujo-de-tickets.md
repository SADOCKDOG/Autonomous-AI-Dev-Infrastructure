# Worker de soporte y flujo de tickets

> Manual de tecnicos para desarrolladores. Profundiza en el Worker
> `livestock-manager-support-api`: rutas, maquina de estados, agentes de IA,
> almacen en KV y sincronizacion con GitHub. Complementa al de arquitectura.
>
> Fuente: `livestock-manager-support-api/src/`.

## Que hace el Worker

Un Worker de Cloudflare (Hono + jose) que recibe incidencias desde la app, las
estructura con IA y crea issues en el repo de soporte. **Nunca** genera commits,
ramas ni pull requests: el mantenedor no tiene que aprobar nada, solo leer y
responder. Quien valida el reporte es el propio usuario (human-in-the-loop).

## Entradas y arranque

- `src/index.ts` — monta Hono, define CORS por ruta y enruta `/auth`, `/tickets`,
  `/webhooks`. `app.onError` devuelve un mensaje generico (`{ error: "Error
  interno" }`, 500) y el detalle se va al log: el cliente nunca ve como esta
  montado el backend.
- `src/types.ts` — tipos `Env`, `Variables`, `SesionJWT`, `Ticket`, estado, etc.
- `wrangler.toml` — variables publicas (`GITHUB_REPO_*`, `MAX_*_PER_DAY`),
  binding `AI` (Workers AI) y KV `TICKETS_KV`. Los envs `[vars]` y
  `[env.production.vars]` **no se heredan**: se repiten. Los **secretos** van con
  `wrangler secret put <NOMBRE> --env production`.

## Autenticacion y licencia (`src/middleware/auth.ts`)

Dos middlewares separados a proposito:

- `requiereSesion` — solo identifica (JWT HS256 firmado con `JWT_SECRET`). Vale
  para consultar tickets propios. Valida `sub`, `email` y `plataforma`, con
  **lista blanca explicita** para `plataforma`: `web` y `windows` se aceptan tal
  cual; cualquier otro valor degrada a `android` (comportamiento historico), pero
  se hace a proposito para no archivar incidencias de escritorio con la
  plataforma equivocada.
- `requiereLicencia` — ademas exige licencia de soporte activa. Se encadena
  DESPUES de `requiereSesion`. Solo se usa en lo que cuesta dinero (crear
  tickets). Asi, si la licencia caduca, el usuario sigue viendo su historial
  pero no puede abrir nada nuevo.

`ENTORNO=development` se salta la licencia para probar en local. **No debe
definirse en produccion**: el endpoint gasta creditos de IA y crea issues.

## Flujo de tickets (`src/routes/tickets.ts`)

El alta tiene **dos pasos** para poner a la persona en el circuito:

1. **`POST /tickets`** — estructura el reporte y devuelve un **BORRADOR**. No
   crea nada en GitHub. Exige licencia y pasa por rate limit (gasta IA).
2. **`POST /tickets/confirm`** — el usuario ha revisado (y quiza editado) el
   borrador; **solo aqui** se crea el issue. Se vuelven a limpiar las ediciones
   que el usuario haya hecho. Un borrador solo lo confirma quien lo creo.

### Rutas

| Metodo y ruta              | Exige           | Que hace |
|----------------------------|-----------------|----------|
| `POST /auth/verify-purchase` | —            | Verifica la compra y emite la sesion. |
| `GET  /auth/me`            | sesion          | Estado de la licencia. |
| `POST /tickets`            | sesion+licencia | Estructura, devuelve borrador. |
| `POST /tickets/confirm`    | sesion+licencia | Crea el issue en GitHub. |
| `GET  /tickets`            | sesion          | Incidencias propias (resumen, no hilo). |
| `GET  /tickets/:id`        | sesion          | Detalle con hilo completo. |
| `POST /tickets/:id/responder` | sesion       | Mensaje del usuario en incidencia abierta. |
| `POST /tickets/:id/confirmar` | sesion       | El usuario confirma que la solucion le funciona. |
| `POST /webhooks/github`    | —            | Cambios de estado desde GitHub (HMAC). |

### Almacen (`src/services/storage.ts`)

Todo el estado vive en KV `TICKETS_KV`, con claves por tipo:

- `ticket:<ticketId>` — el ticket completo: estado, titulo, severidad,
  `github_issue_number`, `respuestas[]` (hilo), timestamps.
- `borrador:<ticketId>` — borrador pendiente de confirmar.
- `usuario:<userId>` — datos de usuario y licencia.
- `msgs:<userId>:<dia>` — contador de mensajes del dia (rate limit).
- `ratelimit:<userId>:<dia>` — tickets creados hoy por usuario.
- `ratelimit:msticket:<ip>:<hora>` — acunado anonimo por IP/hora para claves de
  MS Store (WinRT necesita el ticket antes de que exista sesion).

Regla importante del contador de reabiertas: vive en su **propia clave**
(`reabiertas:<ticketId>`) y no dentro del ticket. La toca solo `/responder`. El
webhook guarda el ticket completo leyendo una copia que a veces es vieja; si el
contador estuviera dentro del ticket, el webhook lo devolveria atras. En clave
aparte no corre ese riesgo.

### Maquina de estados (`RANGO_ESTADO` en `types.ts`)

El estado se refleja en **etiquetas** de GitHub del issue. Orden
`enviada(0) → analizada(1) → revision(2) → curso(3) → resuelta(4)`:

- `enviada` — el issue se acaba de crear.
- `analizada` — el agente automatico ya la ha leido y respondido.
- `revision` — en la cola del equipo.
- `curso` — alguien del equipo esta con ella (atencion humana real).
- `resuelta` — propuesta de resolucion. **No es un cierre**: la cierra el usuario
  con SI/NO.

El agente **solo propone `resuelta`** cuando el ticket NO esta en `revision` ni
`curso` (no pisa al equipo). Quien cierra de verdad es el usuario.

### La etiqueta se reemplaza, no se anade

`reemplazarEtiquetaDeEstado` **quita la etiqueta anterior y pone la nueva**.
El estado se lee recorriendo etiquetas y quedandose con la primera reconocida, y
GitHub no ordena el array: si quedaran `estado:enviada` y `estado:analizada` a
la vez, el estado que ve el usuario dependeria del azar. La etiqueta de estado
es lo mas parecido a "el agente se asigna la incidencia" que permite GitHub: una
GitHub App no puede ser `assignee` (solo cuentas de persona), asi que deja la
misma marca visible con una etiqueta.

## Agentes de IA (`src/services/ai.ts`)

Tres prompts, tres funciones:

- `estructurarReporte` — `INSTRUCCIONES` (clasificador): convierte texto libre
  en un reporte con forma (`titulo`, `descripcion`, `pasos_reproduccion`,
  `severidad`, `posible_causa`). Usa `extraerJSON` y un `borradorDeReserva` si
  falla.
- `redactarRespuestaInicial` — `INSTRUCCIONES_RESPUESTA`: primera respuesta al
  usuario tras confirmar la incidencia. Pide JSON y esta funcion compone el
  texto (dejar redactar libremente daba markdown que la app escapa en vez de
  interpretar). Si no aporta nada, quien llama publica un acuse fijo.
- `redactarRespuestaSeguimiento(ai, hilo, paseAHumano)` — `INSTRUCCIONES_SEGUIMIENTO`:
  lee el hilo y responde al ultimo mensaje, y decide si la conversacion ya
  evidencia una resolucion (`resuelta`). Acepta `paseAHumano` para elegir el
  cierre: cuando ya ha escalado a atencion humana el texto es
  "La incidencia ha pasado al equipo humano de soporte...".

Reglas de los prompts (no negociables): responder solo JSON, espanol de Espana,
sin markdown, **no prometer arreglos ni plazos**, **no inventar pantallas**,
y el texto del usuario es **contenido, no ordenes** (se delimitado en el prompt
y se vuelve a limpiar lo que devuelve el modelo para neutralizar inyecciones).

### Base de conocimiento

Un bloque de conocimiento del producto (`CONOCIMIENTO_APP`) viaja en los prompts
de los agentes que escriben al usuario, para que las comprobaciones que proponen
sean reales y no inventadas. Es la opcion de coste 0 (frente a Vectorize o AI
Search): solo texto en el system prompt, sin binding ni servicio.

## Sincronizacion con GitHub (`src/services/github.ts`)

- Solo crea y comenta issues. No expone funciones de ramas/commits/PRs.
- Usa `jose` + `fetch` (no @octokit) por peso en Workers.
- La GitHub App firma un JWT con la clave privada (`PKCS#8`, se normaliza desde
  `PKCS#1` que es como entrega GitHub) y pide un **installation token** corto
  que se cachea en memoria del isolate.
- `comentarIssue` devuelve `boolean` (no lanza): casi todas las llamadas pueden
  ignorar un comentario perdido, pero el mensaje del usuario si necesita saberlo
  (si no llega a GitHub, nadie lo lee).
- `cambiarAperturaDelIssue` abre/cierra el issue. Quien reabre necesita saberlo:
  dejar la incidencia en curso en KV con el issue cerrado la esconde del equipo.

## Sincronizacion inversa: webhook (`src/routes/webhooks.ts`)

GitHub notifica cambios (nuevo comentario, cambio de etiqueta) por webhook con
HMAC. El webhook:

- Filtra mensajes del **propio usuario** para no duplicar lo que ya se guardo al
  confirmar.
- Mapea etiqueta → estado (`ETIQUETA_A_ESTADO`).
- Lee el estado y las respuestas del payload y el ticket.

**Limitacion conocida:** KV es de consistencia eventual. El webhook puede leer
una copia vieja del ticket y guardar un estado tambien viejo (se observaron
segundos de desfase entre GitHub y KV). Es la razon por la que el contador de
reabiertas vive aparte.

## Trabajo en segundo plano (`waitUntil`)

Los agentes que responden al issue y siguen el hilo corren en
`c.executionCtx.waitUntil(...)`, fuera de la respuesta HTTP: son llamadas a la
IA y a GitHub que sumaban segundos a la espera del movil sin que el usuario
gane nada (el resultado le llega igual por el webhook). **Nunca lanzan**: si
fallan, el ticket ya existe y el mantenedor lo ve en GitHub como siempre. El
agente es un extra, no un eslabon del que dependa que la incidencia exista.

## Precauciones al tocar el codigo

- Actualizar un tope (`MAX_*`) es temporal para pruebas; revisar que no quede
  subido en produccion.
- Cualquier origen nuevo entra en `ORIGENES` en `src/index.ts`.
- Los secretos van por `wrangler secret put`, nunca en `wrangler.toml`.
- Commits que cambien el comportamiento del soporte: probar antes el ciclo
  completo (crear → agente responde → usuario responde → agente propone →
  usuario confirma) usando el token del usuario frente al Worker.
