"""
Parser de PDFs usando PyMuPDF
Extrae texto, imágenes y estructura del documento
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF no instalado. Ejecutar: pip install PyMuPDF")
    raise


@dataclass
class TextBlock:
    """Bloque de texto extraído"""
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    page_num: int
    font_size: float = 0.0
    font_name: str = ""


@dataclass
class ImageBlock:
    """Imagen extraída del PDF"""
    image_data: bytes
    bbox: tuple[float, float, float, float]
    page_num: int
    width: int
    height: int
    xref: int  # Referencia en el PDF


@dataclass
class PDFData:
    """Datos extraídos del PDF"""
    file_path: Path
    page_count: int
    text_blocks: List[TextBlock]
    image_blocks: List[ImageBlock]
    metadata: Dict[str, Any]
    document: Any  # fitz.Document


class PDFParser:
    """Parser de PDFs"""

    def parse(self, file_path: Path) -> PDFData:
        """
        Parsea un archivo PDF

        Args:
            file_path: Ruta al PDF

        Returns:
            PDFData con toda la información extraída
        """
        logger.debug(f"Parseando PDF: {file_path.name}")

        doc = fitz.open(file_path)

        try:
            # Extraer metadatos
            metadata = self._extract_metadata(doc)

            # Extraer texto
            text_blocks = self._extract_text(doc)

            # Extraer imágenes
            image_blocks = self._extract_images(doc)

            pdf_data = PDFData(
                file_path=file_path,
                page_count=doc.page_count,
                text_blocks=text_blocks,
                image_blocks=image_blocks,
                metadata=metadata,
                document=doc,
            )

            logger.debug(
                f"Parseado completo: {len(text_blocks)} bloques de texto, "
                f"{len(image_blocks)} imágenes"
            )

            return pdf_data

        except Exception as e:
            doc.close()
            raise e

    def _extract_metadata(self, doc: fitz.Document) -> Dict[str, Any]:
        """Extrae metadatos del documento"""
        metadata = doc.metadata or {}
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "keywords": metadata.get("keywords", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creationDate": metadata.get("creationDate", ""),
            "modDate": metadata.get("modDate", ""),
        }

    def _extract_text(self, doc: fitz.Document) -> List[TextBlock]:
        """
        Extrae todo el texto con coordenadas

        Args:
            doc: Documento PyMuPDF

        Returns:
            Lista de TextBlocks
        """
        text_blocks = []

        for page_num, page in enumerate(doc):
            # Extraer bloques con información de posición
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if block.get("type") == 0:  # Tipo texto
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if text:
                                bbox = span.get("bbox", (0, 0, 0, 0))
                                text_blocks.append(
                                    TextBlock(
                                        text=text,
                                        bbox=bbox,
                                        page_num=page_num,
                                        font_size=span.get("size", 0),
                                        font_name=span.get("font", ""),
                                    )
                                )

        return text_blocks

    def _extract_images(self, doc: fitz.Document) -> List[ImageBlock]:
        """
        Extrae todas las imágenes del PDF

        Args:
            doc: Documento PyMuPDF

        Returns:
            Lista de ImageBlocks
        """
        image_blocks = []

        for page_num, page in enumerate(doc):
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                xref = img[0]

                try:
                    # Extraer imagen
                    base_image = doc.extract_image(xref)
                    image_data = base_image["image"]

                    # Obtener bbox de la imagen en la página
                    img_rects = page.get_image_rects(xref)

                    if img_rects:
                        bbox = img_rects[0]  # Primera ocurrencia

                        image_blocks.append(
                            ImageBlock(
                                image_data=image_data,
                                bbox=(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                                page_num=page_num,
                                width=base_image["width"],
                                height=base_image["height"],
                                xref=xref,
                            )
                        )

                except Exception as e:
                    logger.warning(f"Error extrayendo imagen {xref}: {e}")
                    continue

        return image_blocks

    def get_page_text(self, pdf_data: PDFData, page_num: int) -> str:
        """
        Obtiene todo el texto de una página

        Args:
            pdf_data: Datos del PDF
            page_num: Número de página

        Returns:
            Texto completo de la página
        """
        blocks = [b for b in pdf_data.text_blocks if b.page_num == page_num]
        return " ".join(b.text for b in blocks)

    def close(self, pdf_data: PDFData) -> None:
        """Cierra el documento PDF"""
        if pdf_data.document:
            pdf_data.document.close()
