@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title FilmPen - Instalador

echo.
echo  ===============================
echo   FilmPen - Instalador
echo  ===============================
echo.

rem --- 1. Procurar Python 3.10 ou mais recente ------------------------------
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
    goto :python_ok
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto :python_ok
)

echo  [!] Não encontrei o Python 3.10 ou mais recente.
echo.
where winget >nul 2>nul
if errorlevel 1 goto :python_manual
choice /c SN /m "  Instalar o Python 3.12 agora com o winget"
if errorlevel 2 goto :python_manual
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo  Python instalado. Fecha esta janela e corre o install.bat outra vez
echo  (o Windows só reconhece o Python novo numa janela nova).
echo.
pause
exit /b 1

:python_manual
echo  Instala o Python a partir de https://www.python.org/downloads/
echo  e marca a opção "Add python.exe to PATH" no instalador.
echo  Depois corre este install.bat outra vez.
echo.
pause
exit /b 1

:python_ok
echo  [1/3] Python encontrado:
%PY% --version
echo.

rem --- 2. Ambiente virtual (.venv) -----------------------------------------
if exist ".venv\Scripts\python.exe" (
    echo  [2/3] Ambiente virtual .venv já existe.
) else (
    echo  [2/3] A criar o ambiente virtual em .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto :venv_fail
)
echo.

rem --- 3. Dependências ------------------------------------------------------
echo  [3/3] A instalar as dependências (numpy, Pillow) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --disable-pip-version-check -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 goto :pip_fail
".venv\Scripts\python.exe" -c "import numpy, PIL; print('        numpy', numpy.__version__, '/ Pillow', PIL.__version__)"
if errorlevel 1 goto :pip_fail
echo.

rem --- Atalho opcional ------------------------------------------------------
choice /c SN /m "  Criar atalho do FilmPen no Ambiente de Trabalho"
if errorlevel 2 goto :done
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\FilmPen.lnk'); $s.TargetPath='%~dp0start.bat'; $s.WorkingDirectory='%~dp0'; $s.Description='FilmPen - film looks para a Olympus E-PL9'; $s.Save()"
if errorlevel 1 (
    echo  [!] Não foi possível criar o atalho, mas o FilmPen está instalado.
) else (
    echo  Atalho criado no Ambiente de Trabalho.
)

:done
echo.
echo  ===============================
echo   Instalação concluída.
echo   Para arrancar: start.bat
echo  ===============================
echo.
pause
exit /b 0

:venv_fail
echo.
echo  [!] Falhou a criação do ambiente virtual.
pause
exit /b 1

:pip_fail
echo.
echo  [!] Falhou a instalação das dependências. Verifica a ligação à internet
echo      (o computador não pode estar ligado ao Wi-Fi da câmara nesta fase).
pause
exit /b 1
