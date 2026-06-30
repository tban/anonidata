"""
Detector basado en reglas configurables
Permite definir patrones de anonimización con control fino sobre qué partes redactar
"""

import re
import json
import sys
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
from utils.geometry import rect_inside_bbox, find_precise_bbox


def get_resource_path(relative_path: str) -> Path:
    """
    Obtiene la ruta correcta para archivos de recursos,
    tanto en desarrollo como cuando está empaquetado con PyInstaller
    """
    try:
        # PyInstaller crea un directorio temporal y almacena la ruta en _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Si no estamos en PyInstaller, usar la ruta normal
        base_path = Path(__file__).parent.parent

    return base_path / relative_path


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
            rules_path = get_resource_path("config/anonymization_rules.json")

        self.rules_path = rules_path
        self.rules: List[AnonymizationRule] = []
        self.settings: Dict[str, Any] = {}
        self._load_rules()

    def _load_rules(self):
        """Carga las reglas desde el archivo JSON"""
        try:
            logger.info(f"Intentando cargar reglas desde: {self.rules_path}")
            logger.info(f"Archivo existe: {self.rules_path.exists()}")

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
                    logger.debug(f"  - Regla cargada: {rule.id} ({rule.name})")

            logger.info(f"✓ Cargadas {len(self.rules)} reglas de anonimización")
            for rule in self.rules:
                logger.info(f"  - {rule.id}: {rule.name} (enabled={rule.enabled})")

        except Exception as e:
            logger.error(f"Error cargando reglas de {self.rules_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def detect_in_text_blocks(self, text_blocks: List[TextBlock], doc) -> List[PIIMatch]:
        """
        Detecta PII en bloques de texto usando las reglas configuradas

        Args:
            text_blocks: Lista de bloques de texto
            doc: Documento PDF abierto (para calcular coordenadas precisas)

        Returns:
            Lista de PIIMatch con coordenadas precisas
        """
        matches = []

        for block in text_blocks:
            for rule in self.rules:
                rule_matches = self._find_matches_in_block(
                    block, rule, doc
                )
                matches.extend(rule_matches)

        logger.debug(f"Detector basado en reglas encontró {len(matches)} coincidencias")
        return matches

    def _find_matches_in_block(
        self,
        block: TextBlock,
        rule: AnonymizationRule,
        doc
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
                if regex_match.lastindex is not None and group_idx <= regex_match.lastindex:
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
        doc,
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
        target_text = full_text[start_pos:end_pos]
        return find_precise_bbox(doc, page_num, target_text, block_bbox)


