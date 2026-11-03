# P1-A3 — Local API Contract del Dev Operations Intermediary

**Fase:** Fase 1 — P1-A3

## 1. Identidad del cliente
- Cliente: procesos agentes (identificación declarada por canal local autenticado).
- Servicio DOI: identidad de servicio diferenciada.

## 2. Autenticación y autorización por operación
- Operación → permiso requerido → respuesta (permitido/denegado/fail-closed).

## 3. Repositorios permitidos
- Lista positiva de repositorios para App Dev (propuesta: seleccionar por justificación; no masivo).

## 4. Ramas y referencias permitidas
- Rama dev objetivo, creación, update, force push, deletion — revalidar.

## 5. Validación de parámetros y payloads
- Validación stricta; fail-closed.

## 6. Caducidad, nonce y protección contra repetición
- Token/IAT expiración; nonce; repetición.

## 7. Límites de frecuencia y tamaño
- Rate/size limits propuestos.

## 8. Respuestas de error y fail-closed
- Errores estructurados; default deny.

## 9. Estado
Especificación de contrato para P1-A2/P1-B.
