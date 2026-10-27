@echo off
title FCC Server - Free Claude Code (Multimodal)
cd /d "%~dp0"
echo =================================================================
echo   INICIANDO FREE CLAUDE CODE SERVER (FCC) CON SOPORTE MULTIMODAL
echo   Puerto Local Loopback: http://127.0.0.1:8082
echo   Parametros: --enable-multimodal
echo =================================================================
echo.

if exist "C:\Users\yo\.local\bin\fcc-server.exe" (
    "C:\Users\yo\.local\bin\fcc-server.exe" --enable-multimodal
) else (
    fcc-server.exe --enable-multimodal
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo FCC Server se ha detenido o ha finalizado con error (Codigo: %ERRORLEVEL%).
    pause
)
