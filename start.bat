@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title FilmPen

rem ======================= Configuração ======================================
rem  PORT     porta do servidor (abre em http://127.0.0.1:PORT)
rem  LOOK     filme carregado ao arrancar: negative, slide, bw
rem           (vazio = mantém o último que escolheste na galeria)
rem  TRANSFER full = ficheiros completos; 2048 = cópias menores, muito mais rápido
rem  LIBRARY  pasta onde ficam as fotos (vazio = %USERPROFILE%\FilmPen)
set "PORT=8080"
set "LOOK="
set "TRANSFER=full"
set "LIBRARY="
rem ===========================================================================

if not exist ".venv\Scripts\python.exe" (
    echo  O FilmPen ainda não está instalado. A correr o instalador...
    call "%~dp0install.bat"
    if not exist ".venv\Scripts\python.exe" exit /b 1
)

set "ARGS=--port %PORT% --transfer %TRANSFER%"
if defined LOOK set "ARGS=%ARGS% --look %LOOK%"
if defined LIBRARY set "ARGS=%ARGS% --library "%LIBRARY%""

set "PYTHONIOENCODING=utf-8"
echo.
echo  FilmPen a arrancar em http://127.0.0.1:%PORT%
echo  1. Na câmara: ativa a ligação ao smartphone (menu de Reprodução)
echo  2. Liga este computador ao Wi-Fi da câmara (E-PL9-...)
echo  Para parar: fecha esta janela ou carrega Ctrl+C.
echo.

".venv\Scripts\python.exe" -m filmpen run --open %ARGS% %*

echo.
echo  O servidor parou.
pause
