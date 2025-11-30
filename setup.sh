#!/bin/bash

# Setup script para AnoniData
# macOS y Linux

set -e  # Exit on error

echo "🚀 AnoniData Setup Script"
echo "========================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para imprimir en color
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "ℹ $1"
}

# Verificar Node.js
echo "Verificando Node.js..."
if ! command -v node &> /dev/null; then
    print_error "Node.js no está instalado"
    echo "Por favor instalar desde: https://nodejs.org/"
    echo "O en macOS: brew install node"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    print_error "Node.js versión 18+ requerida (tienes: $(node --version))"
    exit 1
fi
print_success "Node.js $(node --version)"

# Verificar Python
echo ""
echo "Verificando Python..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 no está instalado"
    echo "Por favor instalar desde: https://www.python.org/"
    echo "O en macOS: brew install python@3.11"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_success "Python $(python3 --version)"

# Verificar Tesseract
echo ""
echo "Verificando Tesseract..."
if ! command -v tesseract &> /dev/null; then
    print_warning "Tesseract OCR no está instalado"
    echo "Instalando con Homebrew..."
    if command -v brew &> /dev/null; then
        brew install tesseract tesseract-lang
        print_success "Tesseract instalado"
    else
        print_error "Homebrew no encontrado. Por favor instalar Tesseract manualmente"
        echo "macOS: brew install tesseract tesseract-lang"
        echo "Linux: sudo apt-get install tesseract-ocr tesseract-ocr-spa"
        exit 1
    fi
else
    print_success "Tesseract $(tesseract --version | head -n1)"
fi

# Instalar dependencias Node.js
echo ""
echo "Instalando dependencias Node.js..."
npm install
print_success "Dependencias Node.js instaladas"

# Configurar backend Python
echo ""
echo "Configurando backend Python..."

cd backend

# Crear entorno virtual
if [ ! -d "venv" ]; then
    print_info "Creando entorno virtual..."
    python3 -m venv venv
    print_success "Entorno virtual creado"
else
    print_info "Entorno virtual ya existe"
fi

# Activar entorno virtual
source venv/bin/activate

# Actualizar pip
print_info "Actualizando pip..."
pip install --upgrade pip -q

# Instalar dependencias
print_info "Instalando dependencias Python (esto puede tardar varios minutos)..."
pip install -r requirements.txt -q
print_success "Dependencias Python instaladas"

# Descargar modelo spaCy
echo ""
print_info "Descargando modelo spaCy español (esto puede tardar)..."
python -m spacy download es_core_news_lg
print_success "Modelo spaCy instalado"

cd ..

# Resumen
echo ""
echo "✨ Setup completado exitosamente"
echo ""
echo "Próximos pasos:"
echo "  1. Ejecutar en modo desarrollo:"
echo "     npm run dev"
echo ""
echo "  2. Compilar para producción:"
echo "     npm run build"
echo "     npm run package:mac    # macOS"
echo ""
echo "  3. Ejecutar tests:"
echo "     npm test                # Frontend"
echo "     npm run test:backend    # Backend"
echo ""
echo "📖 Ver docs/QUICKSTART.md para más información"
echo ""
