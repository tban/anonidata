!macro NSIS_HOOK_PREINSTALL
    ; Matar procesos activos para evitar bloqueos del sistema de archivos durante la instalación/actualización
    nsExec::Exec 'taskkill /F /IM AnoniData.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend-x86_64-pc-windows-msvc.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend-x86_64-pc-windows-gnu.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend-i686-pc-windows-msvc.exe /T'
    Sleep 1000
!macroend

!macro NSIS_HOOK_PREUNINSTALL
    ; Matar procesos activos antes de proceder con la desinstalación
    nsExec::Exec 'taskkill /F /IM AnoniData.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend-x86_64-pc-windows-msvc.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend-x86_64-pc-windows-gnu.exe /T'
    nsExec::Exec 'taskkill /F /IM anonidata-backend-i686-pc-windows-msvc.exe /T'
    Sleep 1000
!macroend
