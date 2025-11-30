"""
Detector de Información Personal Identificable (PII)
Combina regex, NLP y detección visual
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger

try:
    import spacy
    from spacy.language import Language
except ImportError:
    logger.warning("spaCy no instalado")
    spacy = None

from core.config import Settings
from processors.pdf_parser import PDFData, TextBlock
from processors.ocr_engine import OCRData, OCRResult
from detectors.regex_patterns import RegexPatterns
from detectors.visual_detector import VisualDetector
from detectors.models import PIIMatch
from detectors.rule_based_detector import RuleBasedDetector


class PIIDetector:
    """Detector principal de PII"""

    def __init__(self, settings: Settings, pdf_path: Optional[Any] = None):
        self.settings = settings
        self.regex_patterns = RegexPatterns()
        self.visual_detector = VisualDetector(settings)
        self.rule_based_detector = RuleBasedDetector()
        self.pdf_path = pdf_path

        # Cargar modelo NLP
        self.nlp: Optional[Language] = None
        if settings.detect_names or settings.detect_addresses:
            self._load_nlp_model()

    def _load_nlp_model(self):
        """Carga el modelo de spaCy"""
        if spacy is None:
            logger.warning("spaCy no disponible, detección NER deshabilitada")
            return

        try:
            # Intentar cargar modelo español
            self.nlp = spacy.load("es_core_news_lg")
            logger.debug("Modelo spaCy cargado: es_core_news_lg")
        except OSError:
            try:
                # Fallback a modelo pequeño
                self.nlp = spacy.load("es_core_news_sm")
                logger.debug("Modelo spaCy cargado: es_core_news_sm")
            except OSError:
                logger.warning(
                    "Modelo spaCy no encontrado. "
                    "Ejecutar: python -m spacy download es_core_news_lg"
                )

    def set_pdf_path(self, pdf_path: Any):
        """Establece la ruta del PDF para el detector basado en reglas"""
        self.pdf_path = pdf_path

    def detect(self, pdf_data: PDFData, ocr_data: OCRData) -> List[PIIMatch]:
        """
        Detecta PII en el documento

        Args:
            pdf_data: Datos del PDF
            ocr_data: Datos del OCR

        Returns:
            Lista de matches de PII
        """
        matches = []

        # 1. NUEVO: Detección basada en reglas configurables (con bboxes precisas)
        if self.pdf_path:
            logger.debug("Detectando PII con reglas configurables...")
            rule_matches = self.rule_based_detector.detect_in_text_blocks(
                pdf_data.text_blocks,
                self.pdf_path
            )
            matches.extend(rule_matches)

            # También en bloques OCR
            ocr_text_blocks = self._convert_ocr_to_text_blocks(ocr_data.results)
            rule_ocr_matches = self.rule_based_detector.detect_in_text_blocks(
                ocr_text_blocks,
                self.pdf_path
            )
            matches.extend(rule_ocr_matches)

        # 2. Detección NER (nombres, direcciones) - solo si está habilitada
        if self.nlp:
            logger.debug("Detectando PII con NER...")
            ocr_text_blocks = self._convert_ocr_to_text_blocks(ocr_data.results)
            ner_matches = self._detect_with_ner(pdf_data.text_blocks)
            matches.extend(ner_matches)

            # NER en OCR también
            ner_ocr_matches = self._detect_with_ner(ocr_text_blocks)
            matches.extend(ner_ocr_matches)

        # 3. Detección visual (firmas, QR codes)
        logger.debug("Detectando PII visual...")
        visual_matches = self.visual_detector.detect(pdf_data)
        matches.extend(visual_matches)

        # Eliminar duplicados (solapamiento)
        matches = self._remove_duplicates(matches)

        logger.info(f"Detectados {len(matches)} elementos PII")

        return matches

    def _convert_ocr_to_text_blocks(self, ocr_results: List[OCRResult]) -> List[TextBlock]:
        """Convierte resultados OCR a TextBlocks"""
        from processors.pdf_parser import TextBlock

        blocks = []
        for result in ocr_results:
            blocks.append(
                TextBlock(
                    text=result.text,
                    bbox=result.bbox,
                    page_num=result.page_num,
                    font_size=0,
                    font_name="OCR",
                )
            )
        return blocks

    def _detect_with_regex(self, text_blocks: List[TextBlock]) -> List[PIIMatch]:
        """Detecta PII usando patrones regex"""
        matches = []

        for block in text_blocks:
            text = block.text

            # DNI
            if self.settings.detect_dni:
                for match in self.regex_patterns.find_dni(text):
                    matches.append(
                        PIIMatch(
                            type="DNI",
                            text=match,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # NIE
            if self.settings.detect_nie:
                for match in self.regex_patterns.find_nie(text):
                    matches.append(
                        PIIMatch(
                            type="NIE",
                            text=match,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # Email
            if self.settings.detect_emails:
                for match in self.regex_patterns.find_email(text):
                    matches.append(
                        PIIMatch(
                            type="EMAIL",
                            text=match,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # Teléfono
            if self.settings.detect_phones:
                for match in self.regex_patterns.find_phone(text):
                    matches.append(
                        PIIMatch(
                            type="PHONE",
                            text=match,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # IBAN
            if self.settings.detect_iban:
                for match in self.regex_patterns.find_iban(text):
                    matches.append(
                        PIIMatch(
                            type="IBAN",
                            text=match,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

        return matches

    def _detect_with_ner(self, text_blocks: List[TextBlock]) -> List[PIIMatch]:
        """Detecta PII usando NER de spaCy"""
        if not self.nlp:
            return []

        matches = []

        for block in text_blocks:
            doc = self.nlp(block.text)

            for ent in doc.ents:
                # Nombres de personas
                if ent.label_ == "PER" and self.settings.detect_names:
                    matches.append(
                        PIIMatch(
                            type="PERSON",
                            text=ent.text,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=0.9,
                            source="ner",
                        )
                    )

                # Direcciones/Localizaciones
                elif ent.label_ == "LOC" and self.settings.detect_addresses:
                    matches.append(
                        PIIMatch(
                            type="ADDRESS",
                            text=ent.text,
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=0.8,
                            source="ner",
                        )
                    )

        return matches

    def _remove_duplicates(self, matches: List[PIIMatch]) -> List[PIIMatch]:
        """
        Elimina matches duplicados que se solapan

        Args:
            matches: Lista de matches

        Returns:
            Lista filtrada
        """
        if not matches:
            return []

        # Ordenar por confianza (mayor primero)
        sorted_matches = sorted(matches, key=lambda m: m.confidence, reverse=True)

        filtered = []
        for match in sorted_matches:
            # Verificar si solapa con alguno ya agregado
            overlaps = False
            for existing in filtered:
                if self._boxes_overlap(match, existing):
                    overlaps = True
                    break

            if not overlaps:
                filtered.append(match)

        return filtered

    def _boxes_overlap(self, match1: PIIMatch, match2: PIIMatch) -> bool:
        """Verifica si dos bounding boxes se solapan significativamente"""
        if match1.page_num != match2.page_num:
            return False

        x0_1, y0_1, x1_1, y1_1 = match1.bbox
        x0_2, y0_2, x1_2, y1_2 = match2.bbox

        # Calcular intersección
        x_overlap = max(0, min(x1_1, x1_2) - max(x0_1, x0_2))
        y_overlap = max(0, min(y1_1, y1_2) - max(y0_1, y0_2))

        if x_overlap == 0 or y_overlap == 0:
            return False

        intersection = x_overlap * y_overlap

        # Calcular áreas
        area1 = (x1_1 - x0_1) * (y1_1 - y0_1)
        area2 = (x1_2 - x0_2) * (y1_2 - y0_2)

        # Solapamiento significativo si > 50% de área menor
        min_area = min(area1, area2)
        overlap_ratio = intersection / min_area if min_area > 0 else 0

        return overlap_ratio > 0.5
