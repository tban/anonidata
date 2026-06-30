"""
Detector de Información Personal Identificable (PII)
Combina regex, NLP y detección visual
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from loguru import logger

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF no instalado")
    raise

from core.config import Settings
from processors.pdf_parser import PDFData, TextBlock
from processors.ocr_engine import OCRData, OCRResult
from detectors.regex_patterns import RegexPatterns
from detectors.visual_detector import VisualDetector
from detectors.models import PIIMatch
from detectors.rule_based_detector import RuleBasedDetector
from utils.geometry import rect_inside_bbox, find_precise_bbox


# Letras de validación del DNI/NIE español
_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX_MAP = {'X': '0', 'Y': '1', 'Z': '2'}

# --- Patrones regex precompilados (compilados una vez, no por cada bloque) ---

# DNI/NIF con etiqueta: "DNI: 12345678X", "NIF 12.345.678X", "DNI núm. 12345678-X"
_DNI_LABELED_RE = re.compile(
    r'((?:DNI|NIF)(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)'
    r'((?:\d{1,2}\.\d{3}\.\d{3}|\d{8})-?[A-Za-z])\b',
    re.IGNORECASE
)

# NIE con etiqueta: "NIE: X1234567A", "NIE X1.234.567-A"
_NIE_LABELED_RE = re.compile(
    r'(NIE(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)'
    r'([XYZxyz](?:\d{1}\.\d{3}\.\d{3}|\d{7})-?[A-Za-z])\b',
    re.IGNORECASE
)

# CIF con etiqueta: "CIF: B12345678", "CIF B-12345678"
_CIF_LABELED_RE = re.compile(
    r'((?:CIF|NIF|C\.I\.F\.|N\.I\.F\.)(?:\s*:)?\s*(?:n[úu]m\.?|n\.?[oº]\.?)?\s*)'
    r'([A-Za-z]-?(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-?[0-9A-Za-z])\b',
    re.IGNORECASE
)

# NSS con etiqueta: "Nº SS: 281234567890", "Seguridad Social: 28 1234567890"
_NSS_LABELED_RE = re.compile(
    r'(?:N[ºo°]\.?\s*(?:de\s+)?(?:la\s+)?S\.?S\.?|'
    r'Seguridad\s+Social|'
    r'(?:Nº|N[oº°])\s*(?:Afiliación|afiliación))'
    r'(?:\s*:)?\s*'
    r'(\d{2}[\s/-]?\d{8}[\s/-]?\d{2})\b',
    re.IGNORECASE
)

# Nombres con tratamiento formal: D., Don, Fdo., etc.
_FORMAL_PREFIXES = [
    r'D\.', r'Don', r'Doña', r'Dña\.',
    r'Sr\.', r'Sra\.', r'Dr\.', r'Dra\.',
    r'Fdo\.', r'Fdo:', r'Firmado', r'Firmado:', r'Firma',
    r'El\s+Sr\.', r'La\s+Sra\.', r'El\s+Dr\.', r'La\s+Dra\.'
]
_FORMAL_NAME_RE = re.compile(
    r'\b((?:' + '|'.join(_FORMAL_PREFIXES) + r')\s*)'
    r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+(?:\s+(?:de|del|la|los|las|y|[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+)){1,6})',
    re.UNICODE
)

# Palabras clave de direcciones
_ADDRESS_KEYWORDS = [
    r'Domicilio:?\s*',
    r'Dirección:?\s*',
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
    r'Partida\s+',
    r'Polígono\s+',
    r'Barrio\s+',
    r'Edificio\s+',
    r'Bloque\s+',
]

_ADDRESS_RE = re.compile(
    r'(' + '|'.join(_ADDRESS_KEYWORDS) + r')'
    r'([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+(?:de|del|la|los|las|el|y)\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){0,3})'
    r'(?:\s*[,]?\s*(?:nº|n°|núm\.?|número)?\s*(\d{1,4}(?:\s*[A-Za-z])?))?'
    r'(?:\s*[,]?\s*(\d{5}))?'
    r'(?=[,\.\;\:]|\s*$|(?:\s+[A-Z]))',
    re.IGNORECASE
)

# Indicadores organizativos (NO son direcciones personales)
_ORGANIZATIONAL_INDICATORS = [
    'dirección general', 'ministerio', 'consejería', 'secretaría general',
    'departamento', 'servicio canario', 'servicio de', 'recursos humanos',
    'área de', 'subdirección', 'viceconsejería', 'delegación',
    'gerencia', 'jefatura', 'inspección', 'tribunal', 'juzgado', 'administración',
]

# Indicadores de puesto de trabajo (NO son direcciones)
_JOB_POSITION_INDICATORS = [
    'técnico', 'interino', 'funcionario', 'empleado', 'vacante',
    'ofertada', 'personal', 'categoría', 'especialidad', 'servicio',
    'atención primaria', 'adjudicada', 'ocupo', 'desempeño', 'puesto'
]

# Indicadores de títulos/secciones (NO son direcciones)
_TITLE_INDICATORS = [
    'la vía del', 'vía del cobro', 'doctrina', 'enriquecimiento',
]


def _validate_dni_letter(dni_str: str) -> bool:
    """Valida la letra de control de un DNI/NIF español."""
    normalized = dni_str.replace('.', '').replace('-', '')
    if len(normalized) != 9:
        return False
    try:
        number = int(normalized[:8])
        letter = normalized[8].upper()
        return letter == _DNI_LETTERS[number % 23]
    except (ValueError, IndexError):
        return False


def _validate_nie_letter(nie_str: str) -> bool:
    """Valida la letra de control de un NIE español."""
    normalized = nie_str.replace('.', '').replace('-', '')
    if len(normalized) != 9:
        return False
    first_char = normalized[0].upper()
    if first_char not in _NIE_PREFIX_MAP:
        return False
    try:
        number_str = _NIE_PREFIX_MAP[first_char] + normalized[1:8]
        number = int(number_str)
        letter = normalized[8].upper()
        return letter == _DNI_LETTERS[number % 23]
    except (ValueError, IndexError):
        return False


def _validate_cif(cif_str: str) -> bool:
    """Valida la estructura básica de un CIF español."""
    normalized = cif_str.replace('.', '').replace('-', '').upper()
    if len(normalized) != 9:
        return False
    if normalized[0] not in "ABCDEFGHJNPQRSUVW":
        return False
    if not normalized[1:8].isdigit():
        return False
    return True


class PIIDetector:
    """Detector principal de PII"""

    def __init__(self, settings: Settings, pdf_path: Optional[Any] = None):
        self.settings = settings
        self.regex_patterns = RegexPatterns()
        self.visual_detector = VisualDetector(settings)
        self.rule_based_detector = RuleBasedDetector()
        self.pdf_path = pdf_path

        # NER desactivado: no cargar modelo spaCy para ahorrar memoria y tiempo de inicio
        self.nlp = None

    def set_pdf_path(self, pdf_path: Any):
        """Establece la ruta del PDF para el detector basado en reglas"""
        self.pdf_path = pdf_path

    def detect(self, pdf_data: PDFData, ocr_data: OCRData, progress_callback=None) -> List[PIIMatch]:
        """
        Detecta PII en el documento

        Args:
            pdf_data: Datos del PDF
            ocr_data: Datos del OCR
            progress_callback: Callback opcional para reportar progreso

        Returns:
            Lista de matches de PII
        """
        matches = []

        # Convertir OCR a TextBlocks una sola vez (optimización: antes se hacía 2 veces)
        ocr_text_blocks = self._convert_ocr_to_text_blocks(ocr_data.results)

        # Abrir PDF una sola vez para toda la detección (optimización: antes se abría 5 veces)
        doc = None
        if self.pdf_path:
            try:
                doc = fitz.open(self.pdf_path)
            except Exception as e:
                logger.error(f"Error abriendo PDF para detección: {e}")

        try:
            # 1. Detección basada en reglas configurables (con bboxes precisas)
            if progress_callback:
                progress_callback(0, "Detectando PII (Reglas)...")
            if doc:
                logger.debug("Detectando PII con reglas configurables...")
                rule_matches = self.rule_based_detector.detect_in_text_blocks(
                    pdf_data.text_blocks, doc
                )
                matches.extend(rule_matches)

                # También en bloques OCR
                rule_ocr_matches = self.rule_based_detector.detect_in_text_blocks(
                    ocr_text_blocks, doc
                )
                matches.extend(rule_ocr_matches)

            # 2. Detección con regex tradicional (DNI, NIE, teléfonos, emails, etc.)
            if progress_callback:
                progress_callback(20, "Detectando PII (Patrones)...")
            logger.debug("Detectando PII con regex...")
            regex_matches = self._detect_with_regex(pdf_data.text_blocks, doc)
            matches.extend(regex_matches)

            # También en OCR
            regex_ocr_matches = self._detect_with_regex(ocr_text_blocks, doc)
            matches.extend(regex_ocr_matches)

            # También detectar DNI/NIE en texto completo de página para capturar casos fragmentados
            if doc:
                logger.debug("Detectando DNI/NIE en texto completo de páginas...")
                fullpage_dni_matches = self._detect_dni_nie_in_fullpage(doc)
                matches.extend(fullpage_dni_matches)

            # 3. Detección de direcciones con palabras clave
            if progress_callback:
                progress_callback(50, "Detectando PII (Direcciones)...")
            logger.debug("Detectando direcciones...")
            address_matches = self._detect_addresses(pdf_data.text_blocks)
            matches.extend(address_matches)

            # También detectar en texto completo de página para capturar direcciones que cruzan bloques
            if doc:
                logger.debug("Detectando direcciones en texto completo de páginas...")
                fullpage_address_matches = self._detect_addresses_in_fullpage(doc)
                matches.extend(fullpage_address_matches)

            # También en OCR
            address_ocr_matches = self._detect_addresses(ocr_text_blocks)
            matches.extend(address_ocr_matches)

            # 4. Detección visual (firmas, QR codes)
            if progress_callback:
                progress_callback(70, "Detectando PII (Firmas y QR)...")
            logger.debug("Detectando PII visual...")
            visual_matches = self.visual_detector.detect(pdf_data)
            matches.extend(visual_matches)

            # 5. Detección de partes individuales de nombres (apellidos/nombres sueltos)
            # OPTIMIZACIÓN: Deshabilitar para PDFs grandes (>50 páginas) por rendimiento
            if pdf_data.page_count <= 50:
                if progress_callback:
                    progress_callback(85, "Detección (Refinando nombres)...")
                logger.debug("Detectando partes individuales de nombres...")
                name_part_matches = self._detect_name_parts(matches, doc)
                logger.debug(f"Detección de partes encontró {len(name_part_matches)} ocurrencias adicionales")
                matches.extend(name_part_matches)
            else:
                logger.info(f"PDF grande ({pdf_data.page_count} páginas), saltando detección de partes de nombres para mejor rendimiento")

        finally:
            if doc:
                doc.close()

        # Eliminar duplicados (solapamiento)
        matches = self._remove_duplicates(matches)

        if progress_callback:
            progress_callback(100, "Detección completada")

        logger.info(f"Detectados {len(matches)} elementos PII")

        return matches

    def _convert_ocr_to_text_blocks(self, ocr_results: List[OCRResult]) -> List[TextBlock]:
        """Convierte resultados OCR a TextBlocks"""
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

    def _detect_with_regex(self, text_blocks: List[TextBlock], doc=None) -> List[PIIMatch]:
        """Detecta PII usando patrones regex precompilados (preserva etiquetas DNI/NIE)"""
        matches = []

        for block in text_blocks:
            text = block.text

            # DNI/NIF con etiqueta - preservar etiqueta, redactar solo número
            if self.settings.detect_dni:
                for match in _DNI_LABELED_RE.finditer(text):
                    dni_number = match.group(2)
                    # Validar letra de control (evita falsos positivos)
                    if not _validate_dni_letter(dni_number):
                        logger.debug(f"DNI descartado por letra de control inválida: {dni_number}")
                        continue

                    precise_bbox = find_precise_bbox(doc, block.page_num, dni_number, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="DNI",
                            text=dni_number,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

                # CIF con etiqueta - preservar etiqueta, redactar solo número (usando flag detect_dni)
                for match in _CIF_LABELED_RE.finditer(text):
                    cif_number = match.group(2)
                    if not _validate_cif(cif_number):
                        continue

                    precise_bbox = find_precise_bbox(doc, block.page_num, cif_number, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="CIF",
                            text=cif_number,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # NIE con etiqueta - preservar etiqueta, redactar solo número
            if self.settings.detect_nie:
                for match in _NIE_LABELED_RE.finditer(text):
                    nie_number = match.group(2)
                    # Validar letra de control
                    if not _validate_nie_letter(nie_number):
                        logger.debug(f"NIE descartado por letra de control inválida: {nie_number}")
                        continue

                    precise_bbox = find_precise_bbox(doc, block.page_num, nie_number, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="NIE",
                            text=nie_number,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # Email
            if self.settings.detect_emails:
                for match in self.regex_patterns.find_email(text):
                    precise_bbox = find_precise_bbox(doc, block.page_num, match, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="EMAIL",
                            text=match,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # Teléfono
            if self.settings.detect_phones:
                for match in self.regex_patterns.find_phone(text):
                    precise_bbox = find_precise_bbox(doc, block.page_num, match, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="PHONE",
                            text=match,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # IBAN
            if self.settings.detect_iban:
                for match in self.regex_patterns.find_iban(text):
                    precise_bbox = find_precise_bbox(doc, block.page_num, match, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="IBAN",
                            text=match,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source="regex",
                        )
                    )

            # NSS (Número de Seguridad Social) - solo con contexto para evitar falsos positivos
            if getattr(self.settings, 'detect_nss', False):
                for match in _NSS_LABELED_RE.finditer(text):
                    nss_number = match.group(1)
                    precise_bbox = find_precise_bbox(doc, block.page_num, nss_number, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="NSS",
                            text=nss_number,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=0.95,
                            source="regex",
                        )
                    )

            # Nombres con tratamiento formal (D./Doña/Fdo.) - patrón precompilado, sin IGNORECASE
            if self.settings.detect_names:
                for match in _FORMAL_NAME_RE.finditer(text):
                    name_text = match.group(2)
                    # Si contiene números, ignorar
                    if re.search(r'\d', name_text):
                        continue

                    precise_bbox = find_precise_bbox(doc, block.page_num, name_text, block.bbox) if doc else block.bbox
                    matches.append(
                        PIIMatch(
                            type="PERSON",
                            text=name_text,
                            bbox=precise_bbox or block.bbox,
                            page_num=block.page_num,
                            confidence=0.95,
                            source="regex_formal",
                        )
                    )

        return matches



    def _detect_addresses(self, text_blocks: List[TextBlock]) -> List[PIIMatch]:
        """
        Detecta direcciones usando palabras clave españolas.
        Usa el patrón precompilado _ADDRESS_RE y las constantes compartidas.
        """
        if not self.settings.detect_addresses:
            return []

        matches = []

        for block in text_blocks:
            text = block.text

            for match in _ADDRESS_RE.finditer(text):
                matched_text = match.group(0)
                keyword = match.group(1)

                # Filtrar organismos/entidades
                match_start = match.start()
                match_end = match.end()
                context_before = text[max(0, match_start-50):match_start].lower()
                context_after = text[match_end:match_end+100].lower()
                full_context = (context_before + matched_text + context_after).lower()

                if any(indicator in full_context for indicator in _ORGANIZATIONAL_INDICATORS):
                    logger.debug(f"Filtrado nombre organizativo, no dirección personal: '{matched_text}'")
                    continue

                # Filtrar puestos de trabajo ("plaza de técnico", etc.)
                if keyword.strip().lower().startswith('plaza'):
                    context = text[match_end:match_end+100].lower()
                    if any(ind in matched_text.lower() or ind in context for ind in _JOB_POSITION_INDICATORS):
                        logger.debug(f"Filtrado 'plaza' como puesto de trabajo: '{matched_text}'")
                        continue

                # Si es "Domicilio:" o "Dirección:", solo redactar la dirección, no la etiqueta
                if keyword.strip().lower().startswith(('domicilio', 'dirección')):
                    address_parts = []
                    if match.group(2):
                        address_parts.append(match.group(2).strip())
                    if match.group(3):
                        address_parts.append(match.group(3).strip())
                    if match.group(4):
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

    def _detect_addresses_in_fullpage(self, doc) -> List[PIIMatch]:
        """
        Detecta direcciones procesando el texto completo de cada página.
        Usa el documento PDF ya abierto y las constantes compartidas.

        Args:
            doc: Documento PyMuPDF ya abierto

        Returns:
            Lista de matches de direcciones encontradas
        """
        if not self.settings.detect_addresses or not doc:
            return []

        matches = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()

            for match in _ADDRESS_RE.finditer(text):
                matched_text = match.group(0).strip()

                # Filtrar con constantes compartidas
                match_start = match.start()
                match_end = match.end()
                context_before = text[max(0, match_start-50):match_start].lower()
                context_after = text[match_end:match_end+100].lower()
                full_context = (context_before + matched_text + context_after).lower()

                if any(indicator in full_context for indicator in _ORGANIZATIONAL_INDICATORS):
                    logger.debug(f"Filtrado nombre organizativo en fullpage: '{matched_text}'")
                    continue

                if any(indicator in full_context for indicator in _TITLE_INDICATORS):
                    logger.debug(f"Filtrado título/sección en fullpage: '{matched_text}'")
                    continue

                # Filtrar "Vía del/de" sin número (títulos conceptuales)
                if matched_text.lower().strip() in ['vía del', 'vía de', 'vía de la', 'vía de los']:
                    logger.debug(f"Filtrado 'Vía' sin número (título conceptual): '{matched_text}'")
                    continue

                rects = page.search_for(matched_text)
                if rects:
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

        return matches

    def _detect_dni_nie_in_fullpage(self, doc) -> List[PIIMatch]:
        """
        Detecta DNI/NIE procesando el texto completo de cada página.
        Usa patrones precompilados con validación de letra de control.

        Args:
            doc: Documento PyMuPDF ya abierto

        Returns:
            Lista de matches de DNI/NIE encontrados
        """
        if not doc:
            return []

        if not self.settings.detect_dni and not self.settings.detect_nie:
            return []

        matches = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()

            # Buscar DNI con validación
            if self.settings.detect_dni:
                for match in _DNI_LABELED_RE.finditer(text):
                    dni_number = match.group(2)

                    # Validar letra de control
                    if not _validate_dni_letter(dni_number):
                        logger.debug(f"DNI fullpage descartado por letra inválida: {dni_number}")
                        continue

                    bbox = find_precise_bbox(doc, page_num, dni_number)
                    if bbox:
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

                # Buscar CIF con validación
                for match in _CIF_LABELED_RE.finditer(text):
                    cif_number = match.group(2)

                    if not _validate_cif(cif_number):
                        continue

                    bbox = find_precise_bbox(doc, page_num, cif_number)
                    if bbox:
                        matches.append(
                            PIIMatch(
                                type="CIF",
                                text=cif_number,
                                bbox=bbox,
                                page_num=page_num,
                                confidence=1.0,
                                source="regex_fullpage",
                            )
                        )
                        logger.debug(f"CIF detectado en página completa {page_num}: '{cif_number}'")

            # Buscar NIE con validación
            if self.settings.detect_nie:
                for match in _NIE_LABELED_RE.finditer(text):
                    nie_number = match.group(2)

                    # Validar letra de control
                    if not _validate_nie_letter(nie_number):
                        logger.debug(f"NIE fullpage descartado por letra inválida: {nie_number}")
                        continue

                    bbox = find_precise_bbox(doc, page_num, nie_number)
                    if bbox:
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

        return matches

    def _remove_duplicates(self, matches: List[PIIMatch]) -> List[PIIMatch]:
        """
        Elimina matches duplicados que se solapan.
        Optimizado: agrupa por (page_num, texto normalizado) antes de comparar,
        reduciendo la complejidad de O(n²) a O(n log n) en la práctica.
        """
        if not matches:
            return []

        # Ordenar por confianza (mayor primero)
        sorted_matches = sorted(matches, key=lambda m: m.confidence, reverse=True)

        # Agrupar por (page_num, texto normalizado) para comparar solo dentro del grupo
        groups = defaultdict(list)
        for match in sorted_matches:
            key = (match.page_num, match.text.lower().strip())
            groups[key].append(match)

        filtered = []
        for key, group in groups.items():
            for match in group:
                # Solo comparar solapamiento dentro del mismo grupo (mismo texto, misma página)
                overlaps = False
                for existing in filtered:
                    if existing.page_num == match.page_num and existing.text.lower().strip() == match.text.lower().strip():
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

        try:
            x0_1, y0_1, x1_1, y1_1 = match1.bbox
            x0_2, y0_2, x1_2, y1_2 = match2.bbox

            # Validar que no haya None
            if None in (x0_1, y0_1, x1_1, y1_1, x0_2, y0_2, x1_2, y1_2):
                return False

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

        except (TypeError, ValueError):
            return False

    def _detect_name_parts(self, existing_matches: List[PIIMatch], doc=None) -> List[PIIMatch]:
        """
        Detecta partes individuales (apellidos/nombres) de los nombres ya detectados.
        Busca cada palabra una sola vez (search_for ya es case-insensitive) con filtrado contextual.

        Args:
            existing_matches: Matches ya detectados (para extraer nombres)
            doc: Documento PDF abierto (para búsquedas precisas)

        Returns:
            Lista de nuevos matches para partes de nombres
        """
        new_matches = []

        if not doc:
            return new_matches

        # 1. Extraer todos los nombres detectados hasta ahora
        name_types = ['PERSON', 'NOMBRES_CON_PREFIJO', 'NOMBRES_CON_FIRMA']
        detected_names = set()

        for match in existing_matches:
            if match.type in name_types:
                clean_name = match.text.strip()
                detected_names.add(clean_name)

        if not detected_names:
            return new_matches

        logger.debug(f"Buscando partes de {len(detected_names)} nombres detectados")

        # 2. Extraer palabras individuales (apellidos/nombres)
        name_parts = set()
        for full_name in detected_names:
            words = full_name.split()
            for word in words:
                clean_word = re.sub(r'[^\wáéíóúüñÁÉÍÓÚÜÑ]', '', word)
                # Solo añadir palabras de 4+ caracteres (evitar "de", "la", "del", etc.)
                if len(clean_word) >= 4:
                    name_parts.add(clean_word)

        if not name_parts:
            return new_matches

        logger.debug(f"Buscando {len(name_parts)} partes individuales: {name_parts}")

        # 3. Palabras que NO deben marcarse como nombre en ciertos contextos
        address_context_words = {'calle', 'c/', 'avenida', 'plaza', 'paseo', 'camino', 'carretera',
                                 'sentencia', 'recurso', 'expediente', 'referencia', 'asunto'}

        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_text = page.get_text().lower()

            for name_part in name_parts:
                # Buscar una sola vez (search_for es case-insensitive por defecto)
                rects = page.search_for(name_part)

                for rect in rects:
                    # Filtrado contextual: verificar que no aparezca en contexto de dirección u organizativo
                    # Buscar el texto alrededor de la posición encontrada
                    rect_center_y = (rect.y0 + rect.y1) / 2
                    # Obtener texto cercano para contexto (simplificado: usar la posición en page_text)
                    name_lower = name_part.lower()
                    pos = page_text.find(name_lower)
                    if pos >= 0:
                        context_start = max(0, pos - 30)
                        context_snippet = page_text[context_start:pos].strip()
                        # Si la palabra anterior es un indicador de dirección, saltar
                        if any(ctx_word in context_snippet for ctx_word in address_context_words):
                            logger.debug(f"Parte de nombre '{name_part}' filtrada por contexto de dirección")
                            continue

                    new_match = PIIMatch(
                        type='NAME_PART',
                        text=name_part,
                        page_num=page_num,
                        bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                        confidence=0.7,
                        source='name_parts'
                    )
                    new_matches.append(new_match)
                    logger.debug(f"Encontrada parte de nombre: '{name_part}' en página {page_num}")

        return new_matches

