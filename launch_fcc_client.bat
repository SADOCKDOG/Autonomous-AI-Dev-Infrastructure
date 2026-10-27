@echo off
title Cliente de Programacion Asistida - Free Claude Code (FCC)
cd /d "%~dp0"
echo =================================================================
echo   CLIENTE DE PROGRAMACION ASISTIDA CON FREE CLAUDE CODE (FCC)
echo   Proxy Local Loopback: http://127.0.0.1:8082/v1
echo =================================================================
echo.

set "FCC_KEY="
if exist "C:\Users\yo\.fcc\.env" (
    for /f "tokens=1,* delims==" %%A in ('type "C:\Users\yo\.fcc\.env" ^| findstr "^FCC_API_KEY="') do (
        set "FCC_KEY=%%B"
    )
)
if "%FCC_KEY%"=="" set "FCC_KEY=fcc_local_key"

set ANTHROPIC_BASE_URL=http://127.0.0.1:8082/v1
set ANTHROPIC_API_KEY=%FCC_KEY%
set OPENAI_BASE_URL=http://127.0.0.1:8082/v1
set OPENAI_API_KEY=%FCC_KEY%

echo Probando conexion con el proxy local en puerto 8082...
powershell -Command "try { $headers = @{ Authorization = 'Bearer ' + $env:ANTHROPIC_API_KEY }; $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8082/v1/models' -Headers $headers -TimeoutSec 3; Write-Host 'FCC Proxy Activo. Modelos detectados:' $r.data.Count -ForegroundColor Green } catch { Write-Host 'FCC Server no responde en 127.0.0.1:8082' -ForegroundColor Red }"

echo.
echo Entorno configurado:
echo   ANTHROPIC_BASE_URL = %ANTHROPIC_BASE_URL%
echo   OPENAI_BASE_URL    = %OPENAI_BASE_URL%
echo.
echo Herramientas cliente disponibles en C:\Users\yo\.local\bin:
echo   - fcc-claude (Claude Code preconfigurado con FCC)
echo   - fcc-codex  (Codex preconfigurado con FCC)
echo   - fcc-aider  (Aider preconfigurado con FCC)
echo   - claude     (Cliente oficial de Claude Code)
echo.
echo Consola de Administracion Web:
echo   http://127.0.0.1:8082/admin
echo.
cmd /k
