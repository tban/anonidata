---
description: How to build and package AnoniData for distribution
---

# Building AnoniData for Distribution

## Prerequisites
1. Ensure you have the development environment set up
2. Have code signing certificates configured (for macOS)

## Build Steps

### 1. Build all components
```bash
npm run build
```
This command:
- Builds the renderer (Vite) → `dist/renderer/`
- Builds the main process (TypeScript) → `dist/main/`
- Builds the Python backend (PyInstaller) → `dist/anonidata-backend`

### 2. Create distribution package

**For macOS ARM64 (Apple Silicon):**
```bash
npx -y electron-builder --mac dmg --arm64
```

**For macOS Intel:**
```bash
npx -y electron-builder --mac dmg --x64
```

**For macOS Universal (both architectures):**
```bash
npx -y electron-builder --mac dmg --universal
```

### 3. Output location
Distribution files are generated in: `release/`
- `AnoniData-1.0.0-arm64.dmg` - Apple Silicon
- `AnoniData-1.0.0.dmg` - Intel x64
- `AnoniData-1.0.0-universal.dmg` - Universal

## Important Configuration Notes

### Backend Binary Path (CRITICAL)
The `package.json` must have the correct `extraResources` configuration:

```json
"extraResources": [
  {
    "from": "dist/anonidata-backend",
    "to": "anonidata-backend"
  }
]
```

**NOT** `backend/dist/anonidata-backend` - PyInstaller outputs to `dist/`, not `backend/dist/`.

### Entitlements File
The file `build/entitlements.mac.plist` must exist for code signing:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <key>com.apple.security.automation.apple-events</key>
    <true/>
</dict>
</plist>
```

## Clean Build
To do a clean build:
```bash
rm -rf release/*
npm run build
npx -y electron-builder --mac dmg --arm64
```

## Troubleshooting

### "ENOENT anonidata-backend" Error
If you see this error after installing:
1. Verify `extraResources.from` path is `dist/anonidata-backend`
2. Run `npm run build` before packaging
3. Check that `dist/anonidata-backend` exists after build
