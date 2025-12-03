"""
Detector de Información Personal Identificable (PII)
Combina regex, NLP y detección visual
"""

import re
from typing import List, Dict, Any, Optional, Tuple
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

        logger.info("Intentando cargar modelo spaCy para NER...")

        # Si estamos en PyInstaller, buscar modelo en la carpeta empaquetada
        import sys
        from pathlib import Path

        model_names = ["es_core_news_lg", "es_core_news_sm"]

        for model_name in model_names:
            try:
                # Primero intentar carga normal
                self.nlp = spacy.load(model_name)
                logger.info(f"✓ Modelo spaCy cargado exitosamente: {model_name}")
                return
            except OSError:
                # Si falla, intentar buscar en PyInstaller
                try:
                    base_path = Path(sys._MEIPASS)
                    model_path = base_path / "spacy" / "data" / model_name
                    if model_path.exists():
                        logger.info(f"Intentando cargar modelo desde PyInstaller: {model_path}")
                        self.nlp = spacy.load(str(model_path))
                        logger.info(f"✓ Modelo spaCy cargado exitosamente desde PyInstaller: {model_name}")
                        return
                except (AttributeError, OSError) as e:
                    logger.debug(f"No se pudo cargar {model_name} desde PyInstaller: {e}")
                    continue

        logger.error(
            "Modelo spaCy no encontrado. "
            "Ejecutar: python -m spacy download es_core_news_lg"
        )
        self.nlp = None

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

        # 1. Detección basada en reglas configurables (con bboxes precisas)
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

        # 2. Detección con regex tradicional (DNI, NIE, teléfonos, emails, etc.)
        logger.debug("Detectando PII con regex...")
        regex_matches = self._detect_with_regex(pdf_data.text_blocks)
        matches.extend(regex_matches)

        # También en OCR
        ocr_text_blocks = self._convert_ocr_to_text_blocks(ocr_data.results)
        regex_ocr_matches = self._detect_with_regex(ocr_text_blocks)
        matches.extend(regex_ocr_matches)

        # 3. Detección NER (nombres) - solo si está habilitada
        logger.debug(f"NER check: self.nlp={'loaded' if self.nlp else 'None'}, detect_names={self.settings.detect_names}")
        if self.nlp:
            logger.debug("Detectando nombres con NER (IA)...")
            ner_matches = self._detect_with_ner(pdf_data.text_blocks)
            logger.debug(f"NER encontró {len(ner_matches)} nombres en texto extraído")
            matches.extend(ner_matches)

            # NER en OCR también
            ner_ocr_matches = self._detect_with_ner(ocr_text_blocks)
            logger.debug(f"NER encontró {len(ner_ocr_matches)} nombres en OCR")
            matches.extend(ner_ocr_matches)
        else:
            logger.warning("NER no disponible - modelo spaCy no cargado")

        # 4. Detección de direcciones con palabras clave
        logger.debug("Detectando direcciones...")
        address_matches = self._detect_addresses(pdf_data.text_blocks)
        matches.extend(address_matches)

        # También en OCR
        address_ocr_matches = self._detect_addresses(ocr_text_blocks)
        matches.extend(address_ocr_matches)

        # 5. Detección visual (firmas, QR codes)
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
        """Detecta PII usando patrones regex (preserva etiquetas DNI/NIE)"""
        matches = []

        # Abrir el PDF para calcular bboxes precisas
        doc_pdf = None
        if self.pdf_path:
            try:
                import fitz
                doc_pdf = fitz.open(self.pdf_path)
            except Exception as e:
                logger.warning(f"No se pudo abrir PDF para cálculo preciso de bboxes en regex: {e}")

        for block in text_blocks:
            text = block.text

            # DNI/NIF con etiqueta "DNI:", "NIF" - preservar etiqueta, redactar solo número
            if self.settings.detect_dni:
                # Buscar patrón "DNI: 12345678X", "NIF 12345678X", etc.
                dni_pattern = re.compile(r'((?:DNI|NIF):?\s*)(\d{8}[A-Za-z])\b', re.IGNORECASE)
                for match in dni_pattern.finditer(text):
                    # Solo redactar el número (grupo 2), no la etiqueta (grupo 1)
                    dni_number = match.group(2)

                    # Calcular bbox precisa solo para el número
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            text_instances = page.search_for(dni_number)

                            if text_instances:
                                found = False
                                for rect in text_instances:
                                    if self._rect_inside_bbox(rect, block.bbox):
                                        precise_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                                        found = True
                                        break

                                if not found and text_instances:
                                    rect = text_instances[0]
                                    precise_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                        except Exception as e:
                            logger.warning(f"Error calculando bbox precisa para DNI: {e}")

                    matches.append(
                        PIIMatch(
                            type="DNI",
                            text=dni_number,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # NIE con etiqueta "NIE:" - preservar etiqueta, redactar solo número
            if self.settings.detect_nie:
                # Buscar patrón "NIE: X1234567A" o "NIE X1234567A"
                nie_pattern = re.compile(r'(NIE:?\s*)([XYZxyz]\d{7}[A-Za-z])\b', re.IGNORECASE)
                for match in nie_pattern.finditer(text):
                    # Solo redactar el número (grupo 2), no la etiqueta (grupo 1)
                    nie_number = match.group(2)

                    # Calcular bbox precisa solo para el número
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            text_instances = page.search_for(nie_number)

                            if text_instances:
                                found = False
                                for rect in text_instances:
                                    if self._rect_inside_bbox(rect, block.bbox):
                                        precise_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                                        found = True
                                        break

                                if not found and text_instances:
                                    rect = text_instances[0]
                                    precise_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                        except Exception as e:
                            logger.warning(f"Error calculando bbox precisa para NIE: {e}")

                    matches.append(
                        PIIMatch(
                            type="NIE",
                            text=nie_number,
                            bbox=precise_bbox,
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

        # Cerrar el PDF si lo abrimos
        if doc_pdf:
            doc_pdf.close()

        return matches

    def _detect_with_ner(self, text_blocks: List[TextBlock]) -> List[PIIMatch]:
        """Detecta PII usando NER de spaCy (solo nombres de personas)"""
        if not self.nlp:
            logger.warning("_detect_with_ner llamado pero self.nlp es None")
            return []

        matches = []
        total_entities = 0

        # Lista de palabras que NO son nombres de personas (falsos positivos comunes)
        false_positives = {
            # Cargos y roles
            'jefe', 'jefa', 'director', 'directora', 'gerente', 'responsable',
            'coordinador', 'coordinadora', 'técnico', 'técnica', 'secretario',
            'secretaria', 'presidente', 'presidenta', 'vocal', 'empleado', 'empleada',
            'jefe de sección', 'jefa de sección', 'secretario general',
            # Números ordinales
            'primero', 'segundo', 'tercero', 'cuarto', 'quinto', 'sexto',
            'séptimo', 'octavo', 'noveno', 'décimo',
            'primera', 'segunda', 'tercera', 'cuarta', 'quinta', 'sexta',
            'séptima', 'octava', 'novena', 'décima',
            # Términos administrativos
            'interesado', 'interesada', 'solicitante', 'titular', 'beneficiario',
            'beneficiaria', 'representante', 'apoderado', 'apoderada',
            # Abreviaturas de firma
            'fdo', 'fdo.', 'firmado', 'firma', 'atentamente', 'atte', 'atte.',
            # Títulos y tratamientos
            'don', 'd.', 'doña', 'dña', 'dña.', 'sr', 'sr.', 'sra', 'sra.',
            # Términos legales/administrativos
            'desestima', 'estima', 'aprueba', 'deniega', 'concede', 'válida', 'válido',
            'anula', 'nula', 'nulo', 'resuelve', 'acuerda', 'declara',
            # Términos organizativos
            'general', 'dirección', 'servicio', 'área', 'departamento', 'sección',
        }

        # Palabras clave de direcciones (para filtrar false positives del NER)
        address_keywords_filter = [
            'calle', 'c/', 'avenida', 'avda', 'av.', 'plaza', 'pl.',
            'paseo', 'pº', 'camino', 'cam.', 'carretera', 'ctra.',
            'travesía', 'trv.', 'urbanización', 'urb.', 'glorieta',
            'ronda', 'vía', 'domicilio', 'dirección'
        ]

        # Abrir el PDF para calcular bboxes precisas
        doc_pdf = None
        if self.pdf_path:
            try:
                import fitz
                doc_pdf = fitz.open(self.pdf_path)
            except Exception as e:
                logger.warning(f"No se pudo abrir PDF para cálculo preciso de bboxes: {e}")

        for block in text_blocks:
            doc = self.nlp(block.text)

            # Log de todas las entidades encontradas para debug
            if doc.ents:
                total_entities += len(doc.ents)
                logger.debug(f"Página {block.page_num}: Encontradas {len(doc.ents)} entidades: {[(e.text, e.label_) for e in doc.ents]}")

            for ent in doc.ents:
                # Nombres de personas - detectar en todo el documento
                if ent.label_ == "PER" and self.settings.detect_names:
                    # Filtrar falsos positivos
                    entity_text_lower = ent.text.lower().strip()

                    # Saltar si es un falso positivo conocido
                    if entity_text_lower in false_positives:
                        logger.debug(f"Filtrado falso positivo: '{ent.text}' en página {block.page_num}")
                        continue

                    # Saltar si contiene palabras clave de direcciones
                    # Ej: "Calle Matos", "Plaza Mayor"
                    contains_address_keyword = False
                    for keyword in address_keywords_filter:
                        if keyword in entity_text_lower:
                            logger.debug(f"Filtrado dirección como persona: '{ent.text}' (contiene '{keyword}') en página {block.page_num}")
                            contains_address_keyword = True
                            break
                    if contains_address_keyword:
                        continue

                    # Saltar si solo es una palabra y parece un cargo (no tiene apellido)
                    # Los nombres reales suelen tener al menos 2 palabras
                    words = ent.text.split()
                    if len(words) == 1 and entity_text_lower in false_positives:
                        logger.debug(f"Filtrado palabra única no válida: '{ent.text}' en página {block.page_num}")
                        continue

                    # Calcular bbox precisa si tenemos el PDF abierto
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            text_instances = page.search_for(ent.text)

                            if text_instances:
                                # Si hay múltiples instancias, usar la que esté dentro del block_bbox
                                found = False
                                for rect in text_instances:
                                    if self._rect_inside_bbox(rect, block.bbox):
                                        precise_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                                        found = True
                                        break

                                # Si ninguna está dentro, usar la primera
                                if not found:
                                    rect = text_instances[0]
                                    precise_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)

                                logger.debug(f"Bbox precisa calculada para '{ent.text}': {precise_bbox}")
                            else:
                                logger.debug(f"No se encontró bbox precisa para '{ent.text}', usando bbox del bloque")
                        except Exception as e:
                            logger.warning(f"Error calculando bbox precisa para '{ent.text}': {e}")

                    logger.debug(f"Detectado nombre válido: '{ent.text}' en página {block.page_num}")
                    matches.append(
                        PIIMatch(
                            type="PERSON",
                            text=ent.text,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=0.9,
                            source="ner",
                        )
                    )

        # Cerrar el PDF si lo abrimos
        if doc_pdf:
            doc_pdf.close()

        logger.debug(f"NER procesó bloques y encontró {total_entities} entidades totales, {len(matches)} son personas (PER) válidas")
        return matches

    def _detect_addresses(self, text_blocks: List[TextBlock]) -> List[PIIMatch]:
        """
        Detecta direcciones usando palabras clave españolas
        Busca palabras como Calle, C/, Avenida, Plaza, etc.
        """
        if not self.settings.detect_addresses:
            return []

        matches = []

        # Palabras clave que indican el inicio de una dirección
        # NOTA: "Plaza" se excluye porque en documentos administrativos
        # suele referirse a puestos de trabajo, no a espacios urbanos
        address_keywords = [
            r'Domicilio:?\s*',
            r'Dirección:?\s*',
            r'C/',
            r'Calle\s+',
            r'Av\.',
            r'Avda\.',
            r'Avenida\s+',
            # r'Pl\.',  # Comentado: causa falsos positivos con "plaza" (puesto de trabajo)
            # r'Plaza\s+',  # Comentado: causa falsos positivos con "plaza" (puesto de trabajo)
            r'Pº\s+',
            r'Paseo\s+',
            r'Camino\s+',
            r'Cam\.\s+',
            r'Carretera\s+',
            r'Ctra\.\s+',
            r'Travesía\s+',
            r'Trv\.\s+',
            r'Urbanización\s+',
            r'Urb\.\s+',
            r'Glorieta\s+',
            r'Ronda\s+',
            r'Vía\s+',
        ]

        # Crear patrón que busque: palabra clave + nombre de calle + número (opcional)
        # Ejemplo: "Calle Mayor 123" o "C/ de la Paz 45"
        # Requiere al menos UNA palabra real después de la palabra clave
        address_pattern = re.compile(
            r'(' + '|'.join(address_keywords) + r')' +  # Palabra clave
            # Nombre de calle: Debe empezar con una palabra REAL (no preposición)
            # Luego opcionalmente puede tener preposición + palabra (hasta 3 veces)
            r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+(?:de|del|la|los|las|el|y)\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,3})' +
            # Número (opcional): reconoce "nº", "núm.", "número"
            r'(?:\s*[,]?\s*(?:nº|n°|núm\.?|número)?\s*(\d{1,4}(?:\s*[A-Za-z])?))?' +
            # Código postal (opcional)
            r'(?:\s*[,]?\s*(\d{5}))?' +
            # Detenerse en: coma, punto, punto y coma, dos puntos, o final de línea
            r'(?=[,\.\;\:]|\s*$|(?:\s+[A-Z]))',
            re.IGNORECASE
        )

        # Términos que indican puesto de trabajo, no dirección física
        job_position_indicators = [
            'técnico', 'interino', 'funcionario', 'empleado', 'vacante',
            'ofertada', 'personal', 'categoría', 'especialidad', 'servicio',
            'atención primaria', 'adjudicada', 'ocupo', 'desempeño', 'puesto'
        ]

        for block in text_blocks:
            text = block.text

            for match in address_pattern.finditer(text):
                # Capturar toda la dirección excepto la palabra clave inicial si es "Domicilio:" o "Dirección:"
                matched_text = match.group(0)
                keyword = match.group(1)

                # Filtrar falsos positivos: "plaza de técnico", "plaza vacante", etc.
                # Estas son puestos de trabajo, NO direcciones físicas
                if keyword.strip().lower().startswith('plaza'):
                    # Buscar contexto después del match
                    match_end = match.end()
                    context = text[match_end:match_end+100].lower()

                    # Si después de "plaza" viene un indicador de puesto de trabajo, saltar
                    is_job_position = any(indicator in matched_text.lower() or indicator in context
                                        for indicator in job_position_indicators)
                    if is_job_position:
                        logger.debug(f"Filtrado 'plaza' como puesto de trabajo, no dirección: '{matched_text}'")
                        continue

                # Si la palabra clave es "Domicilio:" o "Dirección:", solo redactar la dirección, no la etiqueta
                if keyword.strip().lower().startswith(('domicilio', 'dirección')):
                    # Redactar solo la dirección (grupos 2, 3, 4)
                    address_parts = []
                    if match.group(2):  # Nombre de calle
                        address_parts.append(match.group(2).strip())
                    if match.group(3):  # Número
                        address_parts.append(match.group(3).strip())
                    if match.group(4):  # Código postal
                        address_parts.append(match.group(4).strip())

                    if address_parts:
                        address_text = ' '.join(address_parts)
                        matches.append(
                            PIIMatch(
                                type="ADDRESS",
                                text=address_text,
                                bbox=block.bbox,
                                page_num=block.page_num,
                                confidence=0.85,
                                source="address_detector",
                            )
                        )
                else:
                    # Para otras palabras clave, redactar todo
                    matches.append(
                        PIIMatch(
                            type="ADDRESS",
                            text=matched_text.strip(),
                            bbox=block.bbox,
                            page_num=block.page_num,
                            confidence=0.85,
                            source="address_detector",
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

        # NUEVO: Solo considerar duplicado si el texto es idéntico
        # Esto permite que "Juan García" aparezca múltiples veces en el mismo bloque
        # pero evita que "Juan García" se considere duplicado de "García Pérez"
        if match1.text.lower().strip() != match2.text.lower().strip():
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

    def _rect_inside_bbox(self, rect, bbox: Tuple[float, float, float, float]) -> bool:
        """
        Verifica si un rectángulo está dentro de una bbox

        Args:
            rect: Rectángulo de PyMuPDF (fitz.Rect)
            bbox: Tupla (x0, y0, x1, y1)

        Returns:
            True si rect está dentro de bbox
        """
        try:
            x0, y0, x1, y1 = bbox

            # Validar que ninguna coordenada sea None
            if None in (x0, y0, x1, y1):
                logger.warning(f"Bbox contiene valores None: {bbox}")
                return False

            # Verificar si el centro del rect está dentro del bbox
            center_x = (rect.x0 + rect.x1) / 2
            center_y = (rect.y0 + rect.y1) / 2

            return (x0 <= center_x <= x1) and (y0 <= center_y <= y1)

        except (TypeError, ValueError) as e:
            logger.warning(f"Error en _rect_inside_bbox: {e}, bbox={bbox}")
            return False
