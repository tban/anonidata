"""
Motor de anonimización irreversible de PDFs
Aplica redacción mediante cajas negras, pixelación o difuminado
"""

import io
import json
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

import numpy as np
from PIL import Image, ImageFilter

try:
    import fitz  # PyMuPDF
except ImportError:
    logger.error("PyMuPDF no instalado")
    raise

try:
    import cv2
except ImportError:
    logger.warning("opencv-python no instalado")
    cv2 = None

from core.config import Settings
from processors.pdf_parser import PDFData
from detectors.pii_detector import PIIMatch
from utils.file_manager import FileManager


class Anonymizer:
    """Motor de anonimización de PDFs"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.file_manager = FileManager(settings)

    def anonymize(
        self,
        input_path: Path,
        pdf_data: PDFData,
        pii_matches: List[PIIMatch],
    ) -> Path:
        """
        Anonimiza un PDF redactando todos los matches de PII

        Args:
            input_path: Ruta al PDF original
            pdf_data: Datos del PDF parseado
            pii_matches: Lista de PII detectados

        Returns:
            Ruta al PDF anonimizado
        """
        logger.info(f"Anonimizando {len(pii_matches)} elementos")

        # Generar ruta de salida
        output_path = self.file_manager.generate_output_path(input_path)

        # Abrir documento
        doc = fitz.open(input_path)

        try:
            # Aplanar campos de formulario interactivos por defecto para evitar que se superpongan a las redacciones
            if hasattr(doc, "bake"):
                doc.bake(annots=False, widgets=True)
            else:
                logger.warning("El método 'bake' no está disponible en esta versión de PyMuPDF.")

            # Agrupar matches por página
            matches_by_page = self._group_by_page(pii_matches)

            # Procesar cada página
            for page_num, matches in matches_by_page.items():
                if page_num < doc.page_count:
                    page = doc[page_num]
                    self._anonymize_page(page, matches)

            # Añadir encabezado a todas las páginas
            for page in doc:
                is_scanned = self._is_scanned_page(page)
                self._add_header(page, is_scanned=is_scanned)

            # Guardar documento anonimizado
            doc.save(
                str(output_path),
                garbage=4,  # Máxima compresión
                deflate=True,
                clean=True,
            )

            logger.info(f"PDF anonimizado guardado: {output_path.name}")

            return output_path

        finally:
            doc.close()

    def _group_by_page(self, matches: List[PIIMatch]) -> Dict[int, List[PIIMatch]]:
        """Agrupa matches por número de página"""
        grouped: Dict[int, List[PIIMatch]] = {}

        for match in matches:
            page_num = match.page_num
            if page_num not in grouped:
                grouped[page_num] = []
            grouped[page_num].append(match)

        return grouped

    def _add_header(self, page: fitz.Page, is_scanned: bool = False) -> None:
        """
        Añade encabezado "AnoniData (año)" en la esquina superior derecha

        Args:
            page: Página de PyMuPDF
            is_scanned: Si True, aplica transformación de coordenadas para páginas escaneadas
        """
        from datetime import datetime

        # Obtener año actual
        current_year = datetime.now().year
        header_text = f"AnoniData ({current_year})"

        # Obtener dimensiones de la página
        page_rect = page.rect

        # Configurar posición: esquina superior derecha con margen
        margin = 20
        font_size = 8

        # Calcular ancho aproximado del texto (estimación: 6 pixeles por caracter)
        text_width_approx = len(header_text) * (font_size * 0.6)

        # Si la pagina tiene rotación, debemos calcular la posición visual Top-Right
        # y transformarla a coordenadas de UserSpace
        if page.rotation != 0:
            # Calcular posición en coordenadas visuales (viewport)
            # Como si la página estuviera vertical y "normal"
            # Visual Top-Right
            vis_x = page.rect.width - text_width_approx - margin
            vis_y = margin + font_size

            # Obtener matriz de derotación (Visual -> UserSpace)
            mat = page.derotation_matrix
            
            # Transformar punto visual a UserSpace
            point_vis = fitz.Point(vis_x, vis_y)
            point_us = point_vis * mat
            
            x, y = point_us.x, point_us.y
            
            # Rotar el texto para compensar la rotación de la página
            # Usar page.rotation positivo corrige la orientación "boca abajo"
            text_rotation = page.rotation
            
            logger.debug(f"Header: Visual({vis_x}, {vis_y}) -> User({x}, {y}) | Rot({text_rotation})")

            # Insertar texto con coordenadas transformadas y rotación
            page.insert_text(
                (x, y),
                header_text,
                fontsize=font_size,
                fontname="helv",  # Helvetica
                color=(0.5, 0.5, 0.5),  # Gris medio (RGB)
                rotate=text_rotation
            )
        else:
            # Página estándar sin rotación
            x = page.rect.width - text_width_approx - margin
            y = margin + font_size  # Añadir font_size para que el texto no se corte

            # Insertar texto directamente
            page.insert_text(
                (x, y),
                header_text,
                fontsize=font_size,
                fontname="helv",  # Helvetica
                color=(0.5, 0.5, 0.5)  # Gris medio (RGB)
            )

    def _anonymize_page(self, page: fitz.Page, matches: List[PIIMatch], force_image_mode: bool = False) -> None:
        """
        Anonimiza una página completa

        Args:
            page: Página de PyMuPDF
            matches: Matches a redactar
            force_image_mode: Si True, fuerza el uso de lógica de página escaneada
        """
        logger.info(f"Anonimizando página {page.number}: {len(matches)} detecciones")

        # Detectar si la página es principalmente imagen escaneada
        # Si force_image_mode es True, asumimos que es escaneada
        is_scanned = force_image_mode or self._is_scanned_page(page)

        if is_scanned:
            mode_str = "FORZADO (imagen)" if force_image_mode else "detectado escaneado"
            logger.info(f"Página {page.number} tratada como imagen ({mode_str}), usando método de renderizado y rotación")
            self._anonymize_scanned_page(page, matches)
        else:
            logger.info(f"Página {page.number} con texto nativo, usando redacciones estándar")
            self._anonymize_text_page(page, matches)

    def _is_scanned_page(self, page: fitz.Page) -> bool:
        """
        Detecta si una página es principalmente imagen escaneada

        Args:
            page: Página de PyMuPDF

        Returns:
            True si es página escaneada, False si tiene texto nativo
        """
        # Extraer texto de la página. Si tiene suficiente texto, es un Searchable PDF o PDF nativo.
        text_len = len(page.get_text("text").strip())
        if text_len > 100:
            return False  # Tiene texto, se procesa conservando la capa de texto

        # Si no tiene texto y tiene imágenes grandes (>40% de la página), tratarla como escaneada pura
        image_list = page.get_images(full=True)
        if len(image_list) > 0:
            page_area = page.rect.width * page.rect.height
            for img in image_list:
                xref = img[0]
                try:
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        img_rect = img_rects[0]
                        img_area = (img_rect.x1 - img_rect.x0) * (img_rect.y1 - img_rect.y0)
                        if img_area > page_area * 0.4:
                            return True
                except Exception:
                    pass
        return False

    def _merge_boxes(self, boxes: list, x_tol: float = 12.0, y_tol: float = 5.0) -> list:
        if not boxes: return []
        boxes.sort(key=lambda b: (b[1], b[0]))
        merged = []
        curr = list(boxes[0])
        for b in boxes[1:]:
            same_line = abs(curr[1] - b[1]) <= y_tol and abs(curr[3] - b[3]) <= y_tol
            adjacent_x = (b[0] - curr[2]) <= x_tol and (curr[0] - b[2]) <= x_tol
            if same_line and adjacent_x:
                curr = [min(curr[0], b[0]), min(curr[1], b[1]), max(curr[2], b[2]), max(curr[3], b[3])]
            else:
                merged.append(tuple(curr))
                curr = list(b)
        merged.append(tuple(curr))
        return merged

    def _anonymize_scanned_page(self, page: fitz.Page, matches: List[PIIMatch]) -> None:
        """
        Anonimiza una página escaneada usando ANOTACIONES (overlays no destructivos)
        Las anotaciones se colocan SOBRE el contenido sin modificarlo

        Args:
            page: Página de PyMuPDF
            matches: Matches a redactar
        """
        logger.info(f"Anonimizando página escaneada {page.number} con {len(matches)} matches usando anotaciones")

        # Obtener dimensiones de la página PDF original (sin rotar)
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        # 1. Marcar áreas para destruir el texto subyacente (OCR)
        # Separar boxes de texto para fusionarlas y evitar solapamiento de [ANONIMIZADO]
        boxes_text = []
        for match in matches:
            bbox = match.bbox
            if page.rotation != 0:
                mat = page.derotation_matrix
                target_rect = fitz.Rect(bbox) * mat
            else:
                target_rect = fitz.Rect(bbox)
            
            if match.type == "MANUAL_IMAGE":
                page.add_redact_annot(target_rect, fill=self.settings.redaction_color)
            elif match.type == "MANUAL_TEXT":
                boxes_text.append(target_rect)
            else:
                if self.settings.redaction_strategy == "text_label":
                    boxes_text.append(target_rect)
                else:
                    page.add_redact_annot(target_rect, fill=self.settings.redaction_color)

        merged_text_boxes = self._merge_boxes([(r.x0, r.y0, r.x1, r.y1) for r in boxes_text])
        for bbox in merged_text_boxes:
            rect = fitz.Rect(bbox)
            page.add_redact_annot(
                rect,
                text="[ANONIMIZADO]",
                fill=(1.0, 1.0, 1.0),
                text_color=(1.0, 0.0, 0.0),
                fontsize=max(5.0, min(10.0, rect.height * 0.7)),
                fontname="helv",
                align=1
            )

        # 2. Destruir permanentemente el texto OCR y quemar el texto [ANONIMIZADO]
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        logger.info(f"Página escaneada {page.number} anonimizada")

    def _anonymize_text_page(self, page: fitz.Page, matches: List[PIIMatch]) -> None:
        """
        Anonimiza una página con texto nativo usando redacciones estándar

        Args:
            page: Página de PyMuPDF
            matches: Matches a redactar
        """
        # Marcar todas las regiones para redacción
        boxes_text = []
        boxes_black = []
        boxes_pixelate = []
        boxes_blur = []
        
        for i, match in enumerate(matches, 1):
            bbox = match.bbox
            x0, y0, x1, y1 = bbox
            if x1 - x0 > 4:
                bbox = (x0 + 1.5, y0, x1 - 1.5, y1)

            logger.debug(f"  [{i}/{len(matches)}] {match.type}: '{match.text}' | bbox: {bbox}")

            if match.type == "MANUAL_IMAGE":
                boxes_black.append(bbox)
            elif match.type == "MANUAL_TEXT":
                boxes_text.append(bbox)
            else:
                if self.settings.redaction_strategy == "black_box":
                    boxes_black.append(bbox)
                elif self.settings.redaction_strategy == "text_label":
                    boxes_text.append(bbox)
                elif self.settings.redaction_strategy == "pixelate":
                    boxes_pixelate.append(bbox)
                elif self.settings.redaction_strategy == "blur":
                    boxes_blur.append(bbox)
                    
        # Apply standard redact annotations
        for bbox in boxes_black:
            self._apply_black_box(page, bbox)
            
        merged_text_boxes = self._merge_boxes(boxes_text)
        for bbox in merged_text_boxes:
            rect = fitz.Rect(bbox)
            page.add_redact_annot(
                rect,
                text="[ANONIMIZADO]",
                fill=(1.0, 1.0, 1.0),
                text_color=(1.0, 0.0, 0.0),
                fontsize=max(5.0, min(10.0, rect.height * 0.7)),
                fontname="helv",
                align=1
            )
            
        for bbox in boxes_pixelate:
            self._apply_pixelation(page, bbox)
            
        for bbox in boxes_blur:
            self._apply_blur(page, bbox)

        # Aplicar redacciones destructivas (borra el contenido original y quema el texto [ANONIMIZADO])
        logger.info(f"Aplicando {len(matches)} redacciones a página {page.number}")
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    def _apply_black_box(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica redacción destructiva con caja negra (ELIMINA el contenido del PDF)

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas (x0, y0, x1, y1)
        """
        rect = fitz.Rect(bbox)

        # Marcar región para redacción con relleno negro
        # fill: color de relleno después de eliminar el contenido
        page.add_redact_annot(rect, fill=self.settings.redaction_color)



    def _apply_pixelation(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica pixelación a una región con redacción destructiva

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas
        """
        if cv2 is None:
            # Fallback a caja negra si no hay OpenCV
            self._apply_black_box(page, bbox)
            return

        try:
            # Renderizar región ANTES de redactar
            rect = fitz.Rect(bbox)
            mat = fitz.Matrix(2.0, 2.0)  # 2x resolución
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Convertir a imagen PIL
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            img_array = np.array(img)

            # Aplicar pixelación
            h, w = img_array.shape[:2]
            pixel_size = self.settings.pixelation_level

            # Reducir y ampliar para pixelar
            temp_h = max(1, h // pixel_size)
            temp_w = max(1, w // pixel_size)

            temp = cv2.resize(img_array, (temp_w, temp_h), interpolation=cv2.INTER_LINEAR)
            pixelated = cv2.resize(temp, (w, h), interpolation=cv2.INTER_NEAREST)

            # Convertir de vuelta a PIL
            pixelated_img = Image.fromarray(pixelated)

            # Guardar imagen pixelada como bytes
            img_bytes = io.BytesIO()
            pixelated_img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Marcar región para redacción con la imagen pixelada como relleno
            # IMPORTANTE: Esto ELIMINA el texto original
            page.add_redact_annot(rect, fill=self.settings.redaction_color, image=img_bytes.getvalue())

        except Exception as e:
            logger.warning(f"Error aplicando pixelación: {e}, usando caja negra")
            self._apply_black_box(page, bbox)

    def _apply_blur(self, page: fitz.Page, bbox: tuple) -> None:
        """
        Aplica difuminado gaussiano a una región con redacción destructiva

        Args:
            page: Página de PyMuPDF
            bbox: Coordenadas
        """
        try:
            # Renderizar región ANTES de redactar
            rect = fitz.Rect(bbox)
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, clip=rect)

            # Convertir a PIL
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            # Aplicar blur fuerte
            blurred = img.filter(ImageFilter.GaussianBlur(radius=20))

            # Guardar imagen difuminada como bytes
            img_bytes = io.BytesIO()
            blurred.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Marcar región para redacción con la imagen difuminada como relleno
            # IMPORTANTE: Esto ELIMINA el texto original
            page.add_redact_annot(rect, fill=self.settings.redaction_color, image=img_bytes.getvalue())

        except Exception as e:
            logger.warning(f"Error aplicando blur: {e}, usando caja negra")
            self._apply_black_box(page, bbox)

    def create_pre_anonymized(
        self,
        input_path: Path,
        pii_matches: List[PIIMatch],
    ) -> tuple[Path, Path]:
        """
        Crea un PDF pre-anonimizado (copia del original SIN anotaciones visuales)
        y guarda las detecciones en un archivo JSON.

        Las anotaciones visuales se manejan en el frontend con overlays SVG interactivos.

        Args:
            input_path: Ruta al PDF original
            pii_matches: Lista de PII detectados

        Returns:
            Tupla con (ruta_pdf_pre_anonimizado, ruta_json_detecciones)
        """
        logger.info(f"Creando PDF pre-anonimizado con {len(pii_matches)} detecciones")

        # Generar rutas de salida
        pre_anon_path = self.file_manager.generate_pre_anonymized_path(input_path)
        detections_path = self.file_manager.generate_detections_path(input_path)

        # Abrir documento
        doc = fitz.open(input_path)

        try:
            # Aplanar campos de formulario interactivos en el documento de vista previa
            if hasattr(doc, "bake"):
                doc.bake(annots=False, widgets=True)
            else:
                logger.warning("El método 'bake' no está disponible en esta versión de PyMuPDF.")

            # NO agregar anotaciones visuales al PDF
            # El frontend se encarga de mostrar rectángulos interactivos con SVG overlay

            # Simplemente guardar una copia del PDF original
            doc.save(
                str(pre_anon_path),
                garbage=4,
                deflate=True,
                clean=True,
            )

            logger.info(f"PDF pre-anonimizado guardado (copia sin anotaciones): {pre_anon_path.name}")

            # Guardar detecciones a JSON
            self.save_detections(pii_matches, detections_path)

            return pre_anon_path, detections_path

        finally:
            doc.close()

    def apply_final_redactions(
        self,
        input_path: Path,
        approved_detections: List[PIIMatch],
        force_image_mode: bool = False,
    ) -> Path:
        """
        Aplica redacciones finales SOLO a las detecciones aprobadas,
        eliminando permanentemente el texto subyacente

        Args:
            input_path: Ruta al PDF original
            approved_detections: Lista de PII aprobados para anonimizar
            force_image_mode: Si True, fuerza el uso de lógica de página escaneada (rotación coords)

        Returns:
            Ruta al PDF final anonimizado
        """
        logger.info(f"Aplicando redacciones finales a {len(approved_detections)} detecciones aprobadas")

        # Generar ruta de salida
        output_path = self.file_manager.generate_output_path(input_path)

        # Abrir documento original (NO el pre-anonimizado)
        doc = fitz.open(input_path)

        try:
            # Aplanar campos de formulario interactivos para que las redacciones se apliquen sobre texto estático
            if hasattr(doc, "bake"):
                doc.bake(annots=False, widgets=True)
            else:
                logger.warning("El método 'bake' no está disponible en esta versión de PyMuPDF.")

            # Agrupar detecciones aprobadas por página
            matches_by_page = self._group_by_page(approved_detections)

            # Procesar cada página
            for page_num, matches in matches_by_page.items():
                if page_num < doc.page_count:
                    page = doc[page_num]
                    self._anonymize_page(page, matches, force_image_mode=force_image_mode)

            # Añadir encabezado a todas las páginas
            for page in doc:
                is_scanned = self._is_scanned_page(page)
                self._add_header(page, is_scanned=is_scanned)

            # Guardar documento final anonimizado
            doc.save(
                str(output_path),
                garbage=4,
                deflate=True,
                clean=True,
            )

            logger.info(f"PDF final anonimizado guardado: {output_path.name}")

            return output_path

        finally:
            doc.close()

    def save_detections(self, pii_matches: List[PIIMatch], output_path: Path) -> None:
        """
        Serializa detecciones de PII a JSON

        Args:
            pii_matches: Lista de detecciones PII
            output_path: Ruta del archivo JSON de salida
        """
        detections_data = []

        for idx, match in enumerate(pii_matches):
            detection = {
                "index": idx,
                "type": match.type,
                "text": match.text,
                "bbox": list(match.bbox),  # tuple -> list para JSON
                "page_num": match.page_num,
                "confidence": match.confidence,
                "source": match.source,
            }
            detections_data.append(detection)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(detections_data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Detecciones guardadas en: {output_path.name}")

    def load_detections(self, detections_path: Path) -> List[PIIMatch]:
        """
        Deserializa detecciones de PII desde JSON

        Args:
            detections_path: Ruta del archivo JSON con detecciones

        Returns:
            Lista de objetos PIIMatch
        """
        with open(detections_path, 'r', encoding='utf-8') as f:
            detections_data = json.load(f)

        pii_matches = []
        for detection in detections_data:
            match = PIIMatch(
                type=detection["type"],
                text=detection["text"],
                bbox=tuple(detection["bbox"]),  # list -> tuple
                page_num=detection["page_num"],
                confidence=detection["confidence"],
                source=detection["source"],
            )
            pii_matches.append(match)

        logger.debug(f"Cargadas {len(pii_matches)} detecciones desde: {detections_path.name}")
        return pii_matches
