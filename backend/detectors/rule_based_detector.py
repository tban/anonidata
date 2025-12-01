"""
Detector basado en reglas configurables
Permite definir patrones de anonimización con control fino sobre qué partes redactar
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from loguru import logger

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF no instalado")
    raise

from processors.pdf_parser import TextBlock
from detectors.models import PIIMatch


@dataclass
class AnonymizationRule:
    """Regla de anonimización"""
    id: str
    name: str
    pattern: str
    redact_groups: List[int]
    preserve_groups: List[int]
    replacement: str
    enabled: bool
    case_sensitive: bool
    description: str

    def __post_init__(self):
        """Compila el patrón regex"""
        flags = 0 if self.case_sensitive else re.IGNORECASE
        self.compiled_pattern = re.compile(self.pattern, flags)


class RuleBasedDetector:
    """Detector basado en reglas configurables"""

    def __init__(self, rules_path: Optional[Path] = None):
        """
        Inicializa el detector

        Args:
            rules_path: Ruta al archivo JSON de reglas. Si es None, usa el default.
        """
        if rules_path is None:
            rules_path = Path(__file__).parent.parent / "config" / "anonymization_rules.json"

        self.rules_path = rules_path
        self.rules: List[AnonymizationRule] = []
        self.settings: Dict[str, Any] = {}
        self._load_rules()

    def _load_rules(self):
        """Carga las reglas desde el archivo JSON"""
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.settings = data.get('settings', {})

            for rule_data in data.get('rules', []):
                if rule_data.get('enabled', True):
                    rule = AnonymizationRule(
                        id=rule_data['id'],
                        name=rule_data['name'],
                        pattern=rule_data['pattern'],
                        redact_groups=rule_data['redact_groups'],
                        preserve_groups=rule_data.get('preserve_groups', []),
                        replacement=rule_data['replacement'],
                        enabled=rule_data['enabled'],
                        case_sensitive=rule_data.get('case_sensitive', False),
                        description=rule_data.get('description', ''),
                    )
                    self.rules.append(rule)

            logger.info(f"Cargadas {len(self.rules)} reglas de anonimización")

        except Exception as e:
            logger.error(f"Error cargando reglas de {self.rules_path}: {e}")
            raise

    def detect_in_text_blocks(self, text_blocks: List[TextBlock], pdf_path: Path) -> List[PIIMatch]:
        """
        Detecta PII en bloques de texto usando las reglas configuradas

        Args:
            text_blocks: Lista de bloques de texto
            pdf_path: Ruta al PDF (para abrir y calcular coordenadas precisas)

        Returns:
            Lista de PIIMatch con coordenadas precisas
        """
        matches = []

        # Abrir el PDF para poder buscar coordenadas precisas
        doc = fitz.open(pdf_path)

        try:
            for block in text_blocks:
                for rule in self.rules:
                    rule_matches = self._find_matches_in_block(
                        block, rule, doc
                    )
                    matches.extend(rule_matches)
        finally:
            doc.close()

        logger.debug(f"Detector basado en reglas encontró {len(matches)} coincidencias")
        return matches

    def _find_matches_in_block(
        self,
        block: TextBlock,
        rule: AnonymizationRule,
        doc: fitz.Document
    ) -> List[PIIMatch]:
        """
        Encuentra coincidencias de una regla en un bloque de texto

        Args:
            block: Bloque de texto
            rule: Regla a aplicar
            doc: Documento PDF abierto

        Returns:
            Lista de PIIMatch
        """
        matches = []
        text = block.text

        # Buscar todas las coincidencias del patrón
        for regex_match in rule.compiled_pattern.finditer(text):
            # Para cada grupo que debemos redactar
            for group_idx in rule.redact_groups:
                if group_idx <= regex_match.lastindex:
                    matched_text = regex_match.group(group_idx)
                    start_pos = regex_match.start(group_idx)
                    end_pos = regex_match.end(group_idx)

                    # Calcular bbox precisa para este fragmento de texto
                    precise_bbox = self._calculate_precise_bbox(
                        doc=doc,
                        page_num=block.page_num,
                        full_text=text,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        block_bbox=block.bbox
                    )

                    if precise_bbox:
                        pii_match = PIIMatch(
                            type=rule.id.upper(),
                            text=matched_text,
                            bbox=precise_bbox,
                            page_num=block.page_num,
                            confidence=1.0,
                            source=f"rule:{rule.id}",
                        )
                        matches.append(pii_match)

        return matches

    def _calculate_precise_bbox(
        self,
        doc: fitz.Document,
        page_num: int,
        full_text: str,
        start_pos: int,
        end_pos: int,
        block_bbox: Tuple[float, float, float, float]
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Calcula la bounding box precisa para un fragmento de texto

        Args:
            doc: Documento PDF
            page_num: Número de página
            full_text: Texto completo del bloque
            start_pos: Posición de inicio del fragmento
            end_pos: Posición de fin del fragmento
            block_bbox: Bbox del bloque completo (fallback)

        Returns:
            Tupla (x0, y0, x1, y1) o None si no se puede calcular
        """
        try:
            # Validar que block_bbox no tenga valores None
            if block_bbox and None in block_bbox:
                logger.warning(f"block_bbox contiene valores None: {block_bbox}")
                return None

            page = doc[page_num]
            target_text = full_text[start_pos:end_pos]

            # Buscar el texto en la página
            text_instances = page.search_for(target_text)

            if text_instances:
                # Si hay múltiples instancias, usar la que esté dentro del block_bbox
                for rect in text_instances:
                    if self._rect_inside_bbox(rect, block_bbox):
                        return (rect.x0, rect.y0, rect.x1, rect.y1)

                # Si ninguna está dentro, usar la primera
                rect = text_instances[0]
                return (rect.x0, rect.y0, rect.x1, rect.y1)

            # Fallback: usar bbox del bloque completo
            logger.debug(f"No se encontró bbox precisa para '{target_text}', usando bbox del bloque")
            return block_bbox

        except Exception as e:
            logger.warning(f"Error calculando bbox precisa: {e}")
            return block_bbox

    def _rect_inside_bbox(
        self,
        rect: fitz.Rect,
        bbox: Tuple[float, float, float, float]
    ) -> bool:
        """
        Verifica si un rectángulo está dentro de una bbox

        Args:
            rect: Rectángulo de PyMuPDF
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
