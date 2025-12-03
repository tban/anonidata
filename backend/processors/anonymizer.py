"""
Motor de anonimización irreversible de PDFs
Aplica redacción mediante cajas negras, pixelación o difuminado
"""

import io
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

import numpy as np
from PIL import Image, ImageFilter

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF no instalado")
    raise

try:
    import cv2
except ImportError:
    logger.warning("opencv-python no instalado")
    cv2 = None

from core.config import Settings
from processors.pdf_parser import PDFData
from detectors.pii_detector import PIIMatch
from utils.file_manager import FileManager


class Anonymizer:
    """Motor de anonimización de PDFs"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.file_manager = FileManager(settings)

    def anonymize(
        self,
        input_path: Path,
        pdf_data: PDFData,
        pii_matches: List[PIIMatch],
    ) -> Path:
        """
        Anonimiza un PDF redactando todos los matches de PII

        Args:
            input_path: Ruta al PDF original
            pdf_data: Datos del PDF parseado
            pii_matches: Lista de PII detectados

        Returns:
            Ruta al PDF anonimizado
        """
        logger.info(f"Anonimizando {len(pii_matches)} elementos")

        # Generar ruta de salida
        output_path = self.file_manager.generate_output_path(input_path)

        # Abrir documento
        doc = fitz.open(input_path)

        try:
            # Agrupar matches por página
            matches_by_page = self._group_by_page(pii_matches)

            # Procesar cada página
            for page_num, matches in matches_by_page.items():
                if page_num < doc.page_count:
                    page = doc[page_num]
                    self._anonymize_page(page, matches)

            # Añadir pie de página a todas las páginas
            for page in doc:
                self._add_footer(page)

            # Guardar documento anonimizado
            doc.save(
                str(output_path),
                garbage=4,  # Máxima compresión
                deflate=True,
                clean=True,
            )

            logger.info(f"PDF anonimizado guardado: {output_path.name}")

            return output_path

        finally:
            doc.close()

    def _group_by_page(self, matches: List[PIIMatch]) -> Dict[int, List[PIIMatch]]:
        """Agrupa matches por número de página"""
        grouped: Dict[int, List[PIIMatch]] = {}

        for match in matches:
            page_num = match.page_num
            if page_num not in grouped:
                grouped[page_num] = []
            grouped[page_num].append(match)

        return grouped

    def _add_footer(self, page: fitz.Page) -> None:
        """
        Añade pie de página "AnoniData (año)" en la esquina inferior derecha

        Args:
            page: Página de PyMuPDF
        """
        from datetime import datetime

        # Obtener año actual
        current_year = datetime.now().year
        footer_text = f"AnoniData ({current_year})"

        # Obtener dimensiones de la página
        page_rect = page.rect

        # Configurar posición: esquina inferior derecha con margen
        margin = 20
        font_size = 8

        # Crear objeto de texto
        text_writer = fitz.TextWriter(page_rect)

        # Calcular posición del texto (alineado a la derecha)
        font = fitz.Font("helv")  # Helvetica
        text_width = font.text_length(footer_text, fontsize=font_size)

        # Posición: margen desde la derecha, margen desde abajo
        x = page_rect.width - text_width - margin
        y = page_rect.height - margin

        # Añadir texto
        text_writer.append(
            (x, y),
            footer_text,
            font=font,
            fontsize=font_size,
            color=(0.5, 0.5, 0.5)  # Gris medio
        )

        # Escribir en la página
        text_writer.write_text(page)

    def _anonymize_page(self, page: fitz.Page, matches: List[PIIMatch]) -> None:
        """
        Anonimiza una página completa

        Args:
            page: Página de PyMuPDF
            matches: Matches a redactar
        """
        logger.info(f"Anonimizando página {page.number}: {len(matches)} detecciones")

        # Marcar todas las regiones para redacción
        for i, match in enumerate(matches, 1):
            bbox = match.bbox
            logger.debug(f"  [{i}/{len(matches)}] {match.type}: '{match.text}' | bbox: {bbox}")

            if self.settings.redaction_strategy == "black_box":
                self._apply_black_box(page, bbox)
            elif self.settings.redaction_strategy == "pixelate":
                self._apply_pixelation(page, bbox)
            elif self.settings.redaction_strategy == "blur":
                self._apply_blur(page, bbox)

        # Aplicar todas las redacciones de golpe (ELIMINA el contenido permanentemente)
        # Esto borra el texto subyacente y lo reemplaza con el relleno especificado
        logger.info(f"Aplicando {len(matches)} redacciones a página {page.number}")
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)

    def _apply_black_box(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica redacción destructiva con caja negra (ELIMINA el contenido del PDF)

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas (x0, y0, x1, y1)
        """
        rect = fitz.Rect(bbox)

        # Marcar región para redacción con relleno negro
        # fill: color de relleno después de eliminar el contenido
        page.add_redact_annot(rect, fill=self.settings.redaction_color)

    def _apply_pixelation(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica pixelación a una región con redacción destructiva

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas
        """
        if cv2 is None:
            # Fallback a caja negra si no hay OpenCV
            self._apply_black_box(page, bbox)
            return

        try:
            # Renderizar región ANTES de redactar
            rect = fitz.Rect(bbox)
            mat = fitz.Matrix(2.0, 2.0)  # 2x resolución
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Convertir a imagen PIL
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            img_array = np.array(img)

            # Aplicar pixelación
            h, w = img_array.shape[:2]
            pixel_size = self.settings.pixelation_level

            # Reducir y ampliar para pixelar
            temp_h = max(1, h // pixel_size)
            temp_w = max(1, w // pixel_size)

            temp = cv2.resize(img_array, (temp_w, temp_h), interpolation=cv2.INTER_LINEAR)
            pixelated = cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)

            # Convertir de vuelta a PIL
            pixelated_img = Image.fromarray(pixelated)

            # Guardar imagen pixelada como bytes
            img_bytes = io.BytesIO()
            pixelated_img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Marcar región para redacción con la imagen pixelada como relleno
            # IMPORTANTE: Esto ELIMINA el texto original
            page.add_redact_annot(rect, fill=self.settings.redaction_color, image=img_bytes.getvalue())

        except Exception as e:
            logger.warning(f"Error aplicando pixelación: {e}, usando caja negra")
            self._apply_black_box(page, bbox)

    def _apply_blur(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica difuminado gaussiano a una región con redacción destructiva

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas
        """
        try:
            # Renderizar región ANTES de redactar
            rect = fitz.Rect(bbox)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Convertir a PIL
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            # Aplicar blur fuerte
            blurred = img.filter(ImageFilter.GaussianBlur(radius=20))

            # Guardar imagen difuminada como bytes
            img_bytes = io.BytesIO()
            blurred.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Marcar región para redacción con la imagen difuminada como relleno
            # IMPORTANTE: Esto ELIMINA el texto original
            page.add_redact_annot(rect, fill=self.settings.redaction_color, image=img_bytes.getvalue())

        except Exception as e:
            logger.warning(f"Error aplicando blur: {e}, usando caja negra")
            self._apply_black_box(page, bbox)
