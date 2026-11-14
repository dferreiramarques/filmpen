@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title FilmPen - Criar executável

echo.
echo  ===============================
echo   FilmPen - criar FilmPen.exe
echo  ===============================
echo.

rem Reutiliza o .venv do install.bat (cria-o se não existir).
if not exist ".venv\Scripts\python.exe" (
    call "%~dp0install.bat"
    if not exist ".venv\Scripts\python.exe" exit /b 1
)

echo  [1/2] A instalar o PyInstaller ...
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt --disable-pip-version-check -q
if errorlevel 1 goto :fail

echo  [2/2] A criar o executável (demora 1-2 minutos) ...
".venv\Scripts\python.exe" -m PyInstaller filmpen.spec --noconfirm --clean
if errorlevel 1 goto :fail

echo.
echo  ===============================
echo   Pronto: dist\FilmPen.exe
echo   Podes copiá-lo para qualquer PC Windows,
echo   não precisa de Python instalado.
echo  ===============================
echo.
explorer dist
pause
exit /b 0

:fail
echo.
echo  [!] Falhou a criação do executável.
pause
exit /b 1
