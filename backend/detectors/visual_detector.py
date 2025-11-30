"""
Detector visual para firmas, sellos y códigos QR
"""

import io
from typing import List
from dataclasses import dataclass
from loguru import logger

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError:
    logger.warning("opencv-python no instalado")
    cv2 = None

try:
    from pyzbar import pyzbar
except ImportError:
    logger.warning("pyzbar no instalado")
    pyzbar = None

from core.config import Settings
from processors.pdf_parser import PDFData, ImageBlock
from detectors.models import PIIMatch


class VisualDetector:
    """Detector de elementos visuales (firmas, QR, etc)"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def detect(self, pdf_data: PDFData) -> List[PIIMatch]:
        """
        Detecta elementos visuales en el PDF

        Args:
            pdf_data: Datos del PDF

        Returns:
            Lista de matches
        """
        matches = []

        for img_block in pdf_data.image_blocks:
            # Detectar QR codes
            if self.settings.detect_qr_codes:
                qr_matches = self._detect_qr_codes(img_block)
                matches.extend(qr_matches)

            # Detectar firmas (heurística simple)
            if self.settings.detect_signatures:
                signature_matches = self._detect_signatures(img_block)
                matches.extend(signature_matches)

        return matches

    def _detect_qr_codes(self, img_block: ImageBlock) -> List[PIIMatch]:
        """
        Detecta códigos QR en una imagen

        Args:
            img_block: Bloque de imagen

        Returns:
            Lista de matches
        """
        if pyzbar is None:
            return []

        try:
            img = Image.open(io.BytesIO(img_block.image_data))
            img_array = np.array(img)

            # Detectar códigos
            codes = pyzbar.decode(img_array)

            matches = []
            for code in codes:
                # Usar bbox de toda la imagen (simplificado)
                matches.append(
                    PIIMatch(
                        type="QR_CODE",
                        text="QR Code",
                        bbox=img_block.bbox,
                        page_num=img_block.page_num,
                        confidence=1.0,
                        source="visual",
                    )
                )

            return matches

        except Exception as e:
            logger.warning(f"Error detectando QR codes: {e}")
            return []

    def _detect_signatures(self, img_block: ImageBlock) -> List[PIIMatch]:
        """
        Detecta firmas usando heurística simple

        Nota: Esta es una implementación básica. Para producción,
        considerar usar un modelo ML entrenado.

        Args:
            img_block: Bloque de imagen

        Returns:
            Lista de matches
        """
        if cv2 is None:
            return []

        try:
            # Solo procesar imágenes pequeñas/medianas
            # (firmas suelen ser pequeñas)
            if img_block.width > 1000 or img_block.height > 1000:
                return []

            img = Image.open(io.BytesIO(img_block.image_data))
            img_array = np.array(img)

            # Convertir a escala de grises
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array

            # Detectar si hay contenido tipo "firma"
            # Heurística: imagen con poco texto pero con trazos
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            # Si tiene densidad de bordes característica de firma
            is_signature = 0.01 < edge_density < 0.3

            if is_signature:
                return [
                    PIIMatch(
                        type="SIGNATURE",
                        text="Posible firma",
                        bbox=img_block.bbox,
                        page_num=img_block.page_num,
                        confidence=0.7,  # Baja confianza (heurística simple)
                        source="visual",
                    )
                ]

            return []

        except Exception as e:
            logger.warning(f"Error detectando firmas: {e}")
            return []
