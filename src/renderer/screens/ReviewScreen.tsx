import React, { useState, useEffect, useCallback } from 'react'
import { anonidata } from '../lib/tauri-bridge'
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
  const [scale, setScale] = useState(1.0)
  const [initialFitApplied, setInitialFitApplied] = useState(false)
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

        const result = await anonidata.review.loadDetections(detectionsPath)

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

  const handleFitToPage = useCallback(() => {
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
  }, [canvasWidth, canvasHeight, scale])

  useEffect(() => {
    if (canvasWidth && canvasHeight && !initialFitApplied && viewerContainerRef.current) {
      handleFitToPage()
      setInitialFitApplied(true)
    }
  }, [canvasWidth, canvasHeight, initialFitApplied, handleFitToPage])

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
      await anonidata.review.saveDetections(detectionsPath, updatedDetections)
      console.log('Nueva detección manual guardada:', newDetection)
    } catch (error) {
      console.error('Error guardando detección manual:', error)
    }
  }

  const handleDetectionClick = (index: number) => {
    // Toggle binario: Solo Anonimizar (Aprobado) o Mantener (Rechazado)
    if (approvedIndices.has(index)) {
      // De Aprobado a Rechazado (Mantener) - Color Naranja
      const newApproved = new Set(approvedIndices)
      newApproved.delete(index)
      setApprovedIndices(newApproved)

      const newRejected = new Set(rejectedIndices)
      newRejected.add(index)
      setRejectedIndices(newRejected)
    } else {
      // De Rechazado (o cualquier otro) a Aprobado (Anonimizar) - Color Rojo Cruzado
      const newRejected = new Set(rejectedIndices)
      newRejected.delete(index)
      setRejectedIndices(newRejected)

      const newApproved = new Set(approvedIndices)
      newApproved.add(index)
      setApprovedIndices(newApproved)
    }

    setOverlayVersion(v => v + 1)
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
    rejected: rejectedIndices.size
  }

  // Detecciones de la página actual
  // NOTA: PyMuPDF usa índice base-0 (primera página = 0), PDF.js usa base-1 (primera página = 1)
  const currentPageDetections = detections.filter(d => d.page_num === currentPage - 1)

  // Debug: mostrar todas las detecciones
  console.log('ReviewScreen - Total detecciones:', detections.length)
  console.log('ReviewScreen - Detecciones página', currentPage, ':', currentPageDetections.length)
  console.log('ReviewScreen - Tipos:', currentPageDetections.map(d => `${d.type} (${d.text.substring(0, 20)}...)`))

  return (
    <div className="flex h-screen bg-stone-950 text-stone-100 selection:bg-teal-500/30">
      {/* Sidebar */}
      <div className="w-80 glass border-r border-stone-800/80 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-stone-800">
          <h2 className="text-lg font-semibold mb-2">Revisión de Anonimización</h2>
          <div className="text-sm text-stone-400">
            <div className="truncate" title={originalFilePath}>
              {originalFilePath.split('/').pop()}
            </div>
          </div>
        </div>

        {/* Estadísticas */}
        <div className="p-4 bg-stone-900/60 border-b border-stone-800">
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center justify-between p-2 bg-stone-950/60 border border-stone-800 rounded col-span-2">
              <span className="text-stone-400">Total Detecciones:</span>
              <span className="font-semibold text-stone-200">{stats.total}</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-red-950/20 border border-red-900/30 rounded">
              <span className="text-red-400">Anonimizar:</span>
              <span className="font-semibold text-red-400">{stats.approved}</span>
            </div>
            <div className="flex items-center justify-between p-2 bg-amber-950/20 border border-amber-900/30 rounded">
              <span className="text-amber-400">Mantener:</span>
              <span className="font-semibold text-amber-400">{stats.rejected}</span>
            </div>
          </div>
        </div>

        {/* Acciones rápidas */}
        <div className="p-4 border-b border-stone-800 flex gap-2">
          <button
            onClick={handleApproveAll}
            className="flex-1 btn-danger text-sm py-2 scale-on-hover"
          >
            Anonimizar Todas
          </button>
          <button
            onClick={handleRejectAll}
            className="flex-1 px-3 py-2 bg-gradient-to-r from-amber-600 to-amber-700 text-white text-sm rounded hover:from-amber-750 hover:to-amber-850 shadow-md hover:shadow-lg scale-on-hover transition-all duration-200 border border-amber-600/20"
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
              <div className="text-sm text-stone-500 text-center py-4">
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
                    className={`p-3 rounded-lg border-2 cursor-pointer transition-all duration-200 scale-on-hover ${isHovered ? 'ring-2 ring-teal-500 shadow-lg' : 'shadow-md'
                      } ${isApproved
                        ? 'bg-red-950/20 border-red-500 shadow-red-500/10'
                        : isRejected
                          ? 'bg-amber-950/20 border-amber-850'
                          : 'bg-stone-900/40 border-stone-800 hover:border-stone-700 hover:shadow-xl'
                      }`}
                    onClick={() => handleDetectionClick(detection.index)}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <span className="text-xs font-semibold text-stone-300">
                        {detection.type}
                      </span>
                      <span className="text-xs text-stone-500">#{detection.index}</span>
                    </div>
                    <div className="text-sm font-mono text-stone-200 truncate">
                      {detection.text}
                    </div>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-stone-500">
                        Confianza: {(detection.confidence * 100).toFixed(0)}%
                      </span>
                      {isApproved && (
                        <span className="text-xs font-semibold text-red-400">Anonimizar</span>
                      )}
                      {isRejected && (
                        <span className="text-xs font-semibold text-amber-400">Mantener</span>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Botones de acción */}
        <div className="p-4 border-t border-stone-800 glass-dark backdrop-blur-lg space-y-2">
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
        <div className="glass border-b border-stone-850 shadow-lg p-2.5 sm:p-4 flex flex-wrap items-center justify-between gap-3">
          {/* Controles de página */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            <button
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-2.5 py-1.5 sm:px-3 sm:py-2 bg-stone-800 text-stone-250 border border-stone-700/50 rounded-lg hover:bg-stone-700 disabled:bg-stone-900 disabled:text-stone-600 disabled:border-stone-900 disabled:cursor-not-allowed scale-on-hover shadow-md transition-all text-sm"
            >
              ← <span className="hidden sm:inline">Anterior</span>
            </button>
            <span className="text-xs sm:text-sm font-semibold text-stone-300 px-2 py-1.5 sm:px-3 sm:py-2 bg-stone-900/80 border border-stone-800 rounded-lg shadow-md min-w-[5.5rem] sm:min-w-0 text-center">
              <span className="hidden sm:inline">Página {currentPage} de {totalPages}</span>
              <span className="inline sm:hidden">Pág. {currentPage}/{totalPages}</span>
            </span>
            <button
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="px-2.5 py-1.5 sm:px-3 sm:py-2 bg-stone-800 text-stone-250 border border-stone-700/50 rounded-lg hover:bg-stone-700 disabled:bg-stone-900 disabled:text-stone-600 disabled:border-stone-900 disabled:cursor-not-allowed scale-on-hover shadow-md transition-all text-sm"
            >
              <span className="hidden sm:inline">Siguiente</span> →
            </button>
          </div>

          {/* Modo de selección manual */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsSelectionMode(!isSelectionMode)}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-lg shadow-md scale-on-hover transition-all text-sm ${isSelectionMode
                ? 'text-white hover:bg-amber-600 ring-2 ring-amber-900/60'
                : 'bg-stone-800 text-stone-250 hover:bg-stone-700 border border-stone-700/50'
                }`}
              style={isSelectionMode ? { backgroundColor: '#d97706' } : {}}
            >
              {isSelectionMode ? (
                <>
                  <span className="hidden sm:inline">Modo Selección</span>
                  <span className="inline sm:hidden">Selección</span>
                </>
              ) : (
                <>
                  <span className="hidden sm:inline">+ Añadir Área</span>
                  <span className="inline sm:hidden">+ Área</span>
                </>
              )}
            </button>
          </div>

          {/* Controles de zoom */}
          <div className="flex items-center gap-1.5 sm:gap-2">
            <button
              onClick={() => setScale(Math.max(0.5, scale - 0.25))}
              className="px-2.5 py-1.5 sm:px-3 sm:py-2 bg-stone-800 text-stone-250 border border-stone-700/50 rounded-lg hover:bg-stone-700 scale-on-hover shadow-md text-sm font-semibold"
            >
              -
            </button>
            <span className="text-xs sm:text-sm font-semibold text-stone-300 w-12 sm:w-16 text-center px-2 py-1.5 sm:px-3 sm:py-2 bg-stone-900/80 border border-stone-800 rounded-lg shadow-md">
              {(scale * 100).toFixed(0)}%
            </span>
            <button
              onClick={() => setScale(Math.min(3, scale + 0.25))}
              className="px-2.5 py-1.5 sm:px-3 sm:py-2 bg-stone-800 text-stone-250 border border-stone-700/50 rounded-lg hover:bg-stone-700 scale-on-hover shadow-md text-sm font-semibold"
            >
              +
            </button>
            <button
              onClick={handleFitToPage}
              className="px-2.5 py-1.5 sm:px-3 sm:py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-500 text-xs sm:text-sm font-medium scale-on-hover shadow-md"
              title="Ajustar página completa al visor"
            >
              Ajustar
            </button>
          </div>
        </div>

        {/* PDF Viewer */}
        <div ref={viewerContainerRef} className="flex-1 overflow-auto bg-stone-950/85 border-t border-stone-900 p-8">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-6">
              <div className="spinner-rings"></div>
              <div className="flex flex-col items-center gap-2">
                <div className="text-stone-300 text-xl font-semibold text-gradient-shift">
                  Preparando revisión
                </div>
                <div className="text-stone-400 text-base flex items-center gap-1">
                  {loadingStep}
                  <span className="dots-pulse text-teal-400">
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
