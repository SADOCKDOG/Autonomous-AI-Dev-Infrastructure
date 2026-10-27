# Politicas de Seguridad, Contencion y Privacidad

## 1. Exposicion de Interfaces de Red
- Todos los servicios de escucha de la Software Factory (FastAPI en puerto 8000 y FCC Proxy en puerto 8082) deben enlazarse estrictamente a interfaces de loopback (`127.0.0.1`).
- Queda prohibida la exposicion de puertos de administracion o inferencia hacia redes locales (LAN) o internet publico.

## 2. Clasificacion y Fronteras de Datos
El motor de politicas (`ModelPolicyEngine`) valida la clasificacion de datos antes de enviar cualquier peticion a un proveedor de inferencia:
- **local_only:** Datos de alta confidencialidad o codigo propietario restringido. Prohibicion absoluta de transmision a proveedores remotos. Si se detecta un proveedor no local, la peticion se aborta con `PolicyViolationError`.
- **approved_remote:** Codigo y contexto aprobados para transmision hacia endpoints autorizados por la direccion tecnica.
- **restricted:** Requiere bandera de consentimiento y aprobacion humana explicita previa a su incorporacion en el prompt.

## 3. Seguridad de Ejecucion de Procesos (Sandbox)
El componente `CommandExecutor` aplica una barrera de seguridad de ejecucion rigurosa:
- **Validacion de Ejecutables:** Solo se permite la ejecucion de binarios incluidos en la lista autorizada (`git`, `pytest`, `python3`, `ruff`).
- **Bloqueo de Inyecciones:** Prohibicion de caracteres de encadenamiento y redireccion de shell (`;`, `&&`, `||`, `|`, `>`, `<`, backticks, `$()`).
- **Ejecucion Directa:** Los procesos se invocan mediante `asyncio.create_subprocess_exec` sin interprete de comandos intermedio (`shell=False`).
- **Limites de Recursos:** Aplicacion de tiempos limite obligatorios (timeout) con terminacion forzada (`kill`) de procesos y limitacion de salida a 1 MB.

## 4. Prevencion de Fuga de Credenciales
- **Escaneo Automatizado de Diffs:** Previo a la transicion al estado de revision, `SecretScanner` analiza las adiciones del codigo buscando patrones de claves privadas (RSA/SSH), tokens de GitHub, claves de OpenAI, credenciales de AWS/GCP y tokens Bearer.
- **Sanitizacion de Auditoria:** Se redactan automaticamente campos sensibles (`token`, `password`, `key`, `secret`, `authorization`) en los payloads almacenados en la tabla `audit_logs`.

## 5. Barrera de Aprobacion Humana
Las operaciones con impacto colateral en el ciclo de vida del software exigen intervencion humana directa registrada en auditoria:
- Incorporacion de cambios a ramas principales (`git merge`).
- Publicacion de ramas hacia repositorios remotos (`git push`).
- Transicion final de tareas al estado `DONE`.
- Despliegues o ejecucion de migraciones de esquema destructivas.
