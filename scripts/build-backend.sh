#!/usr/bin/env bash
set -e

echo "=== Iniciando compilación del Backend ==="

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "MacOS detectado. Iniciando proceso de compilación Universal..."

    # Asegurarnos de que el directorio de binarios existe
    mkdir -p src-tauri/binaries

    # 1. Build ARM64 (Apple Silicon)
    echo ""
    echo "--- [1/2] Compilando para ARM64 (Apple Silicon) ---"
    # El entorno actual ya es arm64 (venv)
    venv/bin/pyinstaller --clean anonidata-backend.spec
    rm -f src-tauri/binaries/anonidata-backend-aarch64-apple-darwin
    cp dist/anonidata-backend src-tauri/binaries/anonidata-backend-aarch64-apple-darwin
    echo "✓ Binario ARM64 generado."

    # 2. Build x86_64 (Intel)
    echo ""
    echo "--- [2/2] Compilando para x86_64 (Intel) ---"
    
    # Detectar el Python universal instalado
    PYTHON_INTEL="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    
    if [ ! -f "$PYTHON_INTEL" ]; then
        echo "Error: No se encuentra Python 3.11 en $PYTHON_INTEL."
        echo "Asegúrate de haber instalado el paquete de Python.org."
        exit 1
    fi

    if [ ! -d "venv-intel" ]; then
        echo "Creando entorno virtual para Intel (venv-intel)..."
        arch -x86_64 "$PYTHON_INTEL" -m venv venv-intel
    fi

    echo "Instalando dependencias de Python para la arquitectura Intel..."
    arch -x86_64 venv-intel/bin/pip install --upgrade pip
    arch -x86_64 venv-intel/bin/pip install -r backend/requirements.txt
    
    # Descargar el modelo ligero de spaCy en el entorno Intel
    arch -x86_64 venv-intel/bin/python -m spacy download es_core_news_sm

    echo "Ejecutando PyInstaller en modo Intel (Rosetta 2)..."
    arch -x86_64 venv-intel/bin/pyinstaller --clean anonidata-backend.spec
    rm -f src-tauri/binaries/anonidata-backend-x86_64-apple-darwin
    cp dist/anonidata-backend src-tauri/binaries/anonidata-backend-x86_64-apple-darwin
    echo "✓ Binario x86_64 generado."

    echo ""
    echo "--- [3/3] Creando binario Universal (Lipo) ---"
    rm -f src-tauri/binaries/anonidata-backend-universal-apple-darwin
    lipo -create -output src-tauri/binaries/anonidata-backend-universal-apple-darwin \
        src-tauri/binaries/anonidata-backend-aarch64-apple-darwin \
        src-tauri/binaries/anonidata-backend-x86_64-apple-darwin
    echo "✓ Binario Universal generado."

    echo ""
    echo "=== Backend Universal Compilado Exitosamente ==="
else
    echo "Compilando para Windows..."
    venv/Scripts/pyinstaller --clean anonidata-backend.spec
fi
