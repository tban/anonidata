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
            self.pii_detector.set_pdf_path(input_path)
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

            # Detectar si el PDF es principalmente imágenes escaneadas
            warnings = []
            if len(ocr_data.pages_processed) > 0:
                ocr_percentage = (len(ocr_data.pages_processed) / pdf_data.page_count) * 100
                if ocr_percentage >= 80:
                    warnings.append(
                        f"Este PDF contiene principalmente imágenes escaneadas ({int(ocr_percentage)}% de páginas). "
                        "La detección de PII puede tener limitaciones. Se recomienda revisión manual exhaustiva."
                    )
                    logger.warning(f"PDF con {int(ocr_percentage)}% de páginas escaneadas: {input_path.name}")

            processing_time = time.time() - start_time

            logger.info(f"Completado: {input_path.name} ({processing_time:.2f}s)")

            result = {
                "inputFile": str(input_path),
                "outputFile": str(output_path),
                "status": "success",
                "stats": stats,
                "processingTime": processing_time,
            }

            if warnings:
                result["warnings"] = warnings

            return result

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
            pii_type = match.type.upper()

            # DNI/NIE (incluye reglas basadas en configuración)
            if pii_type in ["DNI", "NIE", "DNI_NIE", "DNI_NIE_CON_ETIQUETA", "DNI_NIE_SIN_ETIQUETA"]:
                stats["dniCount"] += 1
            # Nombres y apellidos (incluye reglas basadas en configuración)
            elif pii_type in ["PERSON", "NOMBRES_APELLIDOS", "NOMBRES_CON_PREFIJO"]:
                stats["nameCount"] += 1
            # Direcciones y domicilios (incluye reglas basadas en configuración)
            elif pii_type in ["ADDRESS", "DOMICILIOS", "DOMICILIO_CON_ETIQUETA"]:
                stats["addressCount"] += 1
            # Teléfonos (incluye reglas basadas en configuración)
            elif pii_type in ["PHONE", "TELEFONOS"]:
                stats["phoneCount"] += 1
            # Emails
            elif pii_type in ["EMAIL"]:
                stats["emailCount"] += 1
            # Firmas
            elif pii_type == "SIGNATURE":
                stats["signatureCount"] += 1
            # QR codes
            elif pii_type == "QR_CODE":
                stats["qrCount"] += 1

        return stats
