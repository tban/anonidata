# Guía de Instalación - AnoniData

## Requisitos del Sistema

### Para Desarrollo

**macOS:**
- macOS 10.15 (Catalina) o superior
- Xcode Command Line Tools
- Homebrew

**Windows:**
- Windows 10/11 (64-bit)
- Visual Studio Build Tools

**Ambos:**
- Node.js 18+ y npm 9+
- Python 3.11+
- Git

---

## Instalación Paso a Paso

### 1. Instalar Node.js

**macOS:**
```bash
brew install node
```

**Windows:**
Descargar desde: https://nodejs.org/

Verificar:
```bash
node --version  # Debe ser v18+
npm --version   # Debe ser v9+
```

### 2. Instalar Python

**macOS:**
```bash
brew install python@3.11
```

**Windows:**
Descargar desde: https://www.python.org/downloads/

Verificar:
```bash
python3 --version  # Debe ser 3.11+
```

### 3. Instalar Tesseract OCR

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Windows:**
1. Descargar instalador desde: https://github.com/UB-Mannheim/tesseract/wiki
2. Instalar en `C:\Program Files\Tesseract-OCR`
3. Agregar al PATH del sistema

Verificar:
```bash
tesseract --version
```

### 4. Clonar Repositorio

```bash
git clone https://github.com/your-org/anonidata.git
cd anonidata
```

### 5. Instalar Dependencias Node.js

```bash
npm install
```

Esto instalará todas las dependencias de Electron y React.

### 6. Configurar Backend Python

```bash
cd backend
python3 -m venv venv

# Activar entorno virtual
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Descargar modelo spaCy español
python -m spacy download es_core_news_lg

cd ..
```

### 7. Ejecutar en Modo Desarrollo

Desde el directorio raíz del proyecto:

```bash
npm run dev
```

Esto iniciará:
- Servidor de desarrollo Vite (React) en puerto 3000
- Proceso Electron
- Backend Python (lanzado por Electron)

---

## Construcción para Producción

### Compilar Backend Python

```bash
cd backend
source venv/bin/activate  # o venv\Scripts\activate en Windows

pyinstaller anonidata-backend.spec

cd ..
```

### Compilar Aplicación Electron

**Para macOS (universal):**
```bash
npm run build
npm run package:mac
```

Resultado: `release/AnoniData-1.0.0-universal.dmg`

**Para Windows:**
```bash
npm run build
npm run package:win
```

Resultado: `release/AnoniData-Setup-1.0.0.exe`

**Para ambos:**
```bash
npm run build
npm run package:all
```

---

## Solución de Problemas

### Error: "Tesseract no encontrado"

**macOS:**
```bash
brew reinstall tesseract
```

**Windows:**
- Verificar que `C:\Program Files\Tesseract-OCR` está en PATH
- Reiniciar terminal/IDE

### Error: "spaCy model not found"

```bash
cd backend
source venv/bin/activate
python -m spacy download es_core_news_lg
```

### Error: "Module not found" en Python

Verificar que el entorno virtual está activado:
```bash
which python  # macOS/Linux
where python  # Windows
```

Debe apuntar a `backend/venv/bin/python`

### Error al compilar para macOS: "No identity found"

Para desarrollo local, puedes deshabilitar la firma:
```json
// En package.json, en build.mac:
"identity": null
```

### Permisos en macOS

Si aparece "App is damaged":
```bash
xattr -cr /Applications/AnoniData.app
```

---

## Desarrollo

### Ejecutar Tests

**Backend Python:**
```bash
cd backend
source venv/bin/activate
pytest
```

**Frontend:**
```bash
npm test
```

### Linting y Formato

```bash
# JavaScript/TypeScript
npm run lint
npm run format

# Python
cd backend
black .
flake8 .
```

---

## Notas de Plataforma

### macOS Apple Silicon (M1/M2/M3)

El build universal funciona en ambas arquitecturas (Intel y Apple Silicon).

Si necesitas build específico:
```bash
npm run package:mac -- --arch arm64  # Solo Apple Silicon
npm run package:mac -- --arch x64    # Solo Intel
```

### Windows

El instalador NSIS permite:
- Instalación personalizada
- Creación de acceso directo en escritorio
- Desinstalación estándar

### Linux (Experimental)

```bash
npm run package -- --linux
```

Genera AppImage y .deb

---

## Recursos Adicionales

- [Documentación Electron](https://www.electronjs.org/docs)
- [PyMuPDF Docs](https://pymupdf.readthedocs.io/)
- [spaCy Docs](https://spacy.io/usage)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## Soporte

Para problemas, crear issue en:
https://github.com/your-org/anonidata/issues
