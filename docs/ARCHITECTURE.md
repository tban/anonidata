# Arquitectura de AnoniData

## Visión General

AnoniData es una aplicación de escritorio multiplataforma que procesa PDFs localmente para anonimizar datos personales conforme a RGPD.

## Stack Tecnológico

### Frontend
- **Electron 28**: Framework de aplicación de escritorio
- **React 18**: UI library
- **TypeScript**: Type safety
- **TailwindCSS**: Styling
- **Zustand**: State management (opcional)

### Backend
- **Python 3.11+**: Lenguaje principal de procesamiento
- **PyMuPDF (fitz)**: Manipulación de PDFs
- **Tesseract**: OCR engine
- **spaCy**: NLP para detección de entidades
- **OpenCV**: Procesamiento de imágenes
- **pyzbar**: Detección de códigos QR/barras

---

## Arquitectura de Capas

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Electron Renderer (React)                             │ │
│  │  - UI Components                                       │ │
│  │  - Drag & Drop Zone                                    │ │
│  │  - Progress Display                                    │ │
│  │  - Results Viewer                                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↕ IPC
┌─────────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Electron Main Process                                 │ │
│  │  - IPC Handlers                                        │ │
│  │  - File System Access                                  │ │
│  │  - Python Process Manager                              │ │
│  │  - Security Policies                                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                      ↕ Child Process / stdin/stdout
┌─────────────────────────────────────────────────────────────┐
│                   PROCESSING LAYER                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Python Backend                                        │ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Core Modules                                    │ │ │
│  │  │  - PDFProcessor (orchestrator)                   │ │ │
│  │  │  - Settings & Config                             │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Processors                                       │ │ │
│  │  │  - PDFParser: Extrae texto/imágenes              │ │ │
│  │  │  - OCREngine: Tesseract integration              │ │ │
│  │  │  - Anonymizer: Redacción irreversible            │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Detectors                                        │ │ │
│  │  │  - RegexPatterns: DNI/NIE/Email/Phone            │ │ │
│  │  │  - PIIDetector: NER con spaCy                    │ │ │
│  │  │  - VisualDetector: Firmas/QR/Sellos             │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Utilities                                        │ │ │
│  │  │  - FileManager: Validación/limpieza              │ │ │
│  │  │  - LoggingConfig: Logs sanitizados               │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                   STORAGE LAYER                              │
│  - Local File System (user-selected PDFs)                   │
│  - Temporary Directory (auto-cleanup)                       │
│  - Logs Directory (sanitized logs)                          │
│  - Config Store (Electron Store)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Flujo de Datos

### 1. Carga de Archivos

```
User Drops PDFs
      ↓
React Component (useDropzone)
      ↓
State Update (files list)
      ↓
Display Pending Status
```

### 2. Procesamiento

```
User Clicks "Anonimizar"
      ↓
React → IPC invoke('process:anonymize', filePaths)
      ↓
Electron Main Process
      ↓
Spawn/Reuse Python Process
      ↓
Send JSON via stdin: {action: 'anonymize', files: [...]}
      ↓
Python Backend receives request
      ↓
For each file:
  ├─ PDFParser.parse() → PDFData
  ├─ OCREngine.process() → OCRData
  ├─ PIIDetector.detect() → PIIMatch[]
  ├─ Anonymizer.anonymize() → output_path
  └─ FileManager.clean_metadata()
      ↓
Python sends result via stdout (JSON)
      ↓
Electron Main receives response
      ↓
IPC returns result to Renderer
      ↓
React updates UI with results
```

---

## Módulos Principales

### Frontend (src/renderer/)

**App.tsx**
- Componente principal
- Manejo de drag & drop
- Estado de archivos
- Llamadas IPC

**main.tsx**
- Entry point de React
- Monta aplicación en DOM

### Electron Main (src/main/)

**main.ts**
- Crea ventana principal
- Configura seguridad (CSP, request blocking)
- Maneja ciclo de vida de app
- Lanza backend Python
- Implementa IPC handlers

### Electron Preload (src/preload/)

**preload.ts**
- Expone API segura a renderer
- Bridge entre main y renderer
- Type-safe con TypeScript

### Backend Python (backend/)

**main.py**
- Entry point del backend
- Loop stdin/stdout
- Procesa requests JSON
- Maneja errores globales

**core/processor.py**
- Orquestador principal
- Coordina todos los módulos
- Manejo de errores por archivo
- Genera estadísticas

**processors/pdf_parser.py**
- Extrae texto vectorial (bloques con coordenadas)
- Extrae imágenes embebidas
- Obtiene metadatos
- Usa PyMuPDF (fitz)

**processors/ocr_engine.py**
- Detecta páginas sin texto
- Aplica Tesseract OCR
- Retorna texto con coordenadas
- Maneja imágenes grandes

**detectors/pii_detector.py**
- Coordina detección multi-fuente
- Combina regex + NER + visual
- Elimina duplicados
- Retorna lista unificada de PIIMatch

**detectors/regex_patterns.py**
- Patrones regex españoles
- Validación de DNI/NIE (letra de control)
- Teléfonos, emails, IBAN

**detectors/visual_detector.py**
- Detecta QR codes (pyzbar)
- Detecta firmas (heurística OpenCV)
- Para producción: entrenar modelo ML

**processors/anonymizer.py**
- Redacción irreversible
- 3 estrategias: black_box, pixelate, blur
- Usa redact annotations de PyMuPDF
- Elimina contenido subyacente

**utils/file_manager.py**
- Validación de PDFs
- Limpieza de metadatos (pikepdf)
- Generación de rutas de salida
- Cleanup de temporales

**utils/logging_config.py**
- Configuración de loguru
- Sanitización automática de PII en logs
- Rotación de archivos
- Niveles configurables

---

## Seguridad y RGPD

### Procesamiento Local

```typescript
// main.ts - Bloqueo de requests externas
session.defaultSession.webRequest.onBeforeRequest(
  { urls: ['*://*/*'] },
  (details, callback) => {
    if (details.url.startsWith('file://') ||
        details.url.startsWith('http://localhost')) {
      callback({});
    } else {
      callback({ cancel: true });
    }
  }
);
```

### Limpieza de Metadatos

```python
# file_manager.py
with pikepdf.open(file_path, allow_overwriting_input=True) as pdf:
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta.clear()
        meta['dc:creator'] = 'AnoniData'
```

### Logs Sanitizados

```python
# logging_config.py
def sanitize_message(message: str) -> str:
    message = re.sub(r'\b[0-9]{8}[A-Z]\b', '[DNI_REDACTED]', message)
    message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                     '[EMAIL_REDACTED]', message)
    return message
```

### Redacción Irreversible

```python
# anonymizer.py
# Método más seguro: usa redact annotations nativas
annot = page.add_redact_annot(rect)
page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
# Elimina el contenido subyacente, no solo lo cubre
```

---

## Extensibilidad

### Plugin System (Futuro)

```python
# Arquitectura para plugins de detección
class PIIDetectorPlugin(ABC):
    @abstractmethod
    def detect(self, text: str, image: np.ndarray) -> List[PIIMatch]:
        pass

# Registro dinámico
plugin_manager.register(CustomDNIDetector())
plugin_manager.register(HealthDataDetector())
```

### API REST (Fase 2)

```python
# FastAPI integration
@app.post("/api/v1/anonymize")
async def anonymize_endpoint(files: List[UploadFile]):
    # Reutilizar mismo core de procesamiento
    processor = PDFProcessor(settings)
    results = processor.process_batch(files)
    return results
```

### Configuración Avanzada

```json
// Reglas personalizables
{
  "rules": [
    {
      "id": "custom-field",
      "type": "regex",
      "pattern": "Expediente: [A-Z0-9]+",
      "enabled": true,
      "strategy": "black_box"
    }
  ]
}
```

---

## Performance

### Estrategias de Optimización

1. **Procesamiento Paralelo**: Múltiples archivos en paralelo (future)
2. **Lazy Loading**: OCR solo cuando es necesario
3. **Caching**: Resultados de NLP en memoria (dentro de sesión)
4. **Streaming**: Páginas procesadas una a una
5. **Resource Cleanup**: Cierre explícito de documentos

### Métricas

- Tiempo promedio por página: ~2-5 segundos (depende de OCR)
- Memoria: ~200-500MB (varía con tamaño de PDF)
- Tamaño final: Similar al original (compresión aplicada)

---

## Testing

### Niveles de Testing

1. **Unit Tests**: Regex patterns, validaciones
2. **Integration Tests**: Flujo completo de procesamiento
3. **E2E Tests**: Electron app completa (futuro)

### Coverage Objetivo

- Backend: >80%
- Frontend: >70%

---

## Build y Distribución

### Build Process

```
1. npm run build:renderer → Vite builds React app
2. npm run build:main → TypeScript compiles main/preload
3. npm run build:backend → PyInstaller creates binary
4. electron-builder → Package everything
```

### Artifacts

**macOS:**
- `.dmg`: Disk image instalable
- `.zip`: Portable version
- Universal binary (Intel + Apple Silicon)

**Windows:**
- `.exe`: NSIS installer
- Portable `.exe`: Sin instalación

**Linux:**
- `.AppImage`: Portable
- `.deb`: Debian package

---

## Roadmap

### v1.0 (Actual)
- ✅ Procesamiento local
- ✅ Detección PII española
- ✅ Anonimización irreversible
- ✅ Drag & drop UI

### v1.1
- [ ] Batch progress granular
- [ ] Configuración avanzada UI
- [ ] Más idiomas (catalán, euskera, gallego)
- [ ] Mejora detección firmas (ML model)

### v2.0
- [ ] API REST opcional
- [ ] Versión web (on-premise)
- [ ] Plugin system
- [ ] Templates de redacción

### Enterprise
- [ ] Active Directory integration
- [ ] Audit trails avanzados
- [ ] Compliance reports
- [ ] Batch API

---

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para guidelines.

## Licencia

MIT License - Ver [LICENSE](../LICENSE)
