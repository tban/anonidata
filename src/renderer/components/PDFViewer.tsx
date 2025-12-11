import React, { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

// Configurar worker de PDF.js
// El worker está copiado en la carpeta public y Vite lo incluye en el build
// Usar ruta relativa para que funcione en producción con Electron
pdfjsLib.GlobalWorkerOptions.workerSrc = './pdf.worker.min.mjs'

interface PDFViewerProps {
  pdfPath: string
  scale?: number
  pageNumber?: number
  onPageRendered?: (pageInfo: {
    width: number
    height: number
    pageNum: number
    originalWidth: number
    originalHeight: number
  }) => void
  onDocumentLoaded?: (doc: PDFDocumentProxy) => void
}

export const PDFViewer: React.FC<PDFViewerProps> = ({
  pdfPath,
  scale = 1.5,
  pageNumber = 1,
  onPageRendered,
  onDocumentLoaded
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Cargar documento PDF
  useEffect(() => {
    let cancelled = false

    const loadPDF = async () => {
      try {
        setLoading(true)
        setError(null)

        console.log('Loading PDF from:', pdfPath)

        // Leer el archivo usando el handler IPC de Electron
        // Esto es más seguro que fetch() con file:// URLs
        const arrayBuffer = await window.anonidata.utils.readPdfFile(pdfPath)
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer })
        const doc = await loadingTask.promise

        if (!cancelled) {
          setPdfDoc(doc)
          setNumPages(doc.numPages)
          onDocumentLoaded?.(doc)
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Error loading PDF:', err)
          setError('Error al cargar el PDF')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadPDF()

    return () => {
      cancelled = true
      pdfDoc?.destroy()
    }
  }, [pdfPath])

  // Renderizar página
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return

    let cancelled = false

    const renderPage = async () => {
      try {
        const page = await pdfDoc.getPage(pageNumber)

        if (cancelled) return

        const viewport = page.getViewport({ scale })
        const originalViewport = page.getViewport({ scale: 1.0 })
        const canvas = canvasRef.current!
        const context = canvas.getContext('2d')!

        canvas.height = viewport.height
        canvas.width = viewport.width

        const renderContext = {
          canvasContext: context,
          viewport: viewport
        }

        await page.render(renderContext).promise

        if (!cancelled) {
          onPageRendered?.({
            width: viewport.width,
            height: viewport.height,
            pageNum: pageNumber,
            originalWidth: originalViewport.width,
            originalHeight: originalViewport.height
          })
        }
      } catch (err) {
        if (!cancelled) {
          console.error('Error rendering page:', err)
          setError('Error al renderizar la página')
        }
      }
    }

    renderPage()

    return () => {
      cancelled = true
    }
  }, [pdfDoc, pageNumber, scale])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
        <div className="spinner-rings"></div>
        <div className="flex flex-col items-center gap-2">
          <div className="text-gray-700 text-lg font-semibold">Cargando PDF</div>
          <div className="dots-pulse text-blue-600">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="bg-red-50 border-2 border-red-300 rounded-lg p-6 shadow-lg">
          <div className="text-red-700 font-semibold text-lg mb-2">Error al cargar PDF</div>
          <div className="text-red-600">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <canvas ref={canvasRef} className="border-2 border-gray-300 rounded-lg shadow-xl" />
      {numPages > 1 && (
        <div className="absolute bottom-3 right-3 glass-dark text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-lg backdrop-blur-md">
          Página {pageNumber} de {numPages}
        </div>
      )}
    </div>
  )
}
