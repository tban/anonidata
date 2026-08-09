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
- **Comando TEST**: Cuando el usuario pida ejecutar "TEST", debes procesar automáticamente (mediante el script `backend/scripts/run_test_suite.py` o similar) las plantillas v1, v2 y v3 ubicadas en `/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA/TEST/`.
- **Cálculo de Aciertos**: Debes calcular el % de aciertos usando los siguientes totales de referencia comprobados (Total: 284 datos):
  - **v1**: 56 datos (Nombres:13, DNI:6, Tel:4, Dir:4, Firma:5, FechaNac:4, NSS:3, Email:4, IBAN:1, Matrícula:1, Colegiado:4, Salud:3, Sindicato:2, Categoría:1, Antigüedad:1)
  - **v2**: 94 datos (Nombres:19, DNI:10, Tel:10, Dir:5, Firma:6, FechaNac:8, NSS:7, Email:4, IBAN:2, Matrícula:4, Colegiado:4, Salud:4, Sindicato:3, NIE:2, Edad:1, Categoría:1, Antigüedad:1, Geoloc:1, Tarjeta:1, Pasaporte:1)
  - **v3**: 134 datos (Nombres:32, DNI:16, Tel:13, Dir:11, Firma:10, FechaNac:9, NSS:7, Email:5, IBAN:5, Matrícula:5, Colegiado:4, Salud:4, Sindicato:3, NIE:2, Edad:1, Categoría:1, Antigüedad:1, Geoloc:1, Tarjeta:1, Pasaporte:1, Infracción penal:1, TIP:1)
- **Histórico y Presentación del Resultado**: 
  - Tras cada test, guarda el histórico en el archivo `.agents/test_history.json` registrando la fecha, versión, total de detecciones por plantilla, % de aciertos globales y desglose.
  - Informa al usuario del resultado con un bloque destacado (`> [!NOTE]`) comparando con la **versión anterior** del historial (mostrando % de aciertos y diferencias en detecciones).
- **Verificación Posterior**: Debes analizar los archivos anonimizados generados para asegurar que no contienen metadatos y que los datos personales (284) ya no son accesibles, asegurando también que no se hayan anonimizado por error los casos de control (CIF, códigos QR/CSV, sellos institucionales, hashes SHA-256).

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
