@echo off
setlocal enabledelayedexpansion

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
        rem Intento alternativo sin requerir el componente especifico
        for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -products * -property installationPath`) do (
            set VS_INSTALL_DIR=%%i
        )
    )
)

if defined VS_INSTALL_DIR (
    echo [OK] Visual Studio encontrado en: !VS_INSTALL_DIR!
    echo Cargando entorno de variables C++ para x64...
    call "!VS_INSTALL_DIR!\VC\Auxiliary\Build\vcvarsall.bat" x64
    
    echo Verificando si link.exe esta disponible ahora...
    where link.exe >nul 2>nul
    if !errorlevel! neq 0 (
        echo [ERROR CRITICO] vcvarsall.bat se ejecuto, pero link.exe no esta en el PATH.
        echo Esto significa que el componente de compilacion cruzada para x64 no esta instalado correctamente.
        pause
        exit /b 1
    ) else (
        echo [OK] link.exe esta listo y configurado.
    )
) else (
    echo [ERROR CRITICO] No se encontro Visual Studio con el componente "MSVC v143 - VS 2022 C++ x64/x86 build tools".
    echo Por favor, abre Visual Studio Installer, dale a Modificar, y en la pestana "Componentes individuales"
    echo asegurate de marcar "Herramientas de compilacion de MSVC v143 - VS 2022 C++ x64/x86".
    echo Sin este componente, no se puede compilar Tauri para x64.
    pause
    exit /b 1
)

echo.
echo 2. Instalando dependencias de Node...
call npm install
if %errorlevel% neq 0 exit /b %errorlevel%

echo 3. Creando entorno virtual de Python...
python -m venv venv

echo 4. Activando entorno e instalando requerimientos...
call venv\Scripts\activate.bat
call pip install -r backend\requirements.txt
call python -m spacy download es_core_news_sm

echo.
echo ==================================================
echo   INICIANDO ORQUESTADOR DE LANZAMIENTO (RELEASE)
echo ==================================================
echo.
call npm run release

echo.
echo Proceso completado. El archivo EXE deberia estar en tu escritorio (o donde apuntara FINAL_DEST_DIR).
pause
