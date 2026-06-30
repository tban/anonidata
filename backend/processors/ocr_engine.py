"""
Motor OCR usando Tesseract y EasyOCR
Detecta texto en imágenes embebidas o páginas escaneadas
"""

import os
import io
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
import shutil
import sys

import numpy as np
from PIL import Image

try:
    import pytesseract
except ImportError:
    logger.warning("pytesseract no instalado")
    pytesseract = None

try:
    import cv2
except ImportError:
    logger.warning("opencv-python no instalado")
    cv2 = None

from core.config import Settings
from processors.pdf_parser import PDFData, ImageBlock


@dataclass
class OCRResult:
    """Resultado de OCR"""
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float
    page_num: int
    source: str  # 'tesseract' o 'easyocr'


@dataclass
class OCRData:
    """Datos de OCR procesados"""
    results: List[OCRResult]
    pages_processed: List[int]


class OCREngine:
    """Motor de OCR"""

    def __init__(self, settings: Settings):
        self.settings = settings

        # Verificar Tesseract
        if pytesseract:
            # En macOS (app empaquetada), el PATH puede no incluir homebrew
            tesseract_path = shutil.which("tesseract")
            if not tesseract_path and sys.platform == "darwin":
                for path in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
                    if os.path.exists(path):
                        tesseract_path = path
                        break
            
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path

            try:
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
                logger.debug(f"Tesseract disponible en {tesseract_path or 'PATH'}")
            except Exception as e:
                logger.warning(f"Tesseract no disponible: {e}")
                self.tesseract_available = False
        else:
            self.tesseract_available = False

    def process(self, pdf_data: PDFData, progress_callback=None) -> OCRData:
        """
        Procesa el PDF aplicando OCR donde sea necesario

        Args:
            pdf_data: Datos del PDF parseado
            progress_callback: Callback opcional para reportar progreso

        Returns:
            OCRData con resultados
        """
        # Si OCR está deshabilitado en la configuración, no procesar
        if not getattr(self.settings, "enable_ocr", True):
            logger.info("OCR está deshabilitado para este documento")
            return OCRData(results=[], pages_processed=[])

        if not self.tesseract_available:
            logger.warning("Tesseract no está disponible. Omitiendo conversión de páginas e imágenes para OCR.")
            return OCRData(results=[], pages_processed=[])

        results = []
        pages_processed = []

        # Precalcular páginas con texto (optimización O(1) lookup vs O(n) iteración)
        pages_with_text = {b.page_num for b in pdf_data.text_blocks}

        # Identificar bloques de imágenes y páginas que necesitarán OCR para calcular pasos
        image_blocks_to_ocr = [img_block for img_block in pdf_data.image_blocks if img_block.width > 800 or img_block.height > 800]
        pages_without_text = []
        for page_num in range(pdf_data.page_count):
            has_text = page_num in pages_with_text
            if not has_text:
                pages_without_text.append(page_num)

        total_steps = len(image_blocks_to_ocr) + len(pages_without_text)
        current_step = 0

        # Procesar imágenes grandes (posibles páginas escaneadas)
        for img_block in pdf_data.image_blocks:
            # Solo procesar imágenes grandes (probablemente páginas escaneadas)
            if img_block.width > 800 or img_block.height > 800:
                logger.debug(
                    f"Aplicando OCR a imagen grande en página {img_block.page_num}"
                )
                if progress_callback and total_steps > 0:
                    pct = int((current_step / total_steps) * 100)
                    progress_callback(pct, f"Procesando imagen en pág. {img_block.page_num + 1}...")

                ocr_results = self._ocr_image(img_block)
                results.extend(ocr_results)

                if img_block.page_num not in pages_processed:
                    pages_processed.append(img_block.page_num)

                current_step += 1

        # Detectar páginas sin texto (completamente escaneadas)
        for page_num in range(pdf_data.page_count):
            has_text = page_num in pages_with_text

            if not has_text:
                # Si la página no tiene texto, procesarla completa independientemente
                # de si ya se procesó parcialmente una imagen grande
                logger.debug(f"Página {page_num} sin texto, aplicando OCR a página completa")
                if progress_callback and total_steps > 0:
                    pct = int((current_step / total_steps) * 100)
                    progress_callback(pct, f"Procesando página completa {page_num + 1}...")

                # Renderizar página completa
                page = pdf_data.document[page_num]
                pix = page.get_pixmap(dpi=self.settings.ocr_dpi)

                # Convertir a imagen
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # Aplicar OCR
                ocr_results = self._ocr_pil_image(
                    img, page_num, (0, 0, page.rect.width, page.rect.height)
                )
                results.extend(ocr_results)

                # Marcar como procesada solo si no estaba ya
                if page_num not in pages_processed:
                    pages_processed.append(page_num)

                current_step += 1

        if progress_callback:
            progress_callback(100, "OCR completado")

        logger.debug(f"OCR completado: {len(results)} resultados")

        return OCRData(results=results, pages_processed=pages_processed)

    def _ocr_image(self, img_block: ImageBlock) -> List[OCRResult]:
        """
        Aplica OCR a un bloque de imagen

        Args:
            img_block: Bloque de imagen

        Returns:
            Lista de resultados OCR
        """
        try:
            # Convertir bytes a imagen PIL
            img = Image.open(io.BytesIO(img_block.image_data))
            return self._ocr_pil_image(img, img_block.page_num, img_block.bbox)

        except Exception as e:
            logger.error(f"Error en OCR de imagen: {e}")
            return []

    def _ocr_pil_image(
        self,
        img: Image.Image,
        page_num: int,
        bbox: tuple[float, float, float, float],
    ) -> List[OCRResult]:
        """
        Aplica OCR a una imagen PIL

        Args:
            img: Imagen PIL
            page_num: Número de página
            bbox: Coordenadas en el PDF

        Returns:
            Lista de resultados OCR
        """
        if not self.tesseract_available:
            logger.warning("Tesseract no disponible, omitiendo OCR")
            return []

        results = []

        try:
            # Configurar Tesseract
            config = f"--oem 3 --psm 6 -l {self.settings.ocr_language}"

            # Obtener datos con coordenadas
            data = pytesseract.image_to_data(
                img, config=config, output_type=pytesseract.Output.DICT
            )

            # Procesar resultados
            n_boxes = len(data["text"])
            img_width, img_height = img.size

            for i in range(n_boxes):
                text = data["text"][i].strip()
                confidence = float(data["conf"][i])

                if text and confidence > 0:
                    # Coordenadas relativas a la imagen
                    x = data["left"][i]
                    y = data["top"][i]
                    w = data["width"][i]
                    h = data["height"][i]

                    # Convertir a coordenadas del PDF
                    bbox_width = bbox[2] - bbox[0]
                    bbox_height = bbox[3] - bbox[1]

                    x0 = bbox[0] + (x / img_width) * bbox_width
                    y0 = bbox[1] + (y / img_height) * bbox_height
                    x1 = x0 + (w / img_width) * bbox_width
                    y1 = y0 + (h / img_height) * bbox_height

                    results.append(
                        OCRResult(
                            text=text,
                            bbox=(x0, y0, x1, y1),
                            confidence=confidence / 100.0,
                            page_num=page_num,
                            source="tesseract",
                        )
                    )

        except Exception as e:
            logger.error(f"Error ejecutando Tesseract: {e}")

        return results
