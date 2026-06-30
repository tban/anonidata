import sys
import json
from pathlib import Path

def emit_progress(file_path, progress: int, step: str):
    """
    Emite un evento de progreso en formato JSON por stdout para que Tauri lo capture.
    """
    if file_path is None:
        return
    try:
        # Mantener el string del path tal como viene para coincidir exactamente
        # con lo que el frontend envió y espera.
        progress_data = {
            "status": "progress",
            "file": str(file_path),
            "progress": int(progress),
            "step": str(step)
        }
        sys.stdout.write(json.dumps(progress_data) + "\n")
        sys.stdout.flush()
    except Exception:
        # Evitar fallos por errores al emitir progreso
        pass
