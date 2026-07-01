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
    echo Cargando entorno de variables C++... intentando arm64_x64 (nativo en ARM)...
    call "!VS_INSTALL_DIR!\VC\Auxiliary\Build\vcvarsall.bat" arm64_x64 >nul 2>nul
    
    if not defined VCToolsInstallDir (
        echo Intentando cargar entorno x64 por emulacion...
        call "!VS_INSTALL_DIR!\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>nul
    )

    if defined VCToolsInstallDir (
        echo [OK] Entorno MSVC cargado. VCToolsInstallDir: !VCToolsInstallDir!
        
        rem Buscar el path absoluto de link.exe real (MSVC) ignorando el de Git
        set REAL_LINK_EXE=
        if exist "!VCToolsInstallDir!bin\Hostarm64\x64\link.exe" set REAL_LINK_EXE=!VCToolsInstallDir!bin\Hostarm64\x64\link.exe
        if exist "!VCToolsInstallDir!bin\Hostx64\x64\link.exe" set REAL_LINK_EXE=!VCToolsInstallDir!bin\Hostx64\x64\link.exe
        if exist "!VCToolsInstallDir!bin\Hostx86\x64\link.exe" set REAL_LINK_EXE=!VCToolsInstallDir!bin\Hostx86\x64\link.exe
        
        if defined REAL_LINK_EXE (
            echo [OK] Enlazador MSVC encontrado en: !REAL_LINK_EXE!
            set CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=!REAL_LINK_EXE!
        ) else (
            echo [ERROR CRITICO] No se encontro link.exe dentro de VCToolsInstallDir.
            echo Asegurate de haber instalado "Herramientas de compilacion de MSVC v143 - VS 2022 C++ x64/x86".
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR CRITICO] Fallo al ejecutar vcvarsall.bat. No se instalaron las herramientas x64 cruzadas.
        pause
        exit /b 1
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
