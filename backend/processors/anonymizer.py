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

    def _anonymize_page(self, page: fitz.Page, matches: List[PIIMatch]) -> None:
        """
        Anonimiza una página completa

        Args:
            page: Página de PyMuPDF
            matches: Matches a redactar
        """
        for match in matches:
            bbox = match.bbox

            if self.settings.redaction_strategy == "black_box":
                self._apply_black_box(page, bbox)
            elif self.settings.redaction_strategy == "pixelate":
                self._apply_pixelation(page, bbox)
            elif self.settings.redaction_strategy == "blur":
                self._apply_blur(page, bbox)

    def _apply_black_box(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica tachado con caja negra (dibuja sobre el texto sin eliminarlo)

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas (x0, y0, x1, y1)
        """
        rect = fitz.Rect(bbox)

        # Dibujar rectángulo negro relleno sobre el texto
        # NO eliminamos el contenido subyacente, solo lo cubrimos
        page.draw_rect(
            rect,
            color=None,
            fill=self.settings.redaction_color,
            overlay=True,
        )

    def _apply_pixelation(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica pixelación a una región

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas
        """
        if cv2 is None:
            # Fallback a caja negra si no hay OpenCV
            self._apply_black_box(page, bbox)
            return

        try:
            # Renderizar región
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

            # Guardar imagen pixelada
            img_bytes = io.BytesIO()
            pixelated_img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Insertar imagen pixelada en el PDF
            page.insert_image(rect, stream=img_bytes.read())

        except Exception as e:
            logger.warning(f"Error aplicando pixelación: {e}, usando caja negra")
            self._apply_black_box(page, bbox)

    def _apply_blur(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica difuminado gaussiano a una región

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas
        """
        try:
            # Renderizar región
            rect = fitz.Rect(bbox)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Convertir a PIL
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            # Aplicar blur fuerte
            blurred = img.filter(ImageFilter.GaussianBlur(radius=20))

            # Guardar
            img_bytes = io.BytesIO()
            blurred.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Insertar en PDF
            page.insert_image(rect, stream=img_bytes.read())

        except Exception as e:
            logger.warning(f"Error aplicando blur: {e}, usando caja negra")
            self._apply_black_box(page, bbox)
