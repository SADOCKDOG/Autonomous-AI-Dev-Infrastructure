# Cómo validar y gestionar versiones — Livestock Manager

> Guía práctica para desarrolladores sobre como verificar que los cambios funcionan correctamente y gestionar las versiones del producto. Incluye procedimientos de testing, validación de accesibilidad y manejo de numeracion de versiones.

## Validación de funcionalidad

### Suite de testing con Playwright
La aplicacion incluye una suite de pruebas end-to-end basada en Playwright que permite validar el comportamiento completo sin depender de marcadores visuales potencialmente engañosos.

**Ejecucion de tests:**
```bash
# Ejecutar todos los tests
npm run test:e2e

# Ejecutar un test específico
npm run test:e2e -- --grep "flujo de soporte"
```

**Caracteristicas importantes:**
- Cada test inicia su **propio servidor local** en un puerto aleatorio
- La fuente de verdad es la **raiz del repositorio**, no el directorio `www/` (que es build output y se ignora en git)
- Esto permite auditar sin fiarse de lo marcado visualmente, ya que los tests interactuan con la aplicacion real en ejecución

### Validación de accesibilidad y contraste
Se utiliza **axe-core** para asegurar cumplimiento de WCAG AA.

**Ejecucion de auditoria de accesibilidad:**
```bash
npm run test:axe
```

**Hallazgos típicos y correcciones:**
- Los tokens de color están definidos en `css/design-tokens.css`
- Algunos acentos de texto necesitan variantes más claras para lograr contraste suficiente
- Buscar variables que empiecen con `--c--txt` y ajustar sus valores si el contraste reportado por axe-core es insuficiente
- En esta sesión se pasó de 27 problemas a 0 tras ajustar variantes de color

### Validación en emulador Android
Para testear la aplicacion Capacitor en Android:

**Requisitos:**
- Android Studio con AVD configurado (Android 10+ recomendado)
- Node.js y dependencias del proyecto instaladas

**Procedimiento:**
1. Levantar un servidor de desarrollo local:
   ```bash
   npm run dev
   ```
   Esto iniciará el servidor en `http://localhost:8080`

2. En el emulador Android, abrir Chrome y navegar a:
   ```
   http://10.0.2.2:8080
   ```
   (La IP `10.0.2.2` es el alias especial del emulador para el host localhost)

3. Para depuración avanzada con Chrome DevTools:
   - En el emulador, ejecutar:
     ```
     adb forward tcp:9222 localabstract:webview_devtools_remote_
     ```
   - Luego abrir en Chrome del host: `chrome://inspect/#devices`
   - Hacer click en "Inspect" frente a la webview de la aplicacion

**Limitación importante:** La demo **NO** utiliza SeedData al arrancar, por lo que aparece en estado inicial vacío. Los tests por coordenadas pueden fallar debido a diferencias de densidad de pantalla entre dispositivos.

## Gestion de versiones y releases

### Proceso de subida a Microsoft Store (Escritorio)

**Para versiones de prueba/vuelo:**
1. Generar el MSIX sin firmar (para testing local):
   ```bash
   npm run build:msix
   ```
   Esto crea el paquete en `src-tauri/target/msix/` sin firma

2. Para subir al vuelo de Partner Center:
   - **NO usar el CLI de Microsoft Store** - solo sirve para crear nuevos productos
   - Subir manualmente el archivo `.msix` o `.msixbundle` generado a través del **Portal de Partner Center**
   - Ruta: Partner Center > Productos > [Tu producto] > Vuelos > [Tu vuelo] > Envíos

**Manejo de rechazos por versión duplicada:**
Si Partner Center muestra el error:
> "Ya existe un envío con este número de versión y contenido diferente"

Hay dos opciones válidas:
1. **Subir el paquete ya generado** (recomendado para vuelos rápidos)
   - Usar exactamente el mismo archivo `.msix` que falló en la validación previa
   - Partner Center lo aceptará como reenvío del mismo contenido

2. **Incrementar el número de version** (para cambios significativos)
   - Actualizar la version en los 4 lugares obligatorios:
     - `frontend/js/app-version.js`: incrementar `version` y `versionCode` (+1)
     - `src-tauri/Cargo.toml`: incrementar `version`
     - `src-tauri/Cargo.lock`: se actualiza automaticamente tras `cargo update`
     - `src-tauri/tauri.conf.json`: incrementar `version`
   - Ejemplo de avance: `4.11.14` → `4.11.15` con `versionCode` 538 → 539

**Sincronizacion previa al build:**
El comando `npm run build:msix` ejecuta primero `npm run sync` que:
- Copia cambios desde el maestro al desktop respetando el `preservedList.txt`
- **Verifica que el maestro esté en rama `master` o `desktop-mvp`**
- Aborta con error si no se cumple esta condición
- Por lo tanto, **siempre verificar la rama del maestro antes de ejecutar build:msix**

### Flujo de trabajo recomendado para releases

1. **Preparacion en maestro (`LIVESTOCK-MANAGER`):**
   - Desarrollar y hacer PRs contra `master`
   - Una vez aprobado, mergiar a `master`

2. **Preparacion en desktop (`livestock-desktop`):**
   - Asegurarse de que el maestro está en `master` (o `desktop-mvp` para testing)
   - Ejecutar `npm run sync` para traer cambios del maestro
   - Hacer ajustes específicos de desktop si es necesario (en ficheros preservados)
   - Probar localmente con `npm run tauri dev`

3. **Generacion y subida de version:**
   - Incrementar version en los 4 lugares si es necesario
   - Ejecutar `npm run build:msix`
   - Subir el MSIX generado a Partner Center vía Portal (no CLI)
   - Para vuelos: subir como reenvío si el contenido no cambio significamente, o como nueva version si si

4. **Post-subida:**
   - Monitorear el estado en Partner Center (En revisión → Aprobado → En vuelo)
   - Notificar a testers para instalar desde el vuelo
   - Recopilar feedback y preparar siguiente iteracion