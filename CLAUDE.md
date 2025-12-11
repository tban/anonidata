# AnoniData - Guía para Claude Code

> **⚠️ IMPORTANTE**: SIEMPRE optimizar el tamaño del ejecutable sin perder funcionalidad. Revisar y eliminar dependencias innecesarias en cada build.

## 📋 Descripción del Proyecto

AnoniData es una aplicación de escritorio para anonimización de documentos PDF, diseñada específicamente para detectar y redactar datos personales (PII) según normativa española y europea (RGPD).

**Stack Tecnológico:**
- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS
- **Main Process**: Electron + TypeScript
- **Backend**: Python 3.13 con PyMuPDF, spaCy, OpenCV, Pillow
- **Empaquetado**: Electron Forge (arm64 optimizado)
- **Control de versiones**: Git + GitHub

**Distribución Optimizada:**
- **DMG arm64**: 312 MB (reducido 55% desde 695 MB)
- **Aplicación**: 511 MB (reducido 49% desde ~1 GB)
- **Backend**: 92 MB (reducido 62% desde ~240 MB)

## 🏗️ Arquitectura del Proyecto

```
anonidata/
├── src/
│   ├── main/           # Proceso principal de Electron (Node.js)
│   ├── renderer/       # Interfaz de usuario (React)
│   │   ├── components/ # Componentes reutilizables
│   │   ├── screens/    # Pantallas principales
│   │   ├── types/      # Definiciones TypeScript
│   │   └── utils/      # Utilidades (coordenadas PDF, etc)
│   └── preload/        # Script de precarga (contextBridge)
├── backend/            # Motor de detección y anonimización (Python)
│   ├── core/           # Configuración y modelos
│   ├── detectors/      # Detectores de PII (regex, NER, visual)
│   ├── processors/     # Procesamiento de PDF y anonimización
│   └── config/         # Reglas de anonimización JSON
├── dist/               # Código compilado
└── out/                # Aplicación empaquetada
```

## 🔄 Flujo de Trabajo Principal

### 1. Desarrollo Local
```bash
# Terminal 1: Desarrollo del renderer (React)
npm run dev:renderer

# Terminal 2: Desarrollo del main (Electron)
npm run dev:main
```

### 2. Compilación Completa
**IMPORTANTE: Siempre compilar después de cambios significativos**

```bash
# Compilar todo el proyecto
npm run build

# O por separado:
npm run build:renderer  # React/Vite (actualiza __BUILD_DATE__)
npm run build:main      # TypeScript main process
npm run build:backend   # PyInstaller (Python → ejecutable)
```

### 3. Empaquetado para Distribución
```bash
# Generar aplicación empaquetada (.app en macOS)
npm run make

# Resultado: out/anonidata-darwin-arm64/anonidata.app
```

### 4. Testing
```bash
# Tests del backend
npm run test:backend

# Ejecutar aplicación empaquetada localmente
open out/anonidata-darwin-arm64/anonidata.app
```

## 📝 Reglas de Código y Estilo

### General
- **NO usar emojis** en el código a menos que el usuario lo solicite explícitamente
- **SIEMPRE optimizar el tamaño del ejecutable** sin perder funcionalidad
- Mantener consistencia con el estilo existente
- Usar nombres descriptivos en inglés para código, español para UI
- Comentarios en español para facilitar colaboración

### Frontend (React + TypeScript)
- Componentes funcionales con hooks
- TailwindCSS para estilos (no CSS inline ni styled-components)
- Tipos explícitos en TypeScript (evitar `any`)
- Botones principales: `bg-blue-600 hover:bg-blue-700 text-white`
- Botones secundarios: `bg-gray-200 hover:bg-gray-300 text-gray-700`

### Backend (Python)
- Type hints en todas las funciones
- Usar `loguru` para logging
- Calcular **bboxes precisas** usando `page.search_for()` para todas las detecciones
- Validar DNI/NIE con algoritmo de dígito de control
- Patrones regex en `backend/detectors/regex_patterns.py`
- Reglas configurables en `backend/config/anonymization_rules.json`

### IPC (Electron)
- Handlers en `main.ts` con prefijo descriptivo (`dialog:`, `process:`, etc.)
- Exponer API segura mediante `contextBridge` en `preload.ts`
- Usar tipos TypeScript para requests/responses
- Parsing línea por línea para salidas JSON del backend Python

## 🎯 Detección de PII

### Tipos de PII Soportados
1. **DNI/NIE**: Regex + validación de letra de control
   - Formatos: `12345678A`, `12345678-A`, `12.345.678A`
2. **Nombres**: NER con spaCy + reglas para prefijos (D./Dña./D.ª)
3. **Emails**: Regex con bbox precisa
4. **Teléfonos**: Regex español (+34, 6XX, etc.)
5. **Direcciones**: Keywords + regex (Calle, C/, Avenida, etc.)
6. **Firmas**: Detección visual con OpenCV
7. **Códigos QR**: Detección visual con OpenCV
8. **Selección manual**: Rectángulos dibujados por usuario

### Flujos de Detección
1. **Automático**: Procesa y anonimiza directamente
2. **Manual/Revisión**: Detecta → Muestra en visor → Usuario aprueba/rechaza → Anonimiza

## 🔧 Comandos Importantes

### Compilación Backend
```bash
cd backend
venv/bin/pyinstaller --clean --onefile --console --name anonidata-backend --add-data 'config:config' main.py
cp dist/anonidata-backend ../dist/
```

**NOTA CRÍTICA**: Usar `--console` en lugar de `--noconsole` en macOS para evitar error ENOTDIR.

### Git Workflow
```bash
# Después de cambios importantes
git add [archivos]
git commit -m "tipo: descripción

- Detalle 1
- Detalle 2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
```

**Tipos de commit**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

## 🚨 Problemas Comunes y Soluciones

### Backend no detecta cambios en app empaquetada
**Causa**: Backend compilado desactualizado
**Solución**: Ejecutar `npm run build:backend` y copiar a `dist/`

### IPC timeout / "Se queda procesando"
**Causa**: Frontend no parsea correctamente JSON mezclado con logs
**Solución**: Parsing línea por línea con flag `resolved` en handlers

### DNI con guión no se detecta
**Causa**: Backend empaquetado tiene versión antigua del regex
**Solución**: Recompilar backend con últimos cambios

### Email captura texto extra
**Causa**: Bbox usa bloque completo en lugar de bbox precisa
**Solución**: Usar `page.search_for(match)` para bbox exacta

### App no cierra en macOS
**Causa**: Comportamiento por defecto de Electron en macOS
**Solución**: Forzar `app.quit()` en evento `window-all-closed`

### "Error al cargar el PDF" en pantalla de revisión manual
**Causa**: `fetch()` con `file://` URLs no funciona en Electron por restricciones de seguridad
**Solución**: Usar handler IPC para leer archivos desde el proceso principal
```typescript
// En preload.ts - Agregar a AnoniDataAPI
utils: {
  readPdfFile: (filePath: string) => Promise<ArrayBuffer>;
}

// En main.ts - Agregar handler IPC
ipcMain.handle('utils:readPdfFile', async (_event, filePath) => {
  const fs = require('fs').promises;
  const buffer = await fs.readFile(filePath);
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
});

// En PDFViewer.tsx - Usar IPC en lugar de fetch
const arrayBuffer = await window.anonidata.utils.readPdfFile(pdfPath);
const doc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
```

## 📊 Testing y Validación

### Verificar Detecciones
1. Procesar PDF de prueba
2. Verificar que detecta:
   - DNI con guión: `43768143-V` ✓
   - Nombres con prefijo: `D.ª María García López` ✓
   - Email preciso: Solo `email@example.com`, no texto extra ✓
3. Verificar bboxes en visor de revisión

### Verificar Build Date
- Abrir "Acerca de" en la aplicación
- Fecha debe ser la del último build (no estática)
- Actualiza automáticamente al ejecutar `npm run build:renderer`

## 🎨 Convenciones de UI

### Colores de Detecciones
```typescript
DNI/NIE: '#ef4444'        // red
PERSON: '#3b82f6'         // blue
ADDRESS: '#10b981'        // green
PHONE: '#f59e0b'          // amber
EMAIL: '#8b5cf6'          // purple
SIGNATURE: '#6366f1'      // indigo
MANUAL: '#f59e0b'         // amber
```

### Botones
- **Primarios**: Azul (`bg-blue-600`)
- **Secundarios**: Gris (`bg-gray-200`)
- **Acciones destructivas**: Rojo (`bg-red-600`)
- **Deshabilitados**: `disabled:bg-gray-400`

### Texto de Botones
- **Específico y descriptivo**: "Revisión manual", no "Revisar"
- **Sin emojis** a menos que se solicite
- **Tamaño**: `text-xs` para botones pequeños, `font-semibold` para principales

## 🔐 Seguridad y Privacidad

1. **No enviar datos a servidores**: Todo el procesamiento es local
2. **Borrar metadatos**: PDFs generados tienen metadatos limpios
3. **Redacción irreversible**: Usar `apply_redactions()` para eliminar texto permanentemente
4. **Anonimización no reversible**: No almacenar texto original en PDFs anonimizados

## 📦 Distribución

### macOS arm64 (Apple Silicon)
```bash
npm run make

# Resultados:
# - DMG: out/make/anonidata-1.0.0-arm64.dmg (312 MB)
# - ZIP: out/make/zip/darwin/arm64/anonidata-darwin-arm64-1.0.0.zip
```

### Recursos Necesarios
- Backend compilado optimizado: `dist/anonidata-backend` (92 MB, arm64)
- Configuración: `backend/config/anonymization_rules.json`
- Modelo spaCy: `es_core_news_sm` (incluido en PyInstaller)
- Icono personalizado: `build/icon.icns`

## 🎯 Checklist Antes de Commit/Push

- [ ] Verificar optimización: Auditar dependencias innecesarias
- [ ] Compilar renderer (`npm run build:renderer`)
- [ ] Compilar main (`npm run build:main`)
- [ ] Compilar backend si hay cambios en Python (`venv/bin/pyinstaller --clean anonidata-backend.spec`)
- [ ] Verificar que no hay errores TypeScript
- [ ] Verificar que fecha de compilación se actualiza
- [ ] Verificar tamaño del DMG (debe ser ~312 MB para arm64)
- [ ] Tests pasan (si aplica)
- [ ] Probar en aplicación empaquetada (`npm run make`)
- [ ] Commit con mensaje descriptivo
- [ ] Push a GitHub

## 🚀 Workflow de Cambios Típicos

### 1. Cambio en UI (React)
```bash
# Editar src/renderer/**/*.tsx
npm run build:renderer
npm run build:main
npm run make
# Verificar en app empaquetada
git add src/renderer/
git commit -m "fix: Descripción del cambio"
git push
```

### 2. Cambio en Detección (Python)
```bash
# Editar backend/**/*.py
cd backend
venv/bin/pyinstaller --clean anonidata-backend.spec  # Usar spec optimizado
rm -rf ../dist/anonidata-backend
cp dist/anonidata-backend ../dist/
ls -lh dist/anonidata-backend  # Verificar tamaño (~92 MB)
cd ..
npm run make
# Verificar detección funciona y tamaño del DMG
git add backend/
git commit -m "feat: Descripción del cambio"
git push
```

### 3. Cambio en IPC/Main Process
```bash
# Editar src/main/**/*.ts o src/preload/**/*.ts
npm run build:main
npm run make
# Verificar comunicación funciona
git add src/main/ src/preload/
git commit -m "fix: Descripción del cambio"
git push
```

## 🗜️ Optimización de Tamaño

**PRINCIPIO FUNDAMENTAL**: SIEMPRE optimizar el tamaño del ejecutable sin perder funcionalidad. Cada build debe ser revisado para eliminar dependencias innecesarias.

### Estado Actual (Optimizado)
- **DMG arm64**: **312 MB**
- **App empaquetada**: **511 MB**
- **Backend Python**: **92 MB**

### Optimizaciones Aplicadas

#### 1. Dependencias Python Eliminadas ✅

**Archivo**: `backend/requirements.txt`

Dependencias pesadas removidas:
- `torch` (2.9.1) - **MUY PESADO** - NO usado en código
- `transformers` (4.57.3) - **MUY PESADO** - NO usado
- `torchvision` (0.24.1) - **MUY PESADO** - NO usado
- `scipy` (1.16.3) - NO usado
- `es_core_news_lg` (3.8.0) - Modelo grande reemplazado por `sm`

```bash
cd backend
venv/bin/pip uninstall -y torch torchvision transformers scipy es-core-news-lg
venv/bin/pip freeze > requirements.txt
```

**Impacto real**: -148 MB en backend (-62%)

#### 2. PyInstaller Optimizado ✅

**Archivo**: `backend/anonidata-backend.spec`

```python
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', 'mypy', 'black', 'flake8', 'mypy_extensions',
        'unittest', 'test', 'tests', '_pytest',
        'coverage', 'pytest_cov',
        'torch', 'transformers', 'scipy', 'torchvision',
    ],
    noarchive=False,
    optimize=2,  # ← Bytecode optimizado
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='anonidata-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,      # ← Símbolos debug removidos
    upx=False,       # ← False en macOS (evita ENOTDIR)
    console=True,
    target_arch='arm64',  # ← Solo arm64
)
```

#### 3. Electron Forge Optimizado ✅

**Archivo**: `forge.config.js`

```javascript
module.exports = {
  packagerConfig: {
    icon: './build/icon',
    arch: 'arm64',          // Solo arm64
    platform: 'darwin',     // Solo macOS
    asar: {
      unpack: '*.node'
    },
    ignore: [
      /^\/backend/,
      /^\/test/,
      /^\/out/,
      /^\/build/,
      /^\/release/,
      /^\/resources/,
      /\.pyc$/,
      /\.spec$/
    ],
    extraResource: [
      'backend/dist/anonidata-backend'
    ],
  },
  makers: [
    {
      name: '@electron-forge/maker-dmg',  // DMG para macOS
      platforms: ['darwin'],
      config: {
        format: 'ULFO',
        icon: './build/icon.icns'
      }
    },
    {
      name: '@electron-forge/maker-zip',  // ZIP alternativo
      platforms: ['darwin'],
    },
    // Removidos: squirrel, deb, rpm
  ],
}
```

### Workflow de Optimización

```bash
# 1. Auditar dependencias Python
cd backend
venv/bin/pip list --format=columns | sort -k2 -rh

# 2. Verificar imports en código
grep -r "^import\|^from" --include="*.py" | grep -E "(torch|transformers|scipy)"

# 3. Desinstalar dependencias no usadas
venv/bin/pip uninstall -y torch transformers scipy torchvision es-core-news-lg

# 4. Actualizar requirements
venv/bin/pip freeze > requirements.txt

# 5. Editar anonidata-backend.spec (añadir excludes, optimize=2, strip=True)

# 6. Recompilar backend
venv/bin/pyinstaller --clean anonidata-backend.spec

# 7. Copiar a dist del proyecto
rm -rf ../dist/anonidata-backend
cp dist/anonidata-backend ../dist/

# 8. Verificar tamaño
ls -lh dist/anonidata-backend

# 9. Generar DMG optimizado
cd ..
npm run make

# 10. Verificar tamaños finales
ls -lh out/make/anonidata-*.dmg
du -sh out/anonidata-darwin-arm64/anonidata.app
```

### Checklist de Optimización

- [x] Auditar `requirements.txt` y remover dependencias no usadas
- [x] Verificar imports en código Python
- [x] Desinstalar `torch`, `transformers`, `scipy`, `torchvision`
- [x] Remover `es_core_news_lg`, mantener solo `es_core_news_sm`
- [x] Editar `.spec`: `strip=True`, `optimize=2`, `target_arch='arm64'`, `excludes`
- [x] Configurar `forge.config.js`: solo arm64, solo macOS
- [x] Recompilar backend optimizado
- [x] Verificar funcionalidad completa
- [x] Medir y documentar reducciones

### Comandos de Verificación

```bash
# Ver dependencias Python ordenadas por tamaño
cd backend
venv/bin/pip list --format=columns | sort -k2 -rh

# Ver modelo spaCy instalado
venv/bin/python -m spacy info

# Ver tamaño del backend compilado
ls -lh dist/anonidata-backend
file dist/anonidata-backend  # Verificar arquitectura

# Ver tamaño de la app empaquetada
du -sh out/anonidata-darwin-arm64/anonidata.app

# Ver tamaño del DMG
ls -lh out/make/anonidata-1.0.0-arm64.dmg
```

### Resultados de Optimización

| Componente | Antes | Después | Reducción |
|------------|-------|---------|-----------|
| **DMG arm64** | 695 MB | **312 MB** | **-383 MB (-55%)** |
| **App empaquetada** | ~1.0 GB | **511 MB** | **-489 MB (-49%)** |
| **Backend Python** | ~240 MB | **92 MB** | **-148 MB (-62%)** |

### Advertencias Críticas

1. **NO remover**: `PyMuPDF`, `spaCy`, `OpenCV`, `Pillow`, `numpy` - son críticas
2. **Mantener**: `es_core_news_sm` - modelo óptimo para NER español
3. **Probar siempre**: Ejecutar app empaquetada y verificar TODAS las funcionalidades
4. **Arquitectura**: Solo arm64 para M1/M2/M3 (no universal2)
5. **UPX**: Mantener en `False` en macOS (evita errores ENOTDIR)

## 📚 Recursos Útiles

- **Electron Docs**: https://www.electronjs.org/docs
- **PyMuPDF Docs**: https://pymupdf.readthedocs.io/
- **spaCy Docs**: https://spacy.io/usage
- **TailwindCSS**: https://tailwindcss.com/docs
- **React Docs**: https://react.dev/

## 🎓 Notas Finales

1. **SIEMPRE optimizar el tamaño del ejecutable sin perder funcionalidad**: Cada build debe minimizar dependencias innecesarias
2. **Siempre compilar antes de empaquetar**: Los cambios en código fuente no se reflejan en el `.app` hasta compilar
3. **Backend es crítico**: Cualquier cambio en Python requiere recompilar con PyInstaller optimizado
4. **Fecha de build es automática**: Se actualiza al compilar renderer con Vite
5. **Usar git descriptivamente**: Commits claros facilitan debugging y rollbacks
6. **Priorizar bboxes precisas**: Mejorar la experiencia de usuario en revisión manual
7. **Solo arm64 para macOS**: Configurado para Apple Silicon (M1/M2/M3)
8. **IPC para operaciones de archivos**: NUNCA usar `fetch()` con `file://` en Electron, siempre usar handlers IPC (ej: `readPdfFile`)

---

**Última actualización**: 10 Diciembre 2025
**Versión del proyecto**: 1.0.0 (arm64 optimizado)
