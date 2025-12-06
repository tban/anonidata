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
        Limpia todos los metadatos sensibles del PDF y los reemplaza con "AnoniData"

        Args:
            file_path: Ruta al PDF
        """
        if pikepdf is None:
            logger.warning("pikepdf no disponible, omitiendo limpieza de metadatos")
            return

        try:
            # Abrir el PDF con permiso para sobrescribir
            pdf = pikepdf.open(file_path, allow_overwriting_input=True)

            # Limpiar completamente metadata XMP
            with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
                meta.clear()
                # Establecer todos los campos con AnoniData
                meta['dc:title'] = 'AnoniData'
                meta['dc:creator'] = ['AnoniData']
                meta['dc:subject'] = 'AnoniData'
                meta['dc:description'] = 'AnoniData'
                meta['pdf:Producer'] = 'AnoniData'
                meta['pdf:Keywords'] = 'AnoniData'
                meta['xmp:CreatorTool'] = 'AnoniData'

            # Limpiar completamente metadata del documento (Document Info Dictionary)
            # Modificar en lugar de reemplazar para evitar errores con pikepdf
            if not hasattr(pdf, 'docinfo') or pdf.docinfo is None:
                pdf.docinfo = pikepdf.Dictionary()

            # Establecer cada campo individualmente
            pdf.docinfo[pikepdf.Name.Title] = 'AnoniData'
            pdf.docinfo[pikepdf.Name.Author] = 'AnoniData'
            pdf.docinfo[pikepdf.Name.Subject] = 'AnoniData'
            pdf.docinfo[pikepdf.Name.Keywords] = 'AnoniData'
            pdf.docinfo[pikepdf.Name.Producer] = 'AnoniData'
            pdf.docinfo[pikepdf.Name.Creator] = 'AnoniData'

            # Eliminar fechas de creación y modificación del docinfo
            if pikepdf.Name.CreationDate in pdf.docinfo:
                del pdf.docinfo[pikepdf.Name.CreationDate]
            if pikepdf.Name.ModDate in pdf.docinfo:
                del pdf.docinfo[pikepdf.Name.ModDate]

            # Guardar los cambios sobrescribiendo el archivo original
            pdf.save(file_path)
            pdf.close()

            logger.debug(f"Metadatos limpiados y reemplazados con AnoniData: {file_path.name}")

        except Exception as e:
            logger.error(f"Error limpiando metadatos: {e}", exc_info=True)

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
        SIEMPRE sobrescribe el archivo si ya existe

        Args:
            input_path: Ruta del archivo original

        Returns:
            Ruta del archivo anonimizado
        """
        stem = input_path.stem
        suffix = input_path.suffix
        directory = input_path.parent

        output_path = directory / f"{stem}_anonimizado{suffix}"

        # NO agregar número, siempre sobrescribir
        return output_path

    def generate_pre_anonymized_path(self, input_path: Path) -> Path:
        """
        Genera la ruta del archivo pre-anonimizado (con anotaciones sin aplicar)
        SIEMPRE sobrescribe el archivo si ya existe

        Args:
            input_path: Ruta del archivo original

        Returns:
            Ruta del archivo pre-anonimizado
        """
        stem = input_path.stem
        suffix = input_path.suffix
        directory = input_path.parent

        output_path = directory / f"{stem}_preAnonimizado{suffix}"

        # NO agregar número, siempre sobrescribir
        return output_path

    def generate_detections_path(self, input_path: Path) -> Path:
        """
        Genera la ruta del archivo JSON con las detecciones de PII
        SIEMPRE sobrescribe el archivo si ya existe

        Args:
            input_path: Ruta del archivo original

        Returns:
            Ruta del archivo de detecciones JSON
        """
        stem = input_path.stem
        directory = input_path.parent

        output_path = directory / f"{stem}_detections.json"

        # NO agregar número, siempre sobrescribir
        return output_path

    def generate_review_state_path(self, input_path: Path) -> Path:
        """
        Genera la ruta del archivo JSON con el estado de revisión
        SIEMPRE sobrescribe el archivo si ya existe

        Args:
            input_path: Ruta del archivo original

        Returns:
            Ruta del archivo de estado de revisión
        """
        stem = input_path.stem
        directory = input_path.parent

        output_path = directory / f"{stem}_review.json"

        # NO agregar número, siempre sobrescribir
        return output_path
