# AnoniData

**Aplicación de escritorio para anonimización de PDFs conforme a RGPD**

## Características

- ✅ Procesamiento 100% local (sin conexión a internet)
- ✅ Detección automática de datos personales:
  - DNI/NIE españoles
  - Nombres propios
  - Direcciones
  - Teléfonos y emails
  - IBAN
  - Firmas manuscritas
  - Códigos QR
- ✅ Anonimización irreversible
- ✅ Procesamiento batch
- ✅ Multiplataforma: Windows, macOS (Intel + Apple Silicon)
- ✅ Zero data retention
- ✅ Logs sanitizados

## Tecnologías

### Frontend
- Electron 28
- React 18 + TypeScript
- TailwindCSS
- Zustand (state management)

### Backend
- Python 3.11+
- PyMuPDF (procesamiento PDF)
- Tesseract + EasyOCR (OCR)
- spaCy (NLP en español)
- OpenCV (detección visual)

## Instalación para Desarrollo

### Requisitos previos

**Node.js y npm:**
```bash
node --version  # v18+
npm --version   # v9+
```

**Python:**
```bash
python --version  # 3.11+
```

**Tesseract OCR:**
- macOS: `brew install tesseract tesseract-lang`
- Windows: Descargar desde https://github.com/UB-Mannheim/tesseract/wiki

### Setup

1. **Clonar repositorio:**
```bash
git clone https://github.com/your-org/anonidata.git
cd anonidata
```

2. **Instalar dependencias Node.js:**
```bash
npm install
```

3. **Configurar entorno Python:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg
cd ..
```

4. **Ejecutar en modo desarrollo:**
```bash
npm run dev
```

## Distribución

### Windows (.exe)
```bash
npm run package:win
```
Salida: `release/AnoniData-Setup-1.0.0.exe`

### macOS (.dmg)
```bash
npm run package:mac
```
Salida: `release/AnoniData-1.0.0-universal.dmg`

## Arquitectura

```
┌─────────────────────────────────────┐
│   Electron (UI + File Management)   │
└─────────────────┬───────────────────┘
                  │ IPC
┌─────────────────┴───────────────────┐
│   Python Backend (PII Detection)    │
│   ├── PDF Parser (PyMuPDF)          │
│   ├── OCR Engine (Tesseract)        │
│   ├── PII Detector (spaCy + Regex)  │
│   └── Anonymizer (irreversible)     │
└─────────────────────────────────────┘
```

## Uso

1. Arrastra archivos PDF a la ventana
2. Haz clic en "Procesar"
3. Espera a que finalice el procesamiento
4. Los archivos anonimizados se guardan con sufijo `_anonimizado.pdf`

## Seguridad y RGPD

- ✅ **Procesamiento local:** Ningún dato sale de tu ordenador
- ✅ **Zero retention:** Archivos temporales eliminados automáticamente
- ✅ **No telemetría:** Sin analytics ni tracking
- ✅ **Metadata cleaning:** Elimina metadatos del PDF
- ✅ **Logs sanitizados:** No contienen información sensible

## Licencia

MIT License - Ver [LICENSE](LICENSE)

## Soporte

Para bugs y feature requests: https://github.com/your-org/anonidata/issues
