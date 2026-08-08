# Reglas de Publicación (Publishing Rules)

- **Publicación en GitHub**: Los instaladores (`Anonidata.dmg` para Mac y `anonidata.exe` para Windows) se publican ahora en **GitHub** en lugar de Google Drive.
- **Nomenclatura del Ejecutable Universal (Mac)**: La versión de Mac debe publicarse **siempre** con el nombre estricto `Anonidata.dmg` (con la 'A' mayúscula y la 'd' minúscula). Asegúrate de que los scripts de release o cualquier copia manual lo renombren de esta manera.
- **Nomenclatura del Instalador de Windows**: El instalador final de Windows debe publicarse **siempre** con el nombre estricto `anonidata.exe` (todo en minúsculas).
- **Extracción de la versión Windows (Máquina Virtual)**: Cuando haya que recuperar la versión de Windows compilada, debes extraerla automáticamente de la máquina virtual Windows ARM conectándote por SMB de esta manera:
  1. Desmonta montajes huérfanos: `umount -f /Volumes/Desarrollos || true` y `umount /tmp/windows_vm || true`
  2. Crea punto de montaje temporal: `mkdir -p /tmp/windows_vm`
  3. Monta la carpeta: `mount_smbfs //ciber:'Privacidad%2C255'@192.168.64.2/Desarrollos /tmp/windows_vm`
  4. Copia los archivos buscando el instalador en `dist/windows` a tu directorio local para publicarlo luego en GitHub (ej. usando la CLI `gh release`).
  5. Desmonta y limpia: `umount /tmp/windows_vm && rm -rf /tmp/windows_vm`
  *(IMPORTANTE: Al extraer la versión Windows, debes asegurar que extraes el instalador completo `.exe` desde la ruta indicada `dist/windows/*.exe` y nunca el binario crudo `anonidata.exe` desde la carpeta `target/release/`, ya que al binario crudo le falta el sidecar adjunto del backend).*

# Peculiaridades de Compilación (Windows ARM64 y Tauri)
- **Tauri y Rust en ARM64**: Si se compila una app Tauri para x64 desde un host Windows ARM64, la herramienta de construcción requiere tener instalado en Visual Studio no solo el componente "MSVC C++ x64/x86 build tools" para cross-compilar la app, sino también el componente nativo **"MSVC C++ ARM64/ARM64 build tools"** para compilar las macros y dependencias internas (proc-macros) que corren en el propio host.
- **Sintaxis Batch (CMD)**: Evita usar siempre paréntesis `()` dentro de los comandos `echo` en un bloque `if ( ... )`. El intérprete Batch los confunde con el cierre del bloque y provoca errores de sintaxis (ej. `No se esperaba : en este momento.`). Utiliza corchetes `[]` en su lugar.

# Reglas de Testeo
- **Validación pre-publicación**: Antes de subir nueva versión recuerda siempre que debes hacer el siguiente test con la versión a publicar: Lanzar el aplicativo en local, procesar el archivo `/Users/tban/Library/CloudStorage/Box-Box/ACCESO PUBLICO/plantilla_prueba_datos_personales_v2_anonimizado.pdf` y analizar el resultado (% de aciertos con respecto a la versión anterior, advertencia si ha bajado, etc.)

# Flujo "COMPILA BUILD"
Cuando el usuario pida ejecutar el flujo "COMPILA BUILD", debes realizar estrictamente los siguientes pasos en orden:
1. **Incrementar versión**: Sube la versión (patch) en `package.json`, `src-tauri/tauri.conf.json` y `src-tauri/Cargo.toml`.
2. **Sincronizar código a la VM Windows**: Ejecuta el script `./scripts/sync-to-windows.sh` para copiar el código fresco a la máquina virtual y que el usuario empiece a compilar allí.
3. **Compilar versión Mac**: Ejecuta localmente `npm run build:backend && npm run build` para compilar la nueva versión en segundo plano.
4. **Pausa y Cartel**: Muestra un mensaje al usuario con un cartelito muy grande (usando Markdown headers o ASCII art) indicando que la compilación de Mac está en marcha/terminada y que **ESTÁS ESPERANDO A QUE EL USUARIO COMPILE WINDOWS**.
5. **Publicación y Versionado**: Solo **después** de que el usuario te avise de que ha terminado de compilar en Windows, debes:
   - Extraer el `.exe` desde la máquina virtual (conectándote por SMB).
   - Crear la Release de GitHub y adjuntar ambos instaladores (`.dmg` de Mac y `.exe` de Windows).
   - Hacer commit de los cambios (archivos de versión como `version.json` y cualquier otro código nuevo) y subirlo a la rama `main` de GitHub. Hacer esto al final garantiza que los usuarios no descarguen el nuevo `version.json` antes de que los ejecutables estén subidos a la release.

# Flujo "COMPILA LOCAL"
Cuando el usuario pida ejecutar el flujo "COMPILA LOCAL", debes realizar estrictamente los siguientes pasos:
1. **Compilar el backend localmente**: Ejecuta `npm run build:backend`.
2. **Lanzar el aplicativo en modo desarrollo**: Una vez que termine la compilación del backend, ejecuta `npm run dev` (que internamente ejecuta Tauri en modo de desarrollo) para que el usuario pueda probar el aplicativo. Asegúrate de dejar el proceso corriendo en segundo plano o de notificar al usuario que la app está abierta.
