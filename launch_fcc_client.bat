@echo off
title Cliente de Programacion Asistida - Free Claude Code (FCC)
cd /d "%~dp0"
echo =================================================================
echo   CLIENTE DE PROGRAMACION ASISTIDA CON FREE CLAUDE CODE (FCC)
echo   Proxy Local Loopback: http://127.0.0.1:8082/v1
echo =================================================================
echo.

set ANTHROPIC_BASE_URL=http://127.0.0.1:8082/v1
set ANTHROPIC_API_KEY=fcc_local_key
set OPENAI_BASE_URL=http://127.0.0.1:8082/v1
set OPENAI_API_KEY=fcc_local_key

echo Probando conexion con el proxy local en puerto 8082...
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8082/v1/models' -TimeoutSec 2; Write-Host 'FCC Proxy Activo. Modelos detectados:' $r.data.Count -ForegroundColor Green } catch { Write-Host 'FCC Server no responde en 127.0.0.1:8082' -ForegroundColor Red }"

echo.
echo Entorno configurado:
echo   ANTHROPIC_BASE_URL = %ANTHROPIC_BASE_URL%
echo   OPENAI_BASE_URL    = %OPENAI_BASE_URL%
echo.
echo Para lanzar Claude Code apuntando a FCC:
echo   claude
echo.
cmd /k
