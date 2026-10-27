# Validar en local con sesión de soporte real

## Qué resuelve

`tauri dev` corre sobre `http://localhost:8088` y no tiene contexto de Microsoft
Store. La compra de `support_unlock` pasa por WinRT (`comprar_complemento`), que
solo funciona en una app instalada desde la Store. Por eso, al desarrollar en
local, el panel de soporte se quedaba en «Sin licencia»: no había `purchase_token`
con el que emitir sesión contra el Worker, y sin sesión no se veían ni los tickets
existentes ni el correo de la licencia.

Hasta ahora la única forma de ver esa parte era generar un `.msix` y subirlo a
Partner Center. Este flujo evita una subida por cada cambio.

## Cómo funciona

`frontend/js/dev-sesion.js` se carga **antes** de `support-api.js`, porque ese
módulo lee la sesión del `localStorage` una sola vez, al evaluarse. Al arrancar
en localhost pide al backend nativo el contenido de `.dev-token` y, si es
distinto de la sesión ya guardada, lo escribe y recarga una vez.

El backend es el comando `token_desarrollo` de `src-tauri/src/main.rs`:

```rust
#[cfg(debug_assertions)]
#[tauri::command]
fn token_desarrollo() -> Result<Option<String>, String>
```

Lee, por orden:

1. La variable de entorno `LIVESTOCK_DEV_TOKEN`.
2. El fichero `.dev-token` de la raíz del repo (`src-tauri/../.dev-token`).

## Uso diario

1. En la app **instalada desde la Store**, consola (`Ctrl+Shift+I`):

   ```js
   copy(JSON.stringify(JSON.parse(localStorage.getItem('livestock_support_session'))))
   ```

2. Pegar ese texto en `.dev-token` (raíz del repo) y guardar.
3. `npm run tauri dev`.

Ya sale con la licencia activa, el histórico de tickets y el correo.

### A mano, sin fichero

```js
DevSesion.estado()        // qué sesión hay, de dónde viene y cuánto le queda
DevSesion.activar(sesion) // pega la sesión y recarga
DevSesion.desactivar()    // la borra y recarga
```

## Caducidad

La sesión dura 24 h (`expira`), aunque el JWT que la firma dure más. Cuando
`DevSesion.estado()` diga que ha caducado, se repite el paso 1. No hay forma de
evitarlo desde el cliente: `JWT_SECRET` es de solo escritura en Cloudflare, así
que no se puede acuñar una sesión nueva desde local.

## Por qué es seguro

| Riesgo | Cómo está cubierto |
| --- | --- |
| Que el token acabe en el paquete de la Store | `.dev-token` está fuera de `frontend/`, y `frontendDist` es `../frontend`. No se empaqueta. |
| Que se suba al repo | `.gitignore` línea `.dev-token`. `git check-ignore -v .dev-token` lo confirma. |
| Que el binario publicado lea credenciales | El comando es `#[cfg(debug_assertions)]`: en release ni se compila. Hay un `generate_handler!` distinto por perfil. |
| Que el código entre en la app instalada | `dev-sesion.js` solo actúa si el host es `localhost`. En la app instalada no hace nada, aunque viaje dentro del paquete. |
| Que se emissionen tickets sin querer | El módulo no habla con el Worker. Solo escribe la sesión en `localStorage`; las llamadas las hace el panel de siempre. |

## Comprobaciones

```bash
node --check frontend/js/dev-sesion.js
cd src-tauri && cargo check            # perfil debug: el comando existe
cd src-tauri && cargo check --release  # perfil release: el comando no existe
```

## Nota sobre `ENTORNO=development`

El Worker tiene un bypass (`ENTORNO=development`) que salta la verificación de
licencia en `requiereLicencia`. **No está definido en producción** y no se usa
aquí: este flujo valida contra la licencia real, que es lo que interesa. Ver
[worker-de-soporte-y-flujo-de-tickets.md](worker-de-soporte-y-flujo-de-tickets.md).