# Políticas de Seguridad y Contención

1. **Loopback Only:** Todos los servicios (FastAPI, FCC proxy, endpoints de administración) deben enlazarse a `127.0.0.1`. Prohibida la exposición pública o en LAN.
2. **Cero Secretos:** Ningún token, API key ni certificado debe persistirse en Git, bases de datos o mensajes de error.
3. **Clasificación de Datos:**
   - `local_only`: Prohíbe terminantemente el envío de contexto a proveedores externos o remotos.
   - `approved_remote`: Permite inferencia en proveedores autorizados por el usuario.
   - `restricted`: Requiere aprobación humana antes de procesar.
4. **Barrera de Aprobación Humana:** Acciones de alto impacto (`git push`, `merge`, `deploy`, borrado de archivos) exigen aprobación explícita del usuario.
5. **Restricción de Modelos Locales:** Prohibida la descarga automática o implícita de pesos de modelos sin autorización previa.
