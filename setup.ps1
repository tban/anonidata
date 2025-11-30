# Setup script para AnoniData
# Windows PowerShell

$ErrorActionPreference = "Stop"

Write-Host "🚀 AnoniData Setup Script" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan
Write-Host ""

# Función para imprimir mensajes
function Print-Success {
    param($Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Print-Error {
    param($Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Print-Warning {
    param($Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Print-Info {
    param($Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

# Verificar Node.js
Write-Host "Verificando Node.js..."
try {
    $nodeVersion = node --version
    if ($nodeVersion -match "v(\d+)\.") {
        $majorVersion = [int]$Matches[1]
        if ($majorVersion -lt 18) {
            Print-Error "Node.js versión 18+ requerida (tienes: $nodeVersion)"
            exit 1
        }
    }
    Print-Success "Node.js $nodeVersion"
} catch {
    Print-Error "Node.js no está instalado"
    Write-Host "Por favor instalar desde: https://nodejs.org/"
    exit 1
}

# Verificar Python
Write-Host ""
Write-Host "Verificando Python..."
try {
    $pythonVersion = python --version
    Print-Success "Python $pythonVersion"
} catch {
    Print-Error "Python no está instalado"
    Write-Host "Por favor instalar desde: https://www.python.org/"
    exit 1
}

# Verificar Tesseract
Write-Host ""
Write-Host "Verificando Tesseract..."
try {
    $tesseractVersion = tesseract --version 2>&1 | Select-Object -First 1
    Print-Success "Tesseract instalado"
} catch {
    Print-Warning "Tesseract OCR no está instalado"
    Write-Host "Por favor instalar desde: https://github.com/UB-Mannheim/tesseract/wiki"
    Write-Host "Luego agregar al PATH: C:\Program Files\Tesseract-OCR"
    Print-Info "Puedes continuar con el setup, pero OCR no funcionará sin Tesseract"
}

# Instalar dependencias Node.js
Write-Host ""
Write-Host "Instalando dependencias Node.js..."
npm install
Print-Success "Dependencias Node.js instaladas"

# Configurar backend Python
Write-Host ""
Write-Host "Configurando backend Python..."

Set-Location backend

# Crear entorno virtual
if (-not (Test-Path "venv")) {
    Print-Info "Creando entorno virtual..."
    python -m venv venv
    Print-Success "Entorno virtual creado"
} else {
    Print-Info "Entorno virtual ya existe"
}

# Activar entorno virtual
& .\venv\Scripts\Activate.ps1

# Actualizar pip
Print-Info "Actualizando pip..."
python -m pip install --upgrade pip -q

# Instalar dependencias
Print-Info "Instalando dependencias Python (esto puede tardar varios minutos)..."
pip install -r requirements.txt -q
Print-Success "Dependencias Python instaladas"

# Descargar modelo spaCy
Write-Host ""
Print-Info "Descargando modelo spaCy español (esto puede tardar)..."
python -m spacy download es_core_news_lg
Print-Success "Modelo spaCy instalado"

Set-Location ..

# Resumen
Write-Host ""
Write-Host "✨ Setup completado exitosamente" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:"
Write-Host "  1. Ejecutar en modo desarrollo:"
Write-Host "     npm run dev"
Write-Host ""
Write-Host "  2. Compilar para producción:"
Write-Host "     npm run build"
Write-Host "     npm run package:win    # Windows"
Write-Host ""
Write-Host "  3. Ejecutar tests:"
Write-Host "     npm test                # Frontend"
Write-Host "     npm run test:backend    # Backend"
Write-Host ""
Write-Host "📖 Ver docs\QUICKSTART.md para más información"
Write-Host ""
