@echo off
title Software Factory Control Center
echo =======================================================================
echo INICIANDO CONSOLA DE GESTION INTEGRAL PARA WINDOWS
echo Sdog Farm Software Factory (sadogfarm.onmicrosoft.com)
echo =======================================================================

cd /d "%~dp0"
set PYTHONPATH=src;%CD%

python desktop_console\app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La consola se cerro con codigo de error %ERRORLEVEL%.
    pause
)
