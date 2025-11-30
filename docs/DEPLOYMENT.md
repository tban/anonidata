# Guía de Despliegue

## Build para Producción

### Preparación

1. **Actualizar versión** en `package.json`
2. **Actualizar CHANGELOG.md** con cambios
3. **Ejecutar tests completos**
   ```bash
   npm test
   npm run test:backend
   ```
4. **Build local de prueba**

---

## macOS

### Requisitos

- macOS 10.15+
- Xcode Command Line Tools
- Apple Developer Account (para firma y notarización)

### Build

```bash
# Build sin firma (desarrollo)
npm run build
npm run package:mac

# Build con firma
npm run package:mac
```

### Firma y Notarización

#### 1. Obtener Certificado

1. Acceder a [Apple Developer](https://developer.apple.com/)
2. Crear certificado "Developer ID Application"
3. Descargar e instalar en Keychain

#### 2. Configurar Variables

```bash
export APPLE_ID="tu@email.com"
export APPLE_ID_PASSWORD="@keychain:AC_PASSWORD"
export CERT_ID="Developer ID Application: Tu Nombre (XXXXXXXXXX)"
```

#### 3. Build con Firma

```bash
# Configurar en package.json
{
  "build": {
    "mac": {
      "identity": "Developer ID Application: ...",
      "hardenedRuntime": true,
      "entitlements": "build/entitlements.mac.plist"
    }
  }
}

npm run package:mac
```

#### 4. Notarizar

```bash
# Subir a Apple
xcrun altool --notarize-app \
  --primary-bundle-id "com.anonidata.app" \
  --username "$APPLE_ID" \
  --password "$APPLE_ID_PASSWORD" \
  --file release/AnoniData-1.0.0-universal.dmg

# Esperar aprobación (10-60 minutos)
# Verificar estado
xcrun altool --notarization-info REQUEST_UUID \
  --username "$APPLE_ID" \
  --password "$APPLE_ID_PASSWORD"

# Staple (adjuntar ticket de notarización)
xcrun stapler staple release/AnoniData-1.0.0-universal.dmg

# Verificar
xcrun stapler validate release/AnoniData-1.0.0-universal.dmg
```

---

## Windows

### Requisitos

- Windows 10/11
- Node.js 18+
- Python 3.11+
- (Opcional) Certificado de firma de código

### Build

```bash
npm run build
npm run package:win
```

Genera:
- `AnoniData-Setup-1.0.0.exe` (instalador NSIS)
- `AnoniData-1.0.0.exe` (portable)

### Firma de Código (Opcional)

#### Con Certificado PFX

```bash
# Configurar en package.json
{
  "build": {
    "win": {
      "certificateFile": "certs/cert.pfx",
      "certificatePassword": "${env.CERT_PASSWORD}",
      "publisherName": "AnoniData"
    }
  }
}

# Build con firma
set CERT_PASSWORD=tu-password
npm run package:win
```

#### Con signtool

```bash
signtool sign /f cert.pfx /p password /t http://timestamp.digicert.com release/AnoniData-Setup-1.0.0.exe
```

---

## Linux (Experimental)

### Build

```bash
npm run build
electron-builder --linux
```

Genera:
- `.AppImage` (portable)
- `.deb` (Debian/Ubuntu)

---

## Automatización con GitHub Actions

### Crear `.github/workflows/build.yml`

```yaml
name: Build

on:
  push:
    tags:
      - 'v*'

jobs:
  build-mac:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          npm install
          cd backend
          pip install -r requirements.txt
          python -m spacy download es_core_news_lg

      - name: Build
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          APPLE_ID_PASSWORD: ${{ secrets.APPLE_ID_PASSWORD }}
        run: npm run package:mac

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: AnoniData-macOS
          path: release/*.dmg

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          npm install
          cd backend
          pip install -r requirements.txt
          python -m spacy download es_core_news_lg

      - name: Build
        run: npm run package:win

      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: AnoniData-Windows
          path: release/*.exe
```

---

## Publicación

### GitHub Releases

1. Crear tag:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. Crear release en GitHub
3. Subir binarios:
   - `AnoniData-1.0.0-universal.dmg`
   - `AnoniData-Setup-1.0.0.exe`
   - `AnoniData-1.0.0.AppImage`

### Auto-update (Futuro)

Configurar con `electron-updater`:

```typescript
import { autoUpdater } from 'electron-updater';

autoUpdater.checkForUpdatesAndNotify();
```

---

## Checklist Pre-Release

- [ ] Tests pasando
- [ ] Documentación actualizada
- [ ] CHANGELOG.md actualizado
- [ ] Versión incrementada
- [ ] Build local exitoso en todas las plataformas
- [ ] Firma y notarización (macOS)
- [ ] Verificar instaladores en VMs limpias
- [ ] Screenshots actualizados
- [ ] Release notes preparadas

---

## Distribución

### App Store (Futuro)

**macOS App Store:**
- Requiere suscripción Apple Developer ($99/año)
- Sandboxing estricto (puede limitar funcionalidad)
- Revisión de Apple (1-3 días)

**Microsoft Store:**
- Requiere cuenta Microsoft Developer ($19 one-time)
- Menos restricciones que Mac App Store

### Alternativas

- **Sitio web oficial**: Hosting propio de binarios
- **GitHub Releases**: Gratis, pero sin auto-update automático
- **Homebrew** (macOS):
  ```bash
  brew install --cask anonidata
  ```
- **Chocolatey** (Windows):
  ```bash
  choco install anonidata
  ```

---

## Monitorización Post-Release

### Crash Reporting (Opcional)

Integrar Sentry:

```typescript
import * as Sentry from '@sentry/electron';

Sentry.init({
  dsn: 'https://...',
  // Solo errores críticos, sin PII
});
```

**IMPORTANTE**: Asegurar que no se envíen datos personales.

### Analytics (Opcional)

Si se requiere, usar analytics que respeten RGPD:
- Plausible Analytics
- Matomo (self-hosted)

**NO usar**: Google Analytics, Mixpanel, etc.

---

## Troubleshooting

### Error: "Cannot find module 'fitz'"

PyInstaller no incluyó PyMuPDF. Agregar a `hiddenimports` en spec.

### macOS: "App is damaged"

```bash
xattr -cr /Applications/AnoniData.app
```

### Windows: "Windows Defender bloquea instalador"

Obtener certificado de firma de código de autoridad certificadora reconocida.

---

## Recursos

- [Electron Builder Docs](https://www.electron.build/)
- [Apple Notarization Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [PyInstaller Manual](https://pyinstaller.org/en/stable/)
