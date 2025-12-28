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

        # Usar solo modelo pequeño para reducir tamaño del paquete
        # es_core_news_sm es suficiente para detección de personas/lugares (17 MB vs 624 MB del lg)
        model_name = "es_core_news_sm"

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

        logger.error(
            "Modelo spaCy no encontrado. "
            "Ejecutar: python -m spacy download es_core_news_sm"
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

        # También detectar DNI/NIE en texto completo de página para capturar casos fragmentados
        if self.pdf_path:
            logger.debug("Detectando DNI/NIE en texto completo de páginas...")
            fullpage_dni_matches = self._detect_dni_nie_in_fullpage()
            matches.extend(fullpage_dni_matches)

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

        # También detectar en texto completo de página para capturar direcciones que cruzan bloques
        if self.pdf_path:
            logger.debug("Detectando direcciones en texto completo de páginas...")
            fullpage_address_matches = self._detect_addresses_in_fullpage()
            matches.extend(fullpage_address_matches)

        # También en OCR
        address_ocr_matches = self._detect_addresses(ocr_text_blocks)
        matches.extend(address_ocr_matches)

        # 5. Detección visual (firmas, QR codes)
        logger.debug("Detectando PII visual...")
        visual_matches = self.visual_detector.detect(pdf_data)
        matches.extend(visual_matches)

        # 6. Detección de partes individuales de nombres (apellidos/nombres sueltos)
        # OPTIMIZACIÓN: Deshabilitar para PDFs grandes (>50 páginas) por rendimiento
        total_pages = len(pdf_data.text_blocks)  # Aproximación del número de páginas
        if total_pages <= 50:
            logger.debug("Detectando partes individuales de nombres...")
            all_text_blocks = pdf_data.text_blocks + ocr_text_blocks
            name_part_matches = self._detect_name_parts(matches, all_text_blocks)
            logger.debug(f"Detección de partes encontró {len(name_part_matches)} ocurrencias adicionales")
            matches.extend(name_part_matches)
        else:
            logger.info(f"PDF grande ({total_pages} páginas aprox), saltando detección de partes de nombres para mejor rendimiento")

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
                # Buscar patrón "DNI: 12345678X", "NIF 12345678X", "DNI núm. 12345678X", etc.
                # Contempla variaciones: DNI, NIF, con o sin :, con núm/nº/n.º
                dni_pattern = re.compile(r'((?:DNI|NIF)(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)(\d{8}[A-Za-z])\b', re.IGNORECASE)
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
                # Buscar patrón "NIE: X1234567A", "NIE X1234567A", "NIE núm. X1234567A", etc.
                # Contempla variaciones: NIE, con o sin :, con núm/nº/n.º
                nie_pattern = re.compile(r'(NIE(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)([XYZxyz]\d{7}[A-Za-z])\b', re.IGNORECASE)
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
                    # Calcular bbox precisa solo para el email
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            text_instances = page.search_for(match)

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
                            logger.warning(f"Error calculando bbox precisa para EMAIL: {e}")

                    matches.append(
                        PIIMatch(
                            type="EMAIL",
                            text=match,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # Teléfono
            if self.settings.detect_phones:
                for match in self.regex_patterns.find_phone(text):
                    # Calcular bbox precisa solo para el teléfono
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            text_instances = page.search_for(match)

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
                            logger.warning(f"Error calculando bbox precisa para PHONE: {e}")

                    matches.append(
                        PIIMatch(
                            type="PHONE",
                            text=match,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # IBAN
            if self.settings.detect_iban:
                for match in self.regex_patterns.find_iban(text):
                    # Calcular bbox precisa solo para el IBAN
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            text_instances = page.search_for(match)

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
                            logger.warning(f"Error calculando bbox precisa para IBAN: {e}")

                    matches.append(
                        PIIMatch(
                            type="IBAN",
                            text=match,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # Nombres con tratamiento formal o firma (D./Doña/Fdo.)
            # RESTRICCIÓN SOLICITADA: Solo detectar si aparece uno de estos prefijos
            if self.settings.detect_names:
                # Patrón para tratamientos y firmas:
                # D., Don, Doña, Dña., Sr., Sra., Dr., Dra., Fdo., Fdo:, Firmado, El Sr., La Sra.
                prefixes = [
                    r'D\.', r'Don', r'Doña', r'Dña\.', 
                    r'Sr\.', r'Sra\.', r'Dr\.', r'Dra\.',
                    r'Fdo\.', r'Fdo:', r'Firmado', r'Firmado:', r'Firma',
                    r'El\s+Sr\.', r'La\s+Sra\.', r'El\s+Dr\.', r'La\s+Dra\.'
                ]
                prefix_pattern = '|'.join(prefixes)
                
                # Regex Explicación:
                # Grupo 1 (Tratamiento): Uno de los prefijos definidos + espacios opcionales
                # Grupo 2 (Nombre):
                #   - Empieza con Mayúscula/Letra
                #   - Permite palabras conectadas por espacios
                #   - Permite conectores (de, del, la...)
                #   - Longitud 1-6 palabras
                formal_name_pattern = re.compile(
                    r'\b((?:' + prefix_pattern + r')\s*)' + 
                    r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+(?:\s+(?:de|del|la|los|las|y|[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+)){1,6})',
                    re.UNICODE | re.IGNORECASE
                )

                for match in formal_name_pattern.finditer(text):
                    # Redactar solo el nombre (Grupo 2)
                    name_text = match.group(2)
                    
                    # Validaciones extra para el nombre capturado
                    # Si contiene números o caracteres extraños, ignorar
                    if re.search(r'\d', name_text): 
                        continue
                        
                    # Calcular bbox precisa solo para el nombre
                    precise_bbox = block.bbox
                    if doc_pdf:
                        try:
                            page = doc_pdf[block.page_num]
                            # Buscar el nombre exacto en la página
                            text_instances = page.search_for(name_text)

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
                            logger.warning(f"Error calculando bbox precisa para Nombre Formal: {e}")

                    matches.append(
                        PIIMatch(
                            type="PERSON",
                            text=name_text,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=0.95,  # Alta confianza por el tratamiento explícito
                            source="regex_formal",
                        )
                    )

        # Cerrar el PDF si lo abrimos
        if doc_pdf:
            doc_pdf.close()

        return matches

    def _detect_with_ner(self, text_blocks: List[TextBlock]) -> List[PIIMatch]:
        """
        Detecta PII usando NER de spaCy.
        
        NOTA: A petición del usuario, se ha DESACTIVADO la detección genérica de nombres de personas.
        Solo se detectan nombres si van precedidos de un tratamiento formal (D., Fdo., etc.)
        mediante regex.
        
        Se mantiene el método por si se requiere reactivar o para otros tipos de entidades en el futuro.
        """
        if not self.nlp:
            logger.warning("_detect_with_ner llamado pero self.nlp es None")
            return []

        matches = []
        # LOGICA NER DESACTIVADA PARA PERSONAS
        # Para reactivar, restaurar el bucle sobre doc.ents verificando ent.label_ == "PER"
        
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
            r'C/\s*',
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

        # Términos que indican nombres de organismos/entidades, no direcciones personales
        # Ejemplos: "Dirección General de Recursos Humanos", "Servicio Canario de la Salud"
        organizational_indicators = [
            'dirección general',
            'ministerio',
            'consejería',
            'secretaría general',
            'departamento',
            'servicio canario',
            'servicio de',
            'recursos humanos',
            'área de',
            'subdirección',
            'viceconsejería',
            'delegación',
            'gerencia',
            'jefatura',
            'inspección',
            'tribunal',
            'juzgado',
            'administración',
        ]

        for block in text_blocks:
            text = block.text

            for match in address_pattern.finditer(text):
                # Capturar toda la dirección excepto la palabra clave inicial si es "Domicilio:" o "Dirección:"
                matched_text = match.group(0)
                keyword = match.group(1)

                # Filtrar organismos/entidades: "Dirección General de...", "Servicio de...", etc.
                # Buscar en un contexto amplio para capturar el nombre completo de la organización
                match_start = match.start()
                match_end = match.end()
                context_before = text[max(0, match_start-50):match_start].lower()
                context_after = text[match_end:match_end+100].lower()
                full_context = (context_before + matched_text + context_after).lower()

                # Si contiene indicadores organizativos, NO es una dirección personal
                is_organization = any(indicator in full_context for indicator in organizational_indicators)
                if is_organization:
                    logger.debug(f"Filtrado nombre organizativo, no dirección personal: '{matched_text}' (contexto: '{full_context[:80]}...')")
                    continue

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

    def _detect_addresses_in_fullpage(self) -> List[PIIMatch]:
        """
        Detecta direcciones procesando el texto completo de cada página.
        Esto permite capturar direcciones que están divididas entre múltiples bloques de texto.

        Returns:
            Lista de matches de direcciones encontradas
        """
        if not self.settings.detect_addresses or not self.pdf_path:
            return []

        import fitz

        matches = []

        # Revertir el cambio del keyword domiciliad - solo usar keywords simples
        address_keywords = [
            r'C/\s*',
            r'Calle\s+',
            r'Av\.',
            r'Avda\.',
            r'Avenida\s+',
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

        address_pattern = re.compile(
            r'(' + '|'.join(address_keywords) + r')' +
            r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+(?:de|del|la|los|las|el|y)\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,3})' +
            r'(?:\s*[,]?\s*(?:nº|n°|núm\.?|número)?\s*(\d{1,4}(?:\s*[A-Za-z])?))?' +
            r'(?:\s*[,]?\s*(\d{5}))?' +
            r'(?=[,\.\;\:]|\s*$|(?:\s+[A-Z]))',
            re.IGNORECASE
        )

        # Términos organizativos (reutilizar de _detect_addresses)
        organizational_indicators = [
            'dirección general', 'ministerio', 'consejería', 'secretaría general',
            'departamento', 'servicio canario', 'servicio de', 'recursos humanos',
            'área de', 'subdirección', 'viceconsejería', 'delegación',
            'gerencia', 'jefatura', 'inspección', 'tribunal', 'juzgado', 'administración',
        ]

        # Indicadores de títulos/secciones (NO son direcciones)
        title_indicators = [
            'la vía del',  # "La Vía del Cobro" es un título, no una dirección
            'vía del cobro',
            'doctrina',
            'enriquecimiento',
        ]

        try:
            doc = fitz.open(self.pdf_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()

                for match in address_pattern.finditer(text):
                    matched_text = match.group(0).strip()

                    # Aplicar filtro organizativo
                    match_start = match.start()
                    match_end = match.end()
                    context_before = text[max(0, match_start-50):match_start].lower()
                    context_after = text[match_end:match_end+100].lower()
                    full_context = (context_before + matched_text + context_after).lower()

                    is_organization = any(indicator in full_context for indicator in organizational_indicators)
                    if is_organization:
                        logger.debug(f"Filtrado nombre organizativo en fullpage: '{matched_text}'")
                        continue

                    # Filtrar títulos de secciones
                    is_title = any(indicator in full_context for indicator in title_indicators)
                    if is_title:
                        logger.debug(f"Filtrado título/sección en fullpage: '{matched_text}' (contexto: '{full_context[:80]}')")
                        continue

                    # Filtrar "Vía del/de" sin número (títulos conceptuales, no direcciones)
                    # Las direcciones reales siempre tienen número. Ej: "Vía Real 123"
                    # Pero "Vía del Cobro" es un título, no una dirección
                    if matched_text.lower().strip() in ['vía del', 'vía de', 'vía de la', 'vía de los']:
                        logger.debug(f"Filtrado 'Vía' sin número de calle (título conceptual): '{matched_text}'")
                        continue

                    # Buscar bbox precisa usando search_for
                    # Buscar solo la parte de la dirección (sin keyword si es Domicilio:/Dirección:)
                    search_text = matched_text
                    rects = page.search_for(search_text)

                    if rects:
                        # Usar el primer rect encontrado
                        rect = rects[0]
                        matches.append(
                            PIIMatch(
                                type="ADDRESS",
                                text=matched_text,
                                bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                                page_num=page_num,
                                confidence=0.85,
                                source="fullpage_address_detector",
                            )
                        )
                        logger.debug(f"Dirección detectada en página completa {page_num}: '{matched_text}'")
                    else:
                        logger.debug(f"No se encontró bbox para dirección: '{matched_text}'")

            doc.close()

        except Exception as e:
            logger.error(f"Error en detección de direcciones en página completa: {e}")

        return matches

    def _detect_dni_nie_in_fullpage(self) -> List[PIIMatch]:
        """
        Detecta DNI/NIE procesando el texto completo de cada página.
        Esto permite capturar DNI/NIE que están divididos entre múltiples bloques de texto
        (ej: "DNI núm." en un bloque y "13920075S" en otro).

        Returns:
            Lista de matches de DNI/NIE encontrados
        """
        if not self.pdf_path:
            return []

        if not self.settings.detect_dni and not self.settings.detect_nie:
            return []

        import fitz

        matches = []

        # Patrones de detección
        dni_pattern = re.compile(
            r'((?:DNI|NIF)(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)(\d{8}[A-Za-z])\b',
            re.IGNORECASE
        )
        nie_pattern = re.compile(
            r'(NIE(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)([XYZxyz]\d{7}[A-Za-z])\b',
            re.IGNORECASE
        )

        try:
            doc = fitz.open(self.pdf_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()

                # Buscar DNI
                if self.settings.detect_dni:
                    for match in dni_pattern.finditer(text):
                        dni_number = match.group(2)  # Solo el número, sin el prefijo "DNI núm."

                        # Buscar bbox precisa usando search_for (buscar solo el número)
                        text_instances = page.search_for(dni_number)

                        if text_instances:
                            # Usar la primera instancia encontrada
                            rect = text_instances[0]
                            bbox = (rect.x0, rect.y0, rect.x1, rect.y1)

                            matches.append(
                                PIIMatch(
                                    type="DNI",
                                    text=dni_number,
                                    bbox=bbox,
                                    page_num=page_num,
                                    confidence=1.0,
                                    source="regex_fullpage",
                                )
                            )
                            logger.debug(f"DNI detectado en página completa {page_num}: '{dni_number}'")
                        else:
                            logger.debug(f"No se encontró bbox para DNI: '{dni_number}'")

                # Buscar NIE
                if self.settings.detect_nie:
                    for match in nie_pattern.finditer(text):
                        nie_number = match.group(2)  # Solo el número, sin el prefijo "NIE núm."

                        # Buscar bbox precisa usando search_for (buscar solo el número)
                        text_instances = page.search_for(nie_number)

                        if text_instances:
                            # Usar la primera instancia encontrada
                            rect = text_instances[0]
                            bbox = (rect.x0, rect.y0, rect.x1, rect.y1)

                            matches.append(
                                PIIMatch(
                                    type="NIE",
                                    text=nie_number,
                                    bbox=bbox,
                                    page_num=page_num,
                                    confidence=1.0,
                                    source="regex_fullpage",
                                )
                            )
                            logger.debug(f"NIE detectado en página completa {page_num}: '{nie_number}'")
                        else:
                            logger.debug(f"No se encontró bbox para NIE: '{nie_number}'")

            doc.close()

        except Exception as e:
            logger.error(f"Error en detección de DNI/NIE en página completa: {e}")

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

    def _detect_name_parts(self, existing_matches: List[PIIMatch], text_blocks: List) -> List[PIIMatch]:
        """
        Detecta partes individuales (apellidos/nombres) de los nombres ya detectados.
        Busca cada palabra de los nombres completos en todo el documento usando search_for() para bboxes precisas.

        Args:
            existing_matches: Matches ya detectados (para extraer nombres)
            text_blocks: Bloques de texto donde buscar (no usado, se usa PDF directo)

        Returns:
            Lista de nuevos matches para partes de nombres
        """
        import re
        import fitz

        new_matches = []

        # 1. Extraer todos los nombres detectados hasta ahora
        name_types = ['PERSON', 'NOMBRES_CON_PREFIJO', 'NOMBRES_CON_FIRMA']
        detected_names = set()

        for match in existing_matches:
            if match.type in name_types:
                # Limpiar y normalizar el nombre
                clean_name = match.text.strip()
                detected_names.add(clean_name)

        if not detected_names:
            return new_matches

        logger.debug(f"Buscando partes de {len(detected_names)} nombres detectados")

        # 2. Extraer palabras individuales (apellidos/nombres) de cada nombre completo
        name_parts = set()
        for full_name in detected_names:
            # Dividir por espacios y filtrar palabras cortas o conectores
            words = full_name.split()
            for word in words:
                # Limpiar puntuación
                clean_word = re.sub(r'[^\wáéíóúüñÁÉÍÓÚÜÑ]', '', word)
                # Solo añadir palabras de 4+ caracteres (evitar "de", "la", "del", etc.)
                if len(clean_word) >= 4:
                    name_parts.add(clean_word)

        if not name_parts:
            return new_matches

        logger.debug(f"Buscando {len(name_parts)} partes individuales: {name_parts}")

        # 3. Si tenemos pdf_path, usar search_for() para bboxes precisas
        if not self.pdf_path:
            logger.debug("No hay pdf_path, saltando detección de partes de nombres")
            return new_matches

        try:
            doc = fitz.open(self.pdf_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]

                for name_part in name_parts:
                    # Buscar en mayúsculas, minúsculas y capitalizado
                    search_variants = [
                        name_part.upper(),
                        name_part.lower(),
                        name_part.capitalize()
                    ]

                    for variant in search_variants:
                        # Buscar el texto en la página
                        rects = page.search_for(variant)

                        for rect in rects:
                            # Crear PIIMatch con bbox precisa
                            new_match = PIIMatch(
                                type='NAME_PART',
                                text=variant,
                                page_num=page_num,
                                bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                                confidence=0.7,
                                source='name_parts'
                            )

                            new_matches.append(new_match)
                            logger.debug(f"Encontrada parte de nombre: '{variant}' en página {page_num}")

            doc.close()

        except Exception as e:
            logger.error(f"Error buscando partes de nombres en PDF: {e}")
            return []

        return new_matches
