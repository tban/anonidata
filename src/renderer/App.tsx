import React, { useState, useCallback } from 'react';
import { ProcessResult } from '../preload/preload';

interface FileItem {
  path: string;
  name: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  result?: any;
}

function App() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  const handleSelectFiles = useCallback(async () => {
    const filePaths = await window.anonidata.dialog.openFile();
    if (filePaths.length > 0) {
      const newFiles: FileItem[] = filePaths.map((filePath) => {
        const fileName = filePath.split('/').pop() || filePath;
        return {
          path: filePath,
          name: fileName,
          size: 0, // No tenemos el tamaño desde el diálogo
          status: 'pending' as const,
          progress: 0,
        };
      });
      setFiles((prev) => [...prev, ...newFiles]);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const pdfFiles = droppedFiles.filter(
      (file) => file.type === 'application/pdf' || file.name.endsWith('.pdf')
    );

    // En Electron con sandbox: false, los File objects tienen la propiedad 'path'
    const newFiles: FileItem[] = pdfFiles.map((file: any) => {
      // Intentar primero acceder directamente a la propiedad path
      let filePath = file.path;

      // Si no existe, intentar con electronWebUtils
      if (!filePath && window.electronWebUtils) {
        try {
          filePath = window.electronWebUtils.getPathForFile(file);
        } catch (error) {
          console.error('Error obteniendo ruta del archivo:', error);
        }
      }

      // Si aún no tenemos ruta, usar el nombre como fallback
      if (!filePath) {
        filePath = file.name;
      }

      return {
        path: filePath,
        name: file.name,
        size: file.size,
        status: 'pending' as const,
        progress: 0,
      };
    });

    if (newFiles.length > 0) {
      setFiles((prev) => [...prev, ...newFiles]);
    }
  }, []);

  const handleProcess = async () => {
    if (files.length === 0) return;

    setIsProcessing(true);
    setProcessResult(null);

    const startTime = Date.now();

    try {
      const filePaths = files.map((f) => f.path);

      // Actualizar estados a "processing"
      setFiles((prev) =>
        prev.map((f) => ({ ...f, status: 'processing' as const, progress: 0 }))
      );

      const result = await window.anonidata.process.anonymize(filePaths);

      const endTime = Date.now();
      const processingTimeSeconds = ((endTime - startTime) / 1000).toFixed(2);

      // Actualizar resultados
      setFiles((prev) =>
        prev.map((f, idx) => {
          const fileResult = result.results[idx];
          return {
            ...f,
            status: fileResult.status === 'success' ? 'completed' : 'error',
            progress: 100,
            result: fileResult,
          };
        })
      );

      setProcessResult(result);

      // Contar archivos exitosos y fallidos
      const successCount = result.results.filter((r) => r.status === 'success').length;
      const errorCount = result.results.filter((r) => r.status === 'error').length;
      const totalFiles = result.results.length;

      // Mostrar mensaje según el resultado
      if (successCount > 0 && errorCount === 0) {
        // Todos los archivos procesados correctamente
        await window.anonidata.dialog.showInfo(
          `PROCESO COMPLETADO\n\n` +
          `✓ Archivos procesados: ${successCount} de ${totalFiles}\n` +
          `⏱ Tiempo de procesamiento: ${processingTimeSeconds} segundos\n\n` +
          `IMPORTANTE: Por favor, revise manualmente los archivos anonimizados para verificar que no queden datos personales sin excluir.\n\n` +
          `Es fundamental verificar que toda la información sensible haya sido correctamente anonimizada.`,
          'Anonimización Completada'
        );
      } else if (successCount > 0 && errorCount > 0) {
        // Algunos archivos fallaron
        const errorMessages = result.results
          .filter((r) => r.status === 'error')
          .map((r) => `• ${r.inputFile.split('/').pop()}: ${r.error || 'Error desconocido'}`)
          .join('\n');

        await window.anonidata.dialog.showInfo(
          `PROCESO COMPLETADO CON ERRORES\n\n` +
          `✓ Archivos exitosos: ${successCount}\n` +
          `✗ Archivos fallidos: ${errorCount}\n` +
          `⏱ Tiempo de procesamiento: ${processingTimeSeconds} segundos\n\n` +
          `ERRORES:\n${errorMessages}\n\n` +
          `Por favor, revise los archivos que se procesaron correctamente.`,
          'Proceso Completado con Errores'
        );
      } else {
        // Todos los archivos fallaron
        const errorMessages = result.results
          .filter((r) => r.status === 'error')
          .map((r) => `• ${r.inputFile.split('/').pop()}: ${r.error || 'Error desconocido'}`)
          .join('\n');

        await window.anonidata.dialog.showInfo(
          `ERROR EN EL PROCESAMIENTO\n\n` +
          `✗ No se pudo procesar ningún archivo\n` +
          `⏱ Tiempo transcurrido: ${processingTimeSeconds} segundos\n\n` +
          `ERRORES:\n${errorMessages}\n\n` +
          `Por favor, verifique los archivos e intente nuevamente.`,
          'Error en Procesamiento'
        );
      }
    } catch (error) {
      console.error('Error procesando archivos:', error);
      setFiles((prev) =>
        prev.map((f) => ({ ...f, status: 'error' as const }))
      );

      // Mostrar error de excepción
      await window.anonidata.dialog.showInfo(
        `ERROR CRÍTICO\n\n` +
        `Ocurrió un error inesperado durante el procesamiento:\n\n` +
        `${error instanceof Error ? error.message : 'Error desconocido'}\n\n` +
        `Por favor, intente nuevamente o contacte soporte técnico.`,
        'Error Crítico'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClear = () => {
    setFiles([]);
    setProcessResult(null);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">AnoniData</h1>
          <p className="text-gray-600">Anonimización de PDFs conforme a RGPD</p>
        </header>

        {/* File Selection Area - Drag & Drop */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-4 border-dashed rounded-lg p-12 mb-6 text-center transition-colors ${
            isDragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 bg-white'
          }`}
        >
          <div className="text-gray-600">
            <svg
              className="mx-auto h-16 w-16 mb-4 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {isDragActive ? (
              <p className="text-lg font-semibold text-blue-600 mb-3">
                Suelta los archivos aquí...
              </p>
            ) : (
              <>
                <p className="text-lg mb-3">
                  Arrastra archivos PDF aquí o
                </p>
                <button
                  onClick={handleSelectFiles}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-lg shadow-md transition-colors mb-3"
                >
                  Seleccionar PDFs
                </button>
              </>
            )}
            <p className="text-sm text-gray-500">
              Procesamiento 100% local - Tus datos nunca salen de tu ordenador
            </p>
          </div>
        </div>

        {/* File List */}
        {files.length > 0 && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-800">
                Archivos ({files.length})
              </h2>
              <button
                onClick={handleClear}
                className="text-sm text-gray-600 hover:text-red-600 transition-colors"
                disabled={isProcessing}
              >
                Limpiar lista
              </button>
            </div>

            <div className="space-y-3">
              {files.map((file, idx) => (
                <div
                  key={idx}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {file.name}
                      </p>
                      <p className="text-xs text-gray-500">{formatBytes(file.size)}</p>
                    </div>
                    <div className="ml-4">
                      {file.status === 'pending' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          Pendiente
                        </span>
                      )}
                      {file.status === 'processing' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          Procesando...
                        </span>
                      )}
                      {file.status === 'completed' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          ✓ Completado
                        </span>
                      )}
                      {file.status === 'error' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                          ✗ Error
                        </span>
                      )}
                    </div>
                  </div>

                  {file.status === 'processing' && (
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${file.progress}%` }}
                      />
                    </div>
                  )}

                  {file.result && file.status === 'completed' && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-600 mb-2">Datos redactados:</p>
                      <div className="grid grid-cols-3 gap-2 text-xs">
                        <div>
                          <span className="font-medium">{file.result.stats.dniCount}</span> DNI/NIE
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.nameCount}</span> Nombres
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.phoneCount}</span> Teléfonos
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.emailCount}</span> Emails
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.signatureCount}</span> Firmas
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.qrCount}</span> QR Codes
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        Guardado en: {file.result.outputFile}
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Process Button */}
        {files.length > 0 && (
          <div className="text-center">
            <button
              onClick={handleProcess}
              disabled={isProcessing || files.every((f) => f.status === 'completed')}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-8 rounded-lg shadow-md transition-colors"
            >
              {isProcessing ? (
                <span className="flex items-center justify-center gap-2">
                  <svg
                    className="animate-spin h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Procesando...
                </span>
              ) : (
                'Anonimizar PDFs'
              )}
            </button>
          </div>
        )}

        {/* Results Summary */}
        {processResult && (
          <div className="mt-8 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Resumen del Procesamiento
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <p className="text-3xl font-bold text-green-600">
                  {processResult.results.filter((r) => r.status === 'success').length}
                </p>
                <p className="text-sm text-gray-600">Archivos exitosos</p>
              </div>
              <div className="text-center p-4 bg-red-50 rounded-lg">
                <p className="text-3xl font-bold text-red-600">
                  {processResult.results.filter((r) => r.status === 'error').length}
                </p>
                <p className="text-sm text-gray-600">Archivos con error</p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-sm text-gray-500">
          <p>
            🔒 Procesamiento 100% local • Sin telemetría • Conforme a RGPD
          </p>
        </footer>
      </div>
    </div>
  );
}

export default App;
