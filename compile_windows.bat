@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if "%~1"=="--env-loaded" goto :build

echo ==================================================
echo   PREPARANDO COMPILACION DE ANONIDATA EN WINDOWS
echo ==================================================
echo.

echo 1. Buscando compilador C++ (MSVC) para x64...
set VSWHERE="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist %VSWHERE% (
    for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set VS_INSTALL_DIR=%%i
    )
    if not defined VS_INSTALL_DIR (
        for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -products * -property installationPath`) do (
            set VS_INSTALL_DIR=%%i
        )
    )
)

if defined VS_INSTALL_DIR (
    echo [OK] Visual Studio encontrado en: !VS_INSTALL_DIR!
    echo.
    echo ==================================================
    echo CARGANDO ENTORNO MSVC (Cualquier error debajo es de Visual Studio)
    echo ==================================================
    
    rem Creamos un script temporal para lanzar el entorno y luego volver a llamarnos
    echo call "!VS_INSTALL_DIR!\VC\Auxiliary\Build\vcvarsall.bat" arm64_x64 ^>nul > "%TEMP%\run_env.bat"
    echo call "%~dp0compile_windows.bat" --env-loaded >> "%TEMP%\run_env.bat"
    
    rem Ejecutamos el script temporal
    "%TEMP%\run_env.bat"
    exit /b !errorlevel!
) else (
    echo [ERROR CRITICO] No se encontro Visual Studio.
    pause
    exit /b 1
)

:build
echo.
echo ==================================================
echo   ENTORNO CARGADO - CONTINUANDO COMPILACION
echo ==================================================
echo.

if defined VCToolsInstallDir (
    set "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=!VCToolsInstallDir!bin\HostARM64\x64\link.exe"
    if not exist "!CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER!" set "CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=!VCToolsInstallDir!bin\Hostx64\x64\link.exe"
    
    set "CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER=!VCToolsInstallDir!bin\HostARM64\ARM64\link.exe"
    if not exist "!CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER!" set "CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER=!VCToolsInstallDir!bin\Hostx64\ARM64\link.exe"
    
    echo Forzando Rust a usar el enlazador MSVC [Target x64]: !CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER!
    echo Forzando Rust a usar el enlazador MSVC [Host ARM64]: !CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER!
)

echo 2. Instalando dependencias de Node...
if exist package-lock.json (
    echo [INFO] Eliminando package-lock.json para evitar conflictos de permisos de red...
    del /f /q package-lock.json
)
call npm install --no-package-lock
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al instalar las dependencias de Node.
    pause
    exit /b %errorlevel%
)

echo 3. Creando entorno virtual de Python...
set PYTHON_CMD=python

py -3.13 -c "import sys" >nul 2>&1
if !errorlevel! equ 0 (
    set PYTHON_CMD=py -3.13
    echo [INFO] Detectado Python 3.13 estable. Usando para el entorno virtual.
) else (
    py -3.12 -c "import sys" >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=py -3.12
        echo [INFO] Detectado Python 3.12 estable. Usando para el entorno virtual.
    ) else (
        echo [WARNING] No se detecto Python 3.13 o 3.12 especifico. Usando python por defecto.
    )
)

!PYTHON_CMD! -m venv venv
if !errorlevel! neq 0 (
    echo [ERROR] Fallo al crear el entorno virtual de Python.
    pause
    exit /b !errorlevel!
)

echo 4. Activando entorno e instalando requerimientos...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al activar el entorno virtual de Python.
    pause
    exit /b %errorlevel%
)

call pip install -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al instalar los requerimientos de Python.
    pause
    exit /b %errorlevel%
)

call python -m spacy download es_core_news_sm
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al descargar el modelo de spacy en espanol.
    pause
    exit /b %errorlevel%
)

echo 5. Copiando Tesseract OCR local para integracion portable...
if exist "C:\Program Files\Tesseract-OCR" (
    echo [INFO] Detectado Tesseract local en C:\Program Files\Tesseract-OCR. Preparando bundle...
    if not exist "backend\tesseract" mkdir "backend\tesseract"
    xcopy /E /I /Y "C:\Program Files\Tesseract-OCR" "backend\tesseract" >nul
) else (
    echo [WARNING] No se encontro Tesseract en C:\Program Files\Tesseract-OCR. El instalador final NO tendra OCR integrado.
)

echo.
echo ==================================================
echo   INICIANDO ORQUESTADOR DE LANZAMIENTO [RELEASE]
echo ==================================================
echo.
call npm run release
if %errorlevel% neq 0 (
    echo [ERROR] Fallo al compilar o empaquetar la aplicacion.
    pause
    exit /b %errorlevel%
)

echo.
echo Proceso completado. El archivo EXE deberia estar en tu escritorio [o donde apuntara FINAL_DEST_DIR].
pause
