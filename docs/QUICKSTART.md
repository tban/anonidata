# Guía Rápida - AnoniData

## Instalación Express (5 minutos)

### macOS

```bash
# 1. Instalar dependencias del sistema
brew install node python@3.11 tesseract tesseract-lang

# 2. Clonar y entrar al proyecto
git clone https://github.com/your-org/anonidata.git
cd anonidata

# 3. Instalar dependencias Node.js
npm install

# 4. Configurar Python
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg
cd ..

# 5. Ejecutar
npm run dev
```

### Windows (PowerShell)

```powershell
# 1. Instalar Node.js desde https://nodejs.org/
# 2. Instalar Python desde https://www.python.org/downloads/
# 3. Instalar Tesseract desde https://github.com/UB-Mannheim/tesseract/wiki

# 4. Clonar proyecto
git clone https://github.com/your-org/anonidata.git
cd anonidata

# 5. Instalar dependencias Node
npm install

# 6. Configurar Python
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download es_core_news_lg
cd ..

# 7. Ejecutar
npm run dev
```

---

## Uso Básico

1. **Arrastra PDFs** a la ventana de AnoniData
2. **Haz clic en "Anonimizar PDFs"**
3. **Espera** a que termine el procesamiento
4. **Encuentra los archivos** anonimizados en el mismo directorio con sufijo `_anonimizado.pdf`

---

## Datos que Detecta

- ✅ **DNI/NIE** españoles (con validación de letra)
- ✅ **Nombres propios** (usando NLP)
- ✅ **Direcciones**
- ✅ **Teléfonos** (varios formatos)
- ✅ **Emails**
- ✅ **IBAN** españoles
- ✅ **Códigos QR**
- ✅ **Firmas** (detección básica)

---

## Comandos Útiles

```bash
# Desarrollo
npm run dev                 # Modo desarrollo

# Build
npm run build              # Compilar todo
npm run package:mac        # Build para macOS
npm run package:win        # Build para Windows

# Testing
npm test                   # Tests frontend
npm run test:backend       # Tests backend

# Linting
npm run lint               # ESLint
npm run format             # Prettier
```

---

## Estructura de Proyecto

```
anonidata/
├── src/
│   ├── main/           # Electron main process
│   ├── preload/        # Electron preload scripts
│   └── renderer/       # React UI
├── backend/
│   ├── core/           # Procesador principal
│   ├── processors/     # PDF, OCR, Anonymizer
│   ├── detectors/      # PII detection
│   └── utils/          # Utilidades
├── build/              # Assets para build
├── docs/               # Documentación
└── test/               # Tests
```

---

## Solución Rápida de Problemas

**"Tesseract not found"**
```bash
# macOS
brew install tesseract

# Windows: Agregar a PATH
C:\Program Files\Tesseract-OCR
```

**"spaCy model not found"**
```bash
cd backend
source venv/bin/activate
python -m spacy download es_core_news_lg
```

**"Module not found" al ejecutar**
- Verificar que estás en el directorio raíz del proyecto
- Verificar que ejecutaste `npm install`

**La app no inicia en macOS**
```bash
xattr -cr /Applications/AnoniData.app
```

---

## Configuración Avanzada

Editar `backend/core/config.py` para:
- Cambiar estrategia de redacción (black_box, pixelate, blur)
- Habilitar/deshabilitar tipos de detección
- Ajustar nivel de pixelación
- Configurar DPI de OCR

---

## Generar Instalador

### macOS
```bash
npm run build
npm run package:mac

# Resultado:
# release/AnoniData-1.0.0-universal.dmg
```

### Windows
```bash
npm run build
npm run package:win

# Resultado:
# release/AnoniData-Setup-1.0.0.exe
```

---

## Recursos

- 📖 [Documentación Completa](./INSTALLATION.md)
- 🏗️ [Arquitectura](./ARCHITECTURE.md)
- 🐛 [Reportar Bug](https://github.com/your-org/anonidata/issues)

---

## Características RGPD

- 🔒 **100% Local**: Ningún dato sale de tu ordenador
- 🚫 **Sin telemetría**: No enviamos analytics
- 🗑️ **Auto-cleanup**: Archivos temporales eliminados
- 📝 **Logs sanitizados**: Sin datos personales en logs
- ✅ **Anonimización irreversible**: Datos eliminados permanentemente

---

## Contribuir

¿Quieres contribuir? Ver [CONTRIBUTING.md](../CONTRIBUTING.md)

## Licencia

MIT License
