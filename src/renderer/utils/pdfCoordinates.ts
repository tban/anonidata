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
