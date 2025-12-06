import React, { useMemo } from 'react'
import { Detection, getDetectionColor } from '../types/detection'
import { pdfToScreen, PDFBBox, ScreenRect } from '../utils/pdfCoordinates'

interface DetectionOverlayProps {
  detections: Detection[]
  currentPage: number
  pdfPageHeight: number
  scale: number
  canvasWidth: number
  canvasHeight: number
  approvedIndices: Set<number>
  rejectedIndices: Set<number>
  onDetectionClick: (index: number) => void
  onDetectionHover?: (index: number | null) => void
}

export const DetectionOverlay: React.FC<DetectionOverlayProps> = ({
  detections,
  currentPage,
  pdfPageHeight,
  scale,
  canvasWidth,
  canvasHeight,
  approvedIndices,
  rejectedIndices,
  onDetectionClick,
  onDetectionHover
}) => {
  // Filtrar detecciones de la página actual
  // NOTA: PyMuPDF usa índice base-0 (primera página = 0), PDF.js usa base-1 (primera página = 1)
  const pageDetections = detections.filter(d => d.page_num === currentPage - 1)

  // Debug desactivado para mejor visualización
  // console.log('===== DetectionOverlay - Render =====')
  // console.log('Página:', currentPage, '| Detecciones:', pageDetections.length)

  if (pageDetections.length === 0 || !canvasWidth || !canvasHeight) {
    return null
  }

  return (
    <svg
      className="absolute top-0 left-0"
      width={canvasWidth}
      height={canvasHeight}
      style={{
        pointerEvents: 'none'
      }}
    >
      {pageDetections.map((detection) => {
        const pdfBBox: PDFBBox = {
          x0: detection.bbox[0],
          y0: detection.bbox[1],
          x1: detection.bbox[2],
          y1: detection.bbox[3]
        }

        const screenRect: ScreenRect = pdfToScreen(pdfBBox, pdfPageHeight, scale)

        // Usar los campos directos del objeto en lugar de los Sets
        const isApproved = detection.isApproved || approvedIndices.has(detection.index)
        const isRejected = detection.isRejected || rejectedIndices.has(detection.index)

        // Color base según tipo de detección
        const baseColor = getDetectionColor(detection.type)

        // APROBADO (para anonimizar) = Rojo cruzado
        // RECHAZADO (NO anonimizar) = Naranja sin cruzar
        // PENDIENTE = Color base del tipo
        const displayColor = isApproved ? '#ef4444' : isRejected ? '#ff8c00' : baseColor
        const fillOpacity = isApproved ? 0.3 : isRejected ? 0.2 : 0.25
        const strokeWidth = isApproved ? 3 : isRejected ? 2 : 2

        return (
          <g key={detection.index}>
            {/* Rectángulo de detección */}
            <rect
              x={screenRect.x}
              y={screenRect.y}
              width={screenRect.width}
              height={screenRect.height}
              fill={displayColor}
              fillOpacity={fillOpacity}
              stroke={displayColor}
              strokeWidth={strokeWidth}
              strokeOpacity={isRejected ? 0.7 : 1}
              style={{
                pointerEvents: 'auto',
                cursor: 'pointer'
              }}
              onClick={() => onDetectionClick(detection.index)}
              onMouseEnter={() => onDetectionHover?.(detection.index)}
              onMouseLeave={() => onDetectionHover?.(null)}
            />

            {/* Indicador visual de estado */}
            {/* APROBADO (para anonimizar) = X cruzada en rojo */}
            {isApproved && (
              <>
                <line
                  x1={screenRect.x}
                  y1={screenRect.y}
                  x2={screenRect.x + screenRect.width}
                  y2={screenRect.y + screenRect.height}
                  stroke={displayColor}
                  strokeWidth={3}
                  strokeOpacity={0.9}
                  className="pointer-events-none"
                />
                <line
                  x1={screenRect.x + screenRect.width}
                  y1={screenRect.y}
                  x2={screenRect.x}
                  y2={screenRect.y + screenRect.height}
                  stroke={displayColor}
                  strokeWidth={3}
                  strokeOpacity={0.9}
                  className="pointer-events-none"
                />
              </>
            )}

            {/* RECHAZADO (NO anonimizar) = Sin marca adicional, solo naranja */}
          </g>
        )
      })}
    </svg>
  )
}
