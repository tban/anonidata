/**
 * Utilidades para transformación de coordenadas entre PDF y pantalla
 */

export interface PDFBBox {
  x0: number // PDF coordinates (origin top-left, same as screen)
  y0: number // (x0, y0) = top-left corner
  x1: number // (x1, y1) = bottom-right corner
  y1: number
}

export interface ScreenRect {
  x: number // Screen coordinates (origin top-left)
  y: number
  width: number
  height: number
}

/**
 * Transforma coordenadas de canvas rotado a PDF original (sin rotar)
 *
 * @param bbox - BBox en coordenadas del canvas rotado (donde dibuja el usuario)
 * @param rotation - Rotación de la página en grados (0, 90, 180, 270)
 * @param pageWidth - Ancho de la página PDF original (sin rotar)
 * @param pageHeight - Alto de la página PDF original (sin rotar)
 * @returns BBox en coordenadas del PDF original (para PyMuPDF)
 */
export function rotatedToPdfCoordinates(
  bbox: PDFBBox,
  rotation: number,
  pageWidth: number,
  pageHeight: number
): PDFBBox {
  // Normalizar rotación a 0, 90, 180, 270
  const normalizedRotation = ((rotation % 360) + 360) % 360

  switch (normalizedRotation) {
    case 0:
      // Sin rotación, devolver coordenadas sin cambios
      return bbox

    case 90:
      // Rotación 90° CW: Canvas tiene dimensiones (H, W)
      // Canvas (cx, cy) → PDF (H - cy, cx)
      return {
        x0: pageHeight - bbox.y1,
        y0: bbox.x0,
        x1: pageHeight - bbox.y0,
        y1: bbox.x1
      }

    case 180:
      // Rotación 180°: Canvas tiene dimensiones (W, H)
      // Canvas (cx, cy) → PDF (W - cx, H - cy)
      return {
        x0: pageWidth - bbox.x1,
        y0: pageHeight - bbox.y1,
        x1: pageWidth - bbox.x0,
        y1: pageHeight - bbox.y0
      }

    case 270:
      // Rotación 270° CW (= 90° CCW): Canvas tiene dimensiones (H, W)
      // Canvas (cx, cy) → PDF (cy, W - cx)
      return {
        x0: bbox.y0,
        y0: pageWidth - bbox.x1,
        x1: bbox.y1,
        y1: pageWidth - bbox.x0
      }

    default:
      console.warn(`Rotación no soportada: ${rotation}°. Usando coordenadas sin transformar.`)
      return bbox
  }
}

/**
 * Transforma coordenadas de PDF original a canvas rotado (para mostrar)
 *
 * @param bbox - BBox en coordenadas del PDF original (de PyMuPDF)
 * @param rotation - Rotación de la página en grados (0, 90, 180, 270)
 * @param pageWidth - Ancho de la página PDF original (sin rotar)
 * @param pageHeight - Alto de la página PDF original (sin rotar)
 * @returns BBox en coordenadas del canvas rotado (para mostrar al usuario)
 */
export function pdfToRotatedCoordinates(
  bbox: PDFBBox,
  rotation: number,
  pageWidth: number,
  pageHeight: number
): PDFBBox {
  // Normalizar rotación a 0, 90, 180, 270
  const normalizedRotation = ((rotation % 360) + 360) % 360

  switch (normalizedRotation) {
    case 0:
      // Sin rotación, devolver coordenadas sin cambios
      return bbox

    case 90:
      // Rotación 90° CW: PDF (px, py) → Canvas (py, H - px)
      return {
        x0: bbox.y0,
        y0: pageHeight - bbox.x1,
        x1: bbox.y1,
        y1: pageHeight - bbox.x0
      }

    case 180:
      // Rotación 180°: PDF (px, py) → Canvas (W - px, H - py)
      return {
        x0: pageWidth - bbox.x1,
        y0: pageHeight - bbox.y1,
        x1: pageWidth - bbox.x0,
        y1: pageHeight - bbox.y0
      }

    case 270:
      // Rotación 270° CW: PDF (px, py) → Canvas (W - py, px)
      return {
        x0: pageWidth - bbox.y1,
        y0: bbox.x0,
        x1: pageWidth - bbox.y0,
        y1: bbox.x1
      }

    default:
      console.warn(`Rotación no soportada: ${rotation}°. Usando coordenadas sin transformar.`)
      return bbox
  }
}

/**
 * Convierte coordenadas PDF a coordenadas de pantalla con escala
 *
 * IMPORTANTE: PyMuPDF y PDF.js usan el MISMO sistema de coordenadas:
 * - Origen en esquina superior-izquierda (0,0)
 * - Eje X crece hacia la derecha
 * - Eje Y crece hacia ABAJO
 * - bbox: (x0, y0, x1, y1) donde (x0,y0) es esquina superior-izquierda
 *
 * Por lo tanto, NO necesitamos invertir el eje Y, solo aplicar escala.
 *
 * @param pdfBBox - Coordenadas en el espacio PDF (PyMuPDF format)
 * @param pdfPageHeight - Altura de la página PDF en puntos (sin escalar) - NO USADO
 * @param scale - Factor de escala (zoom)
 * @param canvasOffsetX - Offset horizontal del canvas
 * @param canvasOffsetY - Offset vertical del canvas
 * @returns Rectángulo en coordenadas de pantalla
 */
export function pdfToScreen(
  pdfBBox: PDFBBox,
  pdfPageHeight: number,
  scale: number,
  canvasOffsetX: number = 0,
  canvasOffsetY: number = 0
): ScreenRect {
  // PyMuPDF y PDF.js usan el mismo sistema de coordenadas
  // Solo necesitamos escalar las coordenadas, sin inversión de ejes

  const screenX = pdfBBox.x0 * scale + canvasOffsetX
  const screenY = pdfBBox.y0 * scale + canvasOffsetY
  const width = (pdfBBox.x1 - pdfBBox.x0) * scale
  const height = (pdfBBox.y1 - pdfBBox.y0) * scale

  return { x: screenX, y: screenY, width, height }
}

/**
 * Convierte coordenadas de pantalla a coordenadas PDF
 *
 * @param screenRect - Rectángulo en coordenadas de pantalla
 * @param pdfPageHeight - Altura de la página PDF en puntos - NO USADO
 * @param scale - Factor de escala (zoom)
 * @param canvasOffsetX - Offset horizontal del canvas
 * @param canvasOffsetY - Offset vertical del canvas
 * @returns Coordenadas en el espacio PDF
 */
export function screenToPdf(
  screenRect: ScreenRect,
  pdfPageHeight: number,
  scale: number,
  canvasOffsetX: number = 0,
  canvasOffsetY: number = 0
): PDFBBox {
  // Mismo sistema de coordenadas, solo desescalar
  const x0 = (screenRect.x - canvasOffsetX) / scale
  const y0 = (screenRect.y - canvasOffsetY) / scale
  const x1 = (screenRect.x + screenRect.width - canvasOffsetX) / scale
  const y1 = (screenRect.y + screenRect.height - canvasOffsetY) / scale

  return { x0, y0, x1, y1 }
}

/**
 * Calcula el factor de escala para ajustar el PDF al ancho del contenedor
 *
 * @param pdfPageWidth - Ancho de la página PDF en puntos
 * @param containerWidth - Ancho del contenedor en píxeles
 * @param maxScale - Escala máxima permitida
 * @returns Factor de escala
 */
export function calculateFitToWidthScale(
  pdfPageWidth: number,
  containerWidth: number,
  maxScale: number = 3.0
): number {
  const scale = containerWidth / pdfPageWidth
  return Math.min(scale, maxScale)
}
