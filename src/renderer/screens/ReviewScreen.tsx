import React, { useState, useEffect } from 'react'
import { PDFViewer } from '../components/PDFViewer'
import { DetectionOverlay } from '../components/DetectionOverlay'
import { SelectionOverlay } from '../components/SelectionOverlay'
import { Detection } from '../types/detection'
import type { PDFDocumentProxy } from 'pdfjs-dist'

interface ReviewScreenProps {
  originalFilePath: string
  preAnonymizedPath: string
  detectionsPath: string
  onFinish: (approvedIndices: number[]) => void
  onCancel: () => void
}

export const ReviewScreen: React.FC<ReviewScreenProps> = ({
  originalFilePath,
  preAnonymizedPath,
  detectionsPath,
  onFinish,
  onCancel
}) => {
  const [detections, setDetections] = useState<Detection[]>([])
  const [approvedIndices, setApprovedIndices] = useState<Set<number>>(new Set())
  const [rejectedIndices, setRejectedIndices] = useState<Set<number>>(new Set())
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [scale, setScale] = useState(1.5)
  const [pdfPageHeight, setPdfPageHeight] = useState(0)
  const [pdfPageWidth, setPdfPageWidth] = useState(0)
  const [canvasWidth, setCanvasWidth] = useState(0)
  const [canvasHeight, setCanvasHeight] = useState(0)
  const [pageRotation, setPageRotation] = useState(0)
  const [hoveredDetectionIndex, setHoveredDetectionIndex] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [overlayVersion, setOverlayVersion] = useState(0)
  const [isSelectionMode, setIsSelectionMode] = useState(false)
  const [loadingStep, setLoadingStep] = useState('Cargando detecciones')
  const viewerContainerRef = React.useRef<HTMLDivElement>(null)

  // Enriquecer detecciones con estado usando useMemo
  const enrichedDetections = React.useMemo(() => {
    return detections.map(d => ({
      ...d,
      isApproved: approvedIndices.has(d.index),
      isRejected: rejectedIndices.has(d.index)
    }))
  }, [detections, approvedIndices, rejectedIndices])

  // Cargar detecciones
  useEffect(() => {
    const loadDetections = async () => {
      try {
        setLoading(true)

        // Simular pasos de carga para mejor UX
        const steps = [
          'Cargando detecciones',
          'Analizando documento',
          'Preparando visor'
        ]

        let stepIndex = 0
        const stepInterval = setInterval(() => {
          if (stepIndex < steps.length) {
            setLoadingStep(steps[stepIndex])
            stepIndex++
          }
        }, 800)

        const result = await window.anonidata.review.loadDetections(detectionsPath)

        clearInterval(stepInterval)

        if (result.success && result.detections) {
          setDetections(result.detections)

          // Marcar todas las detecciones como aprobadas por defecto
          const allIndices = new Set(result.detections.map((d: Detection) => d.index))
          setApprovedIndices(allIndices)
        } else {
          console.error('Error cargando detecciones:', result.error)
        }
      } catch (error) {
        console.error('Error cargando detecciones:', error)
      } finally {
        setLoading(false)
        setLoadingStep('Cargando detecciones')
      }
    }

    loadDetections()
  }, [detectionsPath])

  const handlePageRendered = (pageInfo: {
    width: number
    height: number
    pageNum: number
    originalWidth: number
    originalHeight: number
    rotation: number
  }) => {
    setPdfPageHeight(pageInfo.originalHeight)
    setPdfPageWidth(pageInfo.originalWidth)
    setCanvasWidth(pageInfo.width)
    setCanvasHeight(pageInfo.height)
    setPageRotation(pageInfo.rotation)
    console.log('PDF Page dimensions:', {
      original: { width: pageInfo.originalWidth, height: pageInfo.originalHeight },
      scaled: { width: pageInfo.width, height: pageInfo.height },
      rotation: pageInfo.rotation,
      scale: scale
    })
  }

  const handleFitToPage = () => {
    if (!viewerContainerRef.current || !canvasWidth || !canvasHeight) return

    const container = viewerContainerRef.current
    const containerWidth = container.clientWidth - 64 // Restar padding (32px cada lado)
    const containerHeight = container.clientHeight - 64

    // Calcular dimensiones originales del PDF
    const originalWidth = canvasWidth / scale
    const originalHeight = canvasHeight / scale

    // Calcular escalas necesarias para ajustar
    const scaleX = containerWidth / originalWidth
    const scaleY = containerHeight / originalHeight

    // Usar la escala menor para que quepa completo
    const newScale = Math.min(scaleX, scaleY, 3) // Máximo 300%
    setScale(Math.max(0.5, newScale)) // Mínimo 50%
  }

  const handleDocumentLoaded = (doc: PDFDocumentProxy) => {
    setTotalPages(doc.numPages)
  }

  const handleAddManualDetection = async (bbox: [number, number, number, number]) => {
    // Crear nueva detección manual
    const newDetection: Detection = {
      index: detections.length,
      type: 'MANUAL',
      text: 'Selección manual',
      bbox: bbox,
      page_num: currentPage - 1, // PyMuPDF usa base-0
      confidence: 1.0,
      source: 'manual',
    }

    // Agregar a la lista de detecciones
    const updatedDetections = [...detections, newDetection]
    setDetections(updatedDetections)

    // Marcar como aprobada automáticamente
    const newApproved = new Set(approvedIndices)
    newApproved.add(newDetection.index)
    setApprovedIndices(newApproved)

    setOverlayVersion(v => v + 1)

    // Guardar detecciones actualizadas en el archivo JSON
    try {
      await window.anonidata.review.saveDetections(detectionsPath, updatedDetections)
      console.log('Nueva detección manual guardada:', newDetection)
    } catch (error) {
      console.error('Error guardando detección manual:', error)
    }
  }

  const handleDetectionClick = (index: number) => {
    console.log('Click en detección:', index)
    console.log('Estado actual - Aprobada:', approvedIndices.has(index), 'Rechazada:', rejectedIndices.has(index))

    // Toggle entre estados: pendiente -> aprobado -> rechazado -> pendiente
    if (approvedIndices.has(index)) {
      // De aprobado a rechazado
      console.log('Cambiando de APROBADO a RECHAZADO')
      const newApproved = new Set(approvedIndices)
      newApproved.delete(index)
      setApprovedIndices(newApproved)

      const newRejected = new Set(rejectedIndices)
      newRejected.add(index)
      setRejectedIndices(newRejected)

      setOverlayVersion(v => v + 1)
    } else if (rejectedIndices.has(index)) {
      // De rechazado a pendiente
      console.log('Cambiando de RECHAZADO a PENDIENTE')
      const newRejected = new Set(rejectedIndices)
      newRejected.delete(index)
      setRejectedIndices(newRejected)

      setOverlayVersion(v => v + 1)
    } else {
      // De pendiente a aprobado
      console.log('Cambiando de PENDIENTE a APROBADO')
      const newApproved = new Set(approvedIndices)
      newApproved.add(index)
      setApprovedIndices(newApproved)

      setOverlayVersion(v => v + 1)
    }
  }

  const handleApproveAll = () => {
    const allIndices = new Set(detections.map(d => d.index))
    setApprovedIndices(allIndices)
    setRejectedIndices(new Set())
    setOverlayVersion(v => v + 1)
  }

  const handleRejectAll = () => {
    const allIndices = new Set(detections.map(d => d.index))
    setRejectedIndices(allIndices)
    setApprovedIndices(new Set())
    setOverlayVersion(v => v + 1)
  }

  const handleFinish = async () => {
    const approved = Array.from(approvedIndices)
    onFinish(approved)
  }

  const stats = {
    total: detections.length,
    approved: approvedIndices.size,
    rejected: rejectedIndices.size,
    pending: detections.length - approvedIndices.size - rejectedIndices.size
  }

  // Detecciones de la página actual
  // NOTA: PyMuPDF usa índice base-0 (primera página = 0), PDF.js usa base-1 (primera página = 1)
  const currentPageDetections = detections.filter(d => d.page_num === currentPage - 1)

  // Debug: mostrar todas las detecciones
  console.log('ReviewScreen - Total detecciones:', detections.length)
  console.log('ReviewScreen - Detecciones página', currentPage, ':', currentPageDetections.length)
  console.log('ReviewScreen - Tipos:', currentPageDetections.map(d => `${d.type} (${d.text.substring(0, 20)}...)`))

  return (
    <div className="flex h-screen bg-gradient-to-br from-teal-50 to-cyan-50">
      {/* Sidebar */}
      <div className="w-80 glass border-r border-gray-200/50 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold mb-2">Revisión de Anonimización</h2>
          <div className="text-sm text-gray-600">
            <div className="truncate" title={originalFilePath}>
              {originalFilePath.split('/').pop()}
            </div>
          </div>
        </div>

        {/* Estadísticas */}
        <div className="p-4 bg-gray-50 border-b">
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center justify-between p-2 bg-white rounded">
              <span className="text-gray-600">Total:</span>
              <span className="font-semibold">{stats.total}</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded" style={{ backgroundColor: '#fff5f3' }}>
              <span style={{ color: '#FF6B54' }}>Anonimizar:</span>
              <span className="font-semibold" style={{ color: '#FF6B54' }}>{stats.approved}</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-orange-50 rounded">
              <span className="text-orange-700">Mantener:</span>
              <span className="font-semibold text-orange-700">{stats.rejected}</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-gray-100 rounded">
              <span className="text-gray-600">Pendientes:</span>
              <span className="font-semibold">{stats.pending}</span>
            </div>
          </div>
        </div>

        {/* Acciones rápidas */}
        <div className="p-4 border-b flex gap-2">
          <button
            onClick={handleApproveAll}
            className="flex-1 btn-danger text-sm py-2 scale-on-hover"
          >
            Anonimizar Todas
          </button>
          <button
            onClick={handleRejectAll}
            className="flex-1 px-3 py-2 bg-gradient-to-r from-orange-600 to-orange-700 text-white text-sm rounded hover:from-orange-700 hover:to-orange-800 shadow-md hover:shadow-lg scale-on-hover transition-all duration-200"
          >
            Mantener Todas
          </button>
        </div>

        {/* Lista de detecciones */}
        <div className="flex-1 overflow-y-auto p-4">
          <h3 className="text-sm font-semibold mb-2">
            Detecciones en página {currentPage}:
          </h3>
          <div className="space-y-2">
            {currentPageDetections.length === 0 ? (
              <div className="text-sm text-gray-500 text-center py-4">
                No hay detecciones en esta página
              </div>
            ) : (
              currentPageDetections.map((detection) => {
                const isApproved = approvedIndices.has(detection.index)
                const isRejected = rejectedIndices.has(detection.index)
                const isHovered = hoveredDetectionIndex === detection.index

                return (
                  <div
                    key={detection.index}
                    className={`p-3 rounded-lg border-2 cursor-pointer transition-all duration-200 scale-on-hover ${
                      isHovered ? 'ring-2 ring-teal-400 shadow-lg' : 'shadow-md'
                    } ${
                      isApproved
                        ? 'border-2'
                        : isRejected
                        ? 'bg-amber-50 border-amber-300'
                        : 'bg-white border-gray-300 hover:border-gray-400 hover:shadow-xl'
                    }`}
                    style={isApproved ? { backgroundColor: '#fff5f3', borderColor: '#FF6B54' } : {}}
                    onClick={() => handleDetectionClick(detection.index)}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <span className="text-xs font-semibold text-gray-700">
                        {detection.type}
                      </span>
                      <span className="text-xs text-gray-500">#{detection.index}</span>
                    </div>
                    <div className="text-sm font-mono text-gray-800 truncate">
                      {detection.text}
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-gray-500">
                        Confianza: {(detection.confidence * 100).toFixed(0)}%
                      </span>
                      {isApproved && (
                        <span className="text-xs font-semibold" style={{ color: '#FF6B54' }}>Anonimizar</span>
                      )}
                      {isRejected && (
                        <span className="text-xs font-semibold text-amber-700">Mantener</span>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Botones de acción */}
        <div className="p-4 border-t glass-dark backdrop-blur-lg space-y-2">
          <button
            onClick={handleFinish}
            disabled={approvedIndices.size === 0}
            className="w-full btn-primary focus-ring scale-on-hover"
          >
            Finalizar ({approvedIndices.size} para anonimizar)
          </button>
          <button
            onClick={onCancel}
            className="w-full btn-secondary focus-ring scale-on-hover"
          >
            Cancelar
          </button>
        </div>
      </div>

      {/* Viewer */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="glass border-b border-gray-200/50 shadow-lg p-4 flex items-center justify-between">
          {/* Controles de página */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-3 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed scale-on-hover shadow-md transition-all"
            >
              ← Anterior
            </button>
            <span className="text-sm font-semibold text-gray-700 px-3 py-2 bg-white rounded-lg shadow-md">
              Página {currentPage} de {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed scale-on-hover shadow-md transition-all"
            >
              Siguiente →
            </button>
          </div>

          {/* Modo de selección manual */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsSelectionMode(!isSelectionMode)}
              className={`px-4 py-2 rounded-lg shadow-md scale-on-hover transition-all ${
                isSelectionMode
                  ? 'text-white hover:bg-amber-700 ring-2 ring-amber-300'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
              style={isSelectionMode ? { backgroundColor: '#f59e0b' } : {}}
            >
              {isSelectionMode ? 'Modo Selección' : '+ Añadir Área'}
            </button>
          </div>

          {/* Controles de zoom */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setScale(Math.max(0.5, scale - 0.25))}
              className="px-3 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 scale-on-hover shadow-md"
            >
              -
            </button>
            <span className="text-sm font-semibold text-gray-700 w-16 text-center px-3 py-2 bg-white rounded-lg shadow-md">
              {(scale * 100).toFixed(0)}%
            </span>
            <button
              onClick={() => setScale(Math.min(3, scale + 0.25))}
              className="px-3 py-2 bg-gray-200 rounded-lg hover:bg-gray-300 scale-on-hover shadow-md"
            >
              +
            </button>
            <button
              onClick={handleFitToPage}
              className="px-3 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 text-sm font-medium scale-on-hover shadow-md"
              title="Ajustar página completa al visor"
            >
              Ajustar
            </button>
          </div>
        </div>

        {/* PDF Viewer */}
        <div ref={viewerContainerRef} className="flex-1 overflow-auto bg-gradient-to-br from-gray-100 to-gray-200 p-8">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-6">
              <div className="spinner-rings"></div>
              <div className="flex flex-col items-center gap-2">
                <div className="text-gray-700 text-xl font-semibold text-gradient-shift">
                  Preparando revisión
                </div>
                <div className="text-gray-600 text-base flex items-center gap-1">
                  {loadingStep}
                  <span className="dots-pulse text-teal-600">
                    <span></span>
                    <span></span>
                    <span></span>
                  </span>
                </div>
              </div>
              {/* Skeleton loader para simular interfaz */}
              <div className="mt-8 space-y-3 w-full max-w-md">
                <div className="h-4 skeleton rounded"></div>
                <div className="h-4 skeleton rounded w-3/4"></div>
                <div className="h-4 skeleton rounded w-1/2"></div>
              </div>
            </div>
          ) : (
            <div className="relative inline-block">
              <PDFViewer
                pdfPath={preAnonymizedPath}
                scale={scale}
                pageNumber={currentPage}
                onPageRendered={handlePageRendered}
                onDocumentLoaded={handleDocumentLoaded}
              />
              {/* Overlay de selección manual (detrás de DetectionOverlay) */}
              {isSelectionMode && (
                <SelectionOverlay
                  canvasWidth={canvasWidth}
                  canvasHeight={canvasHeight}
                  pdfPageHeight={pdfPageHeight}
                  pdfPageWidth={pdfPageWidth}
                  pageRotation={pageRotation}
                  scale={scale}
                  onAddManualDetection={handleAddManualDetection}
                />
              )}
              {/* Overlay de detecciones (encima de SelectionOverlay) */}
              <DetectionOverlay
                key={`overlay-v${overlayVersion}-p${currentPage}`}
                detections={enrichedDetections}
                currentPage={currentPage}
                pdfPageHeight={pdfPageHeight}
                pdfPageWidth={pdfPageWidth}
                pageRotation={pageRotation}
                scale={scale}
                canvasWidth={canvasWidth}
                canvasHeight={canvasHeight}
                approvedIndices={approvedIndices}
                rejectedIndices={rejectedIndices}
                onDetectionClick={handleDetectionClick}
                onDetectionHover={setHoveredDetectionIndex}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
