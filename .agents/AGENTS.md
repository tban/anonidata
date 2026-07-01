# Reglas de Publicación (Publishing Rules)

- **Distribución en Google Drive**: Siempre que el usuario solicite publicar, compilar o crear una versión para Mac (o de forma general), copia el ejecutable resultante (ej. `.dmg`) a la carpeta de Google Drive designada: `/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA`. No utilices rutas predeterminadas de Github Releases a menos que el usuario lo solicite expresamente.
- **Nomenclatura del Ejecutable Universal**: La versión universal (o el empaquetado para Mac) debe publicarse **siempre** con el nombre estricto `Anonidata.dmg` (con la 'd' minúscula). Asegúrate de que los scripts de release o cualquier copia manual lo renombren de esta manera.
- **Publicación de la versión Windows (Máquina Virtual)**: Cuando el usuario solicite "actualiza Google Drive" o publicar la versión de Windows, el ejecutable no estará en local. Debes extraerlo automáticamente de la máquina virtual Windows ARM conectándote por SMB de esta manera:
  1. Desmonta montajes huérfanos: `umount -f /Volumes/Desarrollos || true` y `umount /tmp/windows_vm || true`
  2. Crea punto de montaje temporal: `mkdir -p /tmp/windows_vm`
  3. Monta la carpeta: `mount_smbfs //ciber:'Privacidad%2C255'@192.168.64.2/Desarrollos /tmp/windows_vm`
  4. Copia los archivos: `cp /tmp/windows_vm/anonidata/dist/windows/* "/Users/tban/Library/CloudStorage/GoogleDrive-tbanrguez@gmail.com/Mi unidad/PUBLICAPPS/ANONIDATA/"`
  5. Desmonta y limpia: `umount /tmp/windows_vm && rm -rf /tmp/windows_vm`
  *(IMPORTANTE: Al extraer la versión Windows, debes asegurar que extraes el instalador completo `.exe` desde la ruta indicada `dist/windows/*` y nunca el binario crudo `anonidata.exe` desde la carpeta `target/release/`, ya que al binario crudo le falta el sidecar adjunto del backend).*

# Peculiaridades de Compilación (Windows ARM64 y Tauri)
- **Tauri y Rust en ARM64**: Si se compila una app Tauri para x64 desde un host Windows ARM64, la herramienta de construcción requiere tener instalado en Visual Studio no solo el componente "MSVC C++ x64/x86 build tools" para cross-compilar la app, sino también el componente nativo **"MSVC C++ ARM64/ARM64 build tools"** para compilar las macros y dependencias internas (proc-macros) que corren en el propio host.
- **Sintaxis Batch (CMD)**: Evita usar siempre paréntesis `()` dentro de los comandos `echo` en un bloque `if ( ... )`. El intérprete Batch los confunde con el cierre del bloque y provoca errores de sintaxis (ej. `No se esperaba : en este momento.`). Utiliza corchetes `[]` en su lugar.
