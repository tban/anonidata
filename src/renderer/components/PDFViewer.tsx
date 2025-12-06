import React, { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'

// Configurar worker de PDF.js usando archivo local en lugar de CDN
// Esto es necesario porque Electron bloquea requests externas en producción
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString()

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

        // Convertir path a URL file:// para Electron
        let pdfUrl = pdfPath
        if (!pdfPath.startsWith('http') && !pdfPath.startsWith('file://')) {
          pdfUrl = `file://${pdfPath}`
        }

        console.log('Loading PDF from:', pdfUrl)
        const loadingTask = pdfjsLib.getDocument(pdfUrl)
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
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-600">Cargando PDF...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-600">{error}</div>
      </div>
    )
  }

  return (
    <div className="relative">
      <canvas ref={canvasRef} className="border border-gray-300" />
      {numPages > 1 && (
        <div className="absolute bottom-2 right-2 bg-black bg-opacity-50 text-white px-3 py-1 rounded text-sm">
          Página {pageNumber} de {numPages}
        </div>
      )}
    </div>
  )
}
