!macro NSIS_HOOK_PREINSTALL
    ; Omitimos las llamadas a taskkill para evitar cuelgues del enlazador de comandos en Windows ARM64
!macroend

!macro NSIS_HOOK_POSTINSTALL
    ; Vacio
!macroend

!macro NSIS_HOOK_PREUNINSTALL
    ; Vacio
!macroend
