import React, { useState, useRef, useCallback } from 'react'
import { screenToPdf, rotatedToPdfCoordinates, ScreenRect } from '../utils/pdfCoordinates'

interface SelectionOverlayProps {
  canvasWidth: number
  canvasHeight: number
  pdfPageHeight: number
  pdfPageWidth: number
  pageRotation: number
  scale: number
  onAddManualDetection: (bbox: [number, number, number, number]) => void
}

export const SelectionOverlay: React.FC<SelectionOverlayProps> = ({
  canvasWidth,
  canvasHeight,
  pdfPageHeight,
  pdfPageWidth,
  pageRotation,
  scale,
  onAddManualDetection
}) => {
  const [isDrawing, setIsDrawing] = useState(false)
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null)
  const [currentPoint, setCurrentPoint] = useState<{ x: number; y: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const getMousePosition = useCallback((event: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return null

    const rect = svgRef.current.getBoundingClientRect()
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    }
  }, [])

  const handleMouseDown = useCallback((event: React.MouseEvent<SVGSVGElement>) => {
    const pos = getMousePosition(event)
    if (!pos) return

    setIsDrawing(true)
    setStartPoint(pos)
    setCurrentPoint(pos)
  }, [getMousePosition])

  const handleMouseMove = useCallback((event: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing || !startPoint) return

    const pos = getMousePosition(event)
    if (!pos) return

    setCurrentPoint(pos)
  }, [isDrawing, startPoint, getMousePosition])

  const handleMouseUp = useCallback((event: React.MouseEvent<SVGSVGElement>) => {
    if (!isDrawing || !startPoint) return

    const endPos = getMousePosition(event)
    if (!endPos) return

    // Calcular el rectángulo de selección
    const minX = Math.min(startPoint.x, endPos.x)
    const minY = Math.min(startPoint.y, endPos.y)
    const maxX = Math.max(startPoint.x, endPos.x)
    const maxY = Math.max(startPoint.y, endPos.y)
    const width = maxX - minX
    const height = maxY - minY

    // Ignorar selecciones muy pequeñas (clics accidentales)
    if (width < 10 || height < 10) {
      setIsDrawing(false)
      setStartPoint(null)
      setCurrentPoint(null)
      return
    }

    // Convertir coordenadas de pantalla a coordenadas PDF
    const screenRect: ScreenRect = {
      x: minX,
      y: minY,
      width,
      height
    }

    // Convertir de pantalla a coordenadas PDF (solo desescalar, sin transformaciones de rotación)
    // PyMuPDF usa directamente las coordenadas del viewport, sin transformaciones adicionales
    const pdfBBox = screenToPdf(screenRect, pdfPageHeight, scale)

    const bbox: [number, number, number, number] = [
      pdfBBox.x0,
      pdfBBox.y0,
      pdfBBox.x1,
      pdfBBox.y1
    ]

    // DEBUG: Log detallado de la conversión de coordenadas
    console.log('=== SELECCIÓN MANUAL ===')
    console.log('Canvas dimensions:', { width: canvasWidth, height: canvasHeight })
    console.log('PDF page dimensions:', { width: pdfPageWidth, height: pdfPageHeight })
    console.log('Page rotation (ignorada):', pageRotation, 'degrees')
    console.log('Scale:', scale)
    console.log('Screen rect:', screenRect)
    console.log('PDF bbox (desescalado):', pdfBBox)
    console.log('Final bbox array:', bbox)
    console.log('=======================')

    // Llamar al callback con las coordenadas PDF
    onAddManualDetection(bbox)

    // Resetear estado
    setIsDrawing(false)
    setStartPoint(null)
    setCurrentPoint(null)
  }, [isDrawing, startPoint, getMousePosition, pdfPageHeight, pdfPageWidth, pageRotation, scale, onAddManualDetection, canvasWidth, canvasHeight])

  const handleMouseLeave = useCallback(() => {
    // Si el usuario sale del área mientras dibuja, cancelar la selección
    if (isDrawing) {
      setIsDrawing(false)
      setStartPoint(null)
      setCurrentPoint(null)
    }
  }, [isDrawing])

  // Calcular rectángulo temporal para visualización
  const getSelectionRect = useCallback(() => {
    if (!startPoint || !currentPoint) return null

    const minX = Math.min(startPoint.x, currentPoint.x)
    const minY = Math.min(startPoint.y, currentPoint.y)
    const width = Math.abs(currentPoint.x - startPoint.x)
    const height = Math.abs(currentPoint.y - startPoint.y)

    return { x: minX, y: minY, width, height }
  }, [startPoint, currentPoint])

  const selectionRect = getSelectionRect()

  if (!canvasWidth || !canvasHeight) return null

  return (
    <svg
      ref={svgRef}
      className="absolute top-0 left-0"
      width={canvasWidth}
      height={canvasHeight}
      style={{
        pointerEvents: 'auto',
        cursor: isDrawing ? 'crosshair' : 'crosshair'
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      {/* Rectángulo de selección temporal */}
      {isDrawing && selectionRect && (
        <rect
          x={selectionRect.x}
          y={selectionRect.y}
          width={selectionRect.width}
          height={selectionRect.height}
          fill="rgba(245, 158, 11, 0.2)"
          stroke="#f59e0b"
          strokeWidth={2}
          strokeDasharray="5,5"
          className="pointer-events-none"
        />
      )}
    </svg>
  )
}
