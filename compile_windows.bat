@echo off
setlocal enabledelayedexpansion

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
    echo echo [DIAGNOSTICO] Comprobando enlazador disponible: >> "%TEMP%\run_env.bat"
    echo where link.exe >> "%TEMP%\run_env.bat"
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
