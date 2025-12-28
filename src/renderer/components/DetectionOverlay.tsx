import React, { useMemo } from 'react'
import { Detection, getDetectionColor } from '../types/detection'
import { pdfToScreen, pdfToRotatedCoordinates, PDFBBox, ScreenRect } from '../utils/pdfCoordinates'

interface DetectionOverlayProps {
  detections: Detection[]
  currentPage: number
  pdfPageHeight: number
  pdfPageWidth: number
  pageRotation: number
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
  pdfPageWidth,
  pageRotation,
  scale,
  canvasWidth,
  canvasHeight,
  approvedIndices,
  rejectedIndices,
  onDetectionClick,
  onDetectionHover
}) => {
  // Filtrar detecciones de la página actual
  const pageDetections = detections.filter(d => d.page_num === currentPage - 1)

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

        const isApproved = detection.isApproved || approvedIndices.has(detection.index)
        const isRejected = detection.isRejected || rejectedIndices.has(detection.index)
        const baseColor = getDetectionColor(detection.type)

        const displayColor = isApproved ? '#ef4444' : isRejected ? '#ff8c00' : baseColor
        const fillOpacity = isApproved ? 0.3 : isRejected ? 0.2 : 0.25
        const strokeWidth = isApproved ? 3 : isRejected ? 2 : 2

        // Cálculo ancho etiqueta aprox (6px por char + padding)
        const labelWidth = (detection.type.length * 7) + 12

        return (
          <g key={detection.index} className="group">
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

            {/* Etiqueta de Tipo (visible siempre o en hover?) - Siempre visible ayuda */}
            <g style={{ pointerEvents: 'none' }}>
              <rect
                x={screenRect.x}
                y={screenRect.y - 16}
                width={labelWidth}
                height={16}
                rx={2}
                fill={baseColor}
                opacity={0.9}
              />
              <text
                x={screenRect.x + 4}
                y={screenRect.y - 4}
                fill="white"
                fontSize="10"
                fontWeight="bold"
                fontFamily="sans-serif"
              >
                {detection.type}
              </text>
            </g>

            {/* Indicador visual Aprobado (X cruzada grande) */}
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
          </g>
        )
      })}
    </svg>
  )
}
