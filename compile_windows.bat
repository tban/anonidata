@echo off
echo ==================================================
echo   PREPARANDO COMPILACION DE ANONIDATA EN WINDOWS
echo ==================================================
echo.

echo 1. Instalando dependencias de Node...
call npm install
if %errorlevel% neq 0 exit /b %errorlevel%

echo 2. Creando entorno virtual de Python...
python -m venv venv

echo 3. Activando entorno e instalando requerimientos...
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
