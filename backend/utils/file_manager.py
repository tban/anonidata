"""
Gestor de archivos y limpieza de metadatos
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    import pikepdf
except ImportError:
    pikepdf = None

from core.config import Settings


class FileManager:
    """Gestión de archivos y limpieza"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.temp_dir = Path(tempfile.mkdtemp(prefix="anonidata_"))
        logger.debug(f"Directorio temporal creado: {self.temp_dir}")

    def validate_pdf(self, file_path: Path) -> bool:
        """
        Valida que el archivo sea un PDF válido

        Args:
            file_path: Ruta al archivo

        Returns:
            True si es válido

        Raises:
            ValueError: Si el archivo no es válido
        """
        if not file_path.exists():
            raise ValueError(f"Archivo no encontrado: {file_path}")

        if file_path.suffix.lower() != '.pdf':
            raise ValueError(f"El archivo no es un PDF: {file_path}")

        file_size = file_path.stat().st_size
        if file_size > self.settings.max_file_size:
            max_mb = self.settings.max_file_size / 1024 / 1024
            raise ValueError(f"Archivo demasiado grande (máx: {max_mb}MB)")

        if file_size == 0:
            raise ValueError("El archivo está vacío")

        # Verificar que se puede abrir
        try:
            import fitz
            doc = fitz.open(file_path)
            if doc.page_count == 0:
                raise ValueError("El PDF no tiene páginas")
            doc.close()
        except Exception as e:
            raise ValueError(f"Error abriendo PDF: {e}")

        logger.debug(f"Archivo validado: {file_path.name}")
        return True

    def clean_metadata(self, file_path: Path) -> None:
        """
        Limpia metadatos sensibles del PDF

        Args:
            file_path: Ruta al PDF
        """
        if pikepdf is None:
            logger.warning("pikepdf no disponible, omitiendo limpieza de metadatos")
            return

        try:
            with pikepdf.open(file_path, allow_overwriting_input=True) as pdf:
                # Limpiar metadata XMP
                with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                    meta.clear()
                    meta['dc:title'] = 'Documento Anonimizado'
                    meta['dc:creator'] = 'AnoniData'
                    meta['pdf:Producer'] = 'AnoniData'

                # Limpiar metadata del documento
                if pdf.docinfo:
                    pdf.docinfo = pikepdf.Dictionary({
                        pikepdf.Name.Title: 'Documento Anonimizado',
                        pikepdf.Name.Author: 'AnoniData',
                        pikepdf.Name.Producer: 'AnoniData',
                        pikepdf.Name.Creator: 'AnoniData',
                    })

                pdf.save()

            logger.debug(f"Metadatos limpiados: {file_path.name}")

        except Exception as e:
            logger.error(f"Error limpiando metadatos: {e}")

    def cleanup_temp(self) -> None:
        """Limpia archivos temporales"""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.debug("Archivos temporales eliminados")
        except Exception as e:
            logger.error(f"Error limpiando temporales: {e}")

    def generate_output_path(self, input_path: Path) -> Path:
        """
        Genera la ruta del archivo de salida

        Args:
            input_path: Ruta del archivo original

        Returns:
            Ruta del archivo anonimizado
        """
        stem = input_path.stem
        suffix = input_path.suffix
        directory = input_path.parent

        output_path = directory / f"{stem}_anonimizado{suffix}"

        # Si ya existe, agregar número
        counter = 1
        while output_path.exists():
            output_path = directory / f"{stem}_anonimizado_{counter}{suffix}"
            counter += 1

        return output_path
