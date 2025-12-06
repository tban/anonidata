# AnoniData - Guía para Claude Code

## 📋 Descripción del Proyecto

AnoniData es una aplicación de escritorio para anonimización de documentos PDF, diseñada específicamente para detectar y redactar datos personales (PII) según normativa española y europea (RGPD).

**Stack Tecnológico:**
- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS
- **Main Process**: Electron + TypeScript
- **Backend**: Python 3.13 con PyMuPDF, spaCy, OpenCV, Pillow
- **Empaquetado**: Electron Forge
- **Control de versiones**: Git + GitHub

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

### macOS
```bash
npm run make
# Resultado: out/make/zip/darwin/arm64/anonidata-darwin-arm64-1.0.0.zip
```

### Recursos Necesarios
- Backend compilado: `dist/anonidata-backend`
- Configuración: `backend/config/anonymization_rules.json`
- Modelo spaCy: `es_core_news_sm` (incluido en PyInstaller)

## 🎯 Checklist Antes de Commit/Push

- [ ] Compilar renderer (`npm run build:renderer`)
- [ ] Compilar main (`npm run build:main`)
- [ ] Compilar backend si hay cambios en Python (`npm run build:backend`)
- [ ] Verificar que no hay errores TypeScript
- [ ] Verificar que fecha de compilación se actualiza
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
venv/bin/pyinstaller --clean --onefile --console --name anonidata-backend --add-data 'config:config' main.py
cp dist/anonidata-backend ../dist/
cd ..
npm run make
# Verificar detección funciona
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

### Problema Actual
La aplicación empaquetada ocupa **~1.0 GB**, principalmente debido a dependencias innecesarias incluidas en el bundle.

### Desglose de Tamaños
- **Backend Python (PyInstaller)**: ~240 MB
- **Electron Framework**: ~255 MB
- **app.asar (código Electron)**: ~516 MB

### Optimizaciones Recomendadas

#### 1. Limpiar Dependencias Python No Usadas
**Archivos**: `backend/requirements.txt`

Remover dependencias instaladas pero no importadas:
- `torch` (373 MB) - NO usado en el código
- `transformers` (55 MB) - NO usado
- `scipy` (72 MB) - NO usado

```bash
# Editar requirements.txt para remover líneas:
# torch
# transformers
# scipy (si no se usa)

cd backend
pip uninstall torch transformers scipy
pip freeze > requirements.txt
```

**Impacto estimado**: 428 MB menos en venv, ~50-100 MB menos en binario final

#### 2. Optimizar PyInstaller

**Archivo**: `backend/anonidata-backend.spec` (auto-generado, editar tras primer build)

```python
# Cambiar en el spec file:
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='anonidata-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # ← CAMBIAR de False a True
    upx=False,   # Mantener False (UPX puede causar problemas en macOS)
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Añadir excludes para herramientas de desarrollo:
a = Analysis(
    ['main.py'],
    # ... otros parámetros
    excludes=['mypy', 'pytest', 'black', 'flake8', 'mypy_extensions',
              'unittest', 'test', 'tests'],
    # ...
)
```

**Impacto estimado**: 15-25 MB menos

#### 3. Verificar Modelo spaCy

El modelo `es_core_news_sm` (~17 MB) es óptimo. Si por error se incluyó `es_core_news_lg` (~600 MB):

```bash
# Verificar modelo instalado
cd backend
venv/bin/python -m spacy info

# Si muestra 'lg', desinstalar y usar 'sm':
venv/bin/python -m spacy download es_core_news_sm
pip uninstall es-core-news-lg
```

**Impacto**: Hasta 600 MB si se está usando modelo grande

#### 4. Reducir Idiomas de Electron (Opcional)

**Archivo**: `forge.config.js`

```javascript
packagerConfig: {
  asar: true,
  // Añadir:
  ignore: [
    /\.git/,
    /node_modules\/.*\/test/,
    /node_modules\/.*\/tests/,
  ],
  // Opcional: Solo incluir idiomas necesarios
  afterCopy: [(buildPath, electronVersion, platform, arch, callback) => {
    // Remover locales innecesarios excepto es, en
    const localesPath = path.join(buildPath, 'locales');
    const keepLocales = ['es.pak', 'es-419.pak', 'en-US.pak', 'en-GB.pak'];
    // Implementar limpieza...
    callback();
  }],
}
```

**Impacto estimado**: 2-5 MB

### Checklist de Optimización

- [ ] Auditar `requirements.txt` y remover dependencias no usadas
- [ ] Verificar imports en código Python (buscar `torch`, `transformers`)
- [ ] Editar `.spec` para añadir `strip=True` y `excludes`
- [ ] Recompilar backend: `npm run build:backend`
- [ ] Verificar modelo spaCy es `sm` no `lg`
- [ ] Empaquetar y medir: `npm run make`
- [ ] Comparar tamaño antes/después

### Comandos de Verificación

```bash
# Ver tamaño de dependencias Python
cd backend
venv/bin/pip list --format=columns | sort -k2 -hr

# Ver tamaño del backend compilado
ls -lh dist/anonidata-backend

# Ver tamaño de la app empaquetada
du -sh out/anonidata-darwin-arm64/anonidata.app
du -sh out/make/zip/darwin/arm64/*.zip
```

### Impacto Total Estimado

| Escenario | Tamaño Actual | Tamaño Optimizado | Reducción |
|-----------|---------------|-------------------|-----------|
| Sin optimizar | 1.0 GB | - | - |
| Optimizaciones rápidas | - | 980 MB | 2% |
| + Modelo spaCy optimizado | - | 950 MB | 5% |
| + Todas las optimizaciones | - | 875-945 MB | 5-12% |

### Advertencias

1. **NO remover**: `PyMuPDF`, `spaCy`, `OpenCV`, `Pillow` - son críticas
2. **Probar siempre** la app empaquetada tras optimizar
3. **Mantener backup** del `.spec` file original
4. **Documentar** qué dependencias se removieron y por qué

## 📚 Recursos Útiles

- **Electron Docs**: https://www.electronjs.org/docs
- **PyMuPDF Docs**: https://pymupdf.readthedocs.io/
- **spaCy Docs**: https://spacy.io/usage
- **TailwindCSS**: https://tailwindcss.com/docs
- **React Docs**: https://react.dev/

## 🎓 Notas Finales

1. **Siempre compilar antes de empaquetar**: Los cambios en código fuente no se reflejan en el `.app` hasta compilar
2. **Backend es crítico**: Cualquier cambio en Python requiere recompilar con PyInstaller
3. **Fecha de build es automática**: Se actualiza al compilar renderer con Vite
4. **Usar git descriptivamente**: Commits claros facilitan debugging y rollbacks
5. **Priorizar bboxes precisas**: Mejorar la experiencia de usuario en revisión manual

---

**Última actualización**: Diciembre 2025
**Versión del proyecto**: 1.0.0
