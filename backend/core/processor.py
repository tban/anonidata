"""
Procesador principal de PDFs
Orquesta todos los módulos (OCR, detección, anonimización)
"""

import time
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from core.config import Settings
from processors.pdf_parser import PDFParser
from processors.ocr_engine import OCREngine
from detectors.pii_detector import PIIDetector
from processors.anonymizer import Anonymizer
from utils.file_manager import FileManager


class PDFProcessor:
    """Procesador principal de PDFs"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.pdf_parser = PDFParser()
        self.ocr_engine = OCREngine(settings)
        self.pii_detector = PIIDetector(settings)
        self.anonymizer = Anonymizer(settings)
        self.file_manager = FileManager(settings)

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Procesa un archivo PDF completo

        Args:
            file_path: Ruta al archivo PDF

        Returns:
            Diccionario con resultados del procesamiento
        """
        start_time = time.time()
        input_path = Path(file_path)

        logger.info(f"Procesando: {input_path.name}")

        try:
            # Validar archivo
            self.file_manager.validate_pdf(input_path)

            # 1. Parsear PDF
            logger.debug("Parseando PDF...")
            pdf_data = self.pdf_parser.parse(input_path)

            # 2. Aplicar OCR si es necesario
            logger.debug("Aplicando OCR...")
            ocr_data = self.ocr_engine.process(pdf_data)

            # 3. Detectar PII
            logger.debug("Detectando datos personales...")
            pii_matches = self.pii_detector.detect(pdf_data, ocr_data)

            # 4. Anonimizar
            logger.debug("Anonimizando...")
            output_path = self.anonymizer.anonymize(
                input_path,
                pdf_data,
                pii_matches
            )

            # 5. Limpiar metadatos
            logger.debug("Limpiando metadatos...")
            self.file_manager.clean_metadata(output_path)

            # Calcular estadísticas
            stats = self._calculate_stats(pii_matches)

            processing_time = time.time() - start_time

            logger.info(f"Completado: {input_path.name} ({processing_time:.2f}s)")

            return {
                "inputFile": str(input_path),
                "outputFile": str(output_path),
                "status": "success",
                "stats": stats,
                "processingTime": processing_time,
            }

        except Exception as e:
            logger.error(f"Error procesando {input_path.name}: {e}", exc_info=True)
            return {
                "inputFile": str(input_path),
                "status": "error",
                "error": str(e),
                "processingTime": time.time() - start_time,
            }

        finally:
            # Limpiar archivos temporales
            if self.settings.auto_clean_temp:
                self.file_manager.cleanup_temp()

    def _calculate_stats(self, pii_matches: list) -> Dict[str, int]:
        """Calcula estadísticas de datos detectados"""
        stats = {
            "dniCount": 0,
            "nameCount": 0,
            "addressCount": 0,
            "phoneCount": 0,
            "emailCount": 0,
            "signatureCount": 0,
            "qrCount": 0,
        }

        for match in pii_matches:
            pii_type = match.type

            if pii_type in ["DNI", "NIE"]:
                stats["dniCount"] += 1
            elif pii_type == "PERSON":
                stats["nameCount"] += 1
            elif pii_type == "ADDRESS":
                stats["addressCount"] += 1
            elif pii_type == "PHONE":
                stats["phoneCount"] += 1
            elif pii_type == "EMAIL":
                stats["emailCount"] += 1
            elif pii_type == "SIGNATURE":
                stats["signatureCount"] += 1
            elif pii_type == "QR_CODE":
                stats["qrCount"] += 1

        return stats
