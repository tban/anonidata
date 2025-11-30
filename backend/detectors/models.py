"""
Modelos compartidos para detectores
"""

from dataclasses import dataclass


@dataclass
class PIIMatch:
    """Match de PII detectado"""
    type: str  # DNI, NIE, PERSON, EMAIL, etc.
    text: str
    bbox: tuple[float, float, float, float]
    page_num: int
    confidence: float
    source: str  # 'regex', 'ner', 'visual'
