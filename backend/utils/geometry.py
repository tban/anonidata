"""
Utilidades geométricas compartidas para detección de PII
"""

from typing import Tuple, Optional
from loguru import logger


def rect_inside_bbox(
    rect,
    bbox: Tuple[float, float, float, float]
) -> bool:
    """
    Verifica si un rectángulo está dentro de una bbox

    Args:
        rect: Rectángulo de PyMuPDF (fitz.Rect) o cualquier objeto con x0, y0, x1, y1
        bbox: Tupla (x0, y0, x1, y1)

    Returns:
        True si el centro del rect está dentro de bbox
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
        logger.warning(f"Error en rect_inside_bbox: {e}, bbox={bbox}")
        return False


def find_precise_bbox(
    doc,
    page_num: int,
    search_text: str,
    block_bbox: Optional[Tuple[float, float, float, float]] = None
) -> Optional[Tuple[float, float, float, float]]:
    """
    Calcula la bounding box precisa para un texto buscándolo en la página del PDF.

    Args:
        doc: Documento PyMuPDF abierto
        page_num: Número de página
        search_text: Texto a buscar
        block_bbox: Bbox del bloque contenedor (fallback y filtro)

    Returns:
        Tupla (x0, y0, x1, y1) o None si no se puede calcular
    """
    try:
        if block_bbox and None in block_bbox:
            logger.warning(f"block_bbox contiene valores None: {block_bbox}")
            return None

        page = doc[page_num]
        text_instances = page.search_for(search_text)

        if text_instances:
            # Si hay block_bbox, buscar la instancia dentro del bloque
            if block_bbox:
                for rect in text_instances:
                    if rect_inside_bbox(rect, block_bbox):
                        return (rect.x0, rect.y0, rect.x1, rect.y1)

            # Usar la primera instancia
            rect = text_instances[0]
            return (rect.x0, rect.y0, rect.x1, rect.y1)

        # Fallback: usar bbox del bloque si disponible
        return block_bbox

    except Exception as e:
        logger.warning(f"Error calculando bbox precisa para '{search_text}': {e}")
        return block_bbox
