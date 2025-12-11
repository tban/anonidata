import React, { useState, useCallback } from 'react';
import { ProcessResult } from '../preload/preload';
import { ReviewScreen } from './screens/ReviewScreen';
import { UpdateNotification } from './components/UpdateNotification';
import logoImage from './assets/logo.png';

interface FileItem {
  path: string;
  name: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  result?: any;
}

interface ReviewState {
  originalFilePath: string;
  preAnonymizedPath: string;
  detectionsPath: string;
}

function App() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [showCompletionModal, setShowCompletionModal] = useState(false);
  const [showAboutModal, setShowAboutModal] = useState(false);
  const [reviewState, setReviewState] = useState<ReviewState | null>(null);
  const [isDetecting, setIsDetecting] = useState<number | null>(null);
  const [processingStep, setProcessingStep] = useState<string>('');
  const [completionData, setCompletionData] = useState<{
    type: 'success' | 'partial' | 'error' | 'critical';
    successCount: number;
    errorCount: number;
    totalFiles: number;
    processingTime: string;
    errors?: Array<{ file: string; error: string }>;
    warnings?: Array<{ file: string; warnings: string[] }>;
    message?: string;
  } | null>(null);

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

      // Simular pasos de procesamiento para mejor UX
      const steps = [
        'Analizando documentos...',
        'Detectando datos personales...',
        'Procesando anonimizaciones...',
        'Generando PDFs finales...'
      ];

      let stepIndex = 0;
      const stepInterval = setInterval(() => {
        if (stepIndex < steps.length) {
          setProcessingStep(steps[stepIndex]);
          stepIndex++;
        }
      }, 1500);

      const result = await window.anonidata.process.anonymize(filePaths);

      clearInterval(stepInterval);
      setProcessingStep('');

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

      // Extraer warnings de archivos exitosos
      const fileWarnings = result.results
        .filter((r) => r.status === 'success' && r.warnings && r.warnings.length > 0)
        .map((r) => ({
          file: r.inputFile.split('/').pop() || r.inputFile,
          warnings: r.warnings
        }));

      // Preparar datos para el modal según el resultado
      if (successCount > 0 && errorCount === 0) {
        // Todos los archivos procesados correctamente
        setCompletionData({
          type: 'success',
          successCount,
          errorCount,
          totalFiles,
          processingTime: processingTimeSeconds,
          warnings: fileWarnings.length > 0 ? fileWarnings : undefined,
        });
      } else if (successCount > 0 && errorCount > 0) {
        // Algunos archivos fallaron
        const errors = result.results
          .filter((r) => r.status === 'error')
          .map((r) => ({
            file: r.inputFile.split('/').pop() || r.inputFile,
            error: r.error || 'Error desconocido'
          }));

        setCompletionData({
          type: 'partial',
          successCount,
          errorCount,
          totalFiles,
          processingTime: processingTimeSeconds,
          errors,
          warnings: fileWarnings.length > 0 ? fileWarnings : undefined,
        });
      } else {
        // Todos los archivos fallaron
        const errors = result.results
          .filter((r) => r.status === 'error')
          .map((r) => ({
            file: r.inputFile.split('/').pop() || r.inputFile,
            error: r.error || 'Error desconocido'
          }));

        setCompletionData({
          type: 'error',
          successCount,
          errorCount,
          totalFiles,
          processingTime: processingTimeSeconds,
          errors,
        });
      }
      setShowCompletionModal(true);
    } catch (error) {
      console.error('Error procesando archivos:', error);
      setFiles((prev) =>
        prev.map((f) => ({ ...f, status: 'error' as const }))
      );

      // Mostrar error crítico en modal
      setCompletionData({
        type: 'critical',
        successCount: 0,
        errorCount: files.length,
        totalFiles: files.length,
        processingTime: '0',
        message: error instanceof Error ? error.message : 'Error desconocido',
      });
      setShowCompletionModal(true);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClear = () => {
    setFiles([]);
    setProcessResult(null);
  };

  const handleStartReview = async (fileIndex: number) => {
    const file = files[fileIndex];
    setIsDetecting(fileIndex);

    try {
      const result = await window.anonidata.process.detectOnly(file.path);

      if (result.success && result.preAnonymizedPath && result.detectionsPath) {
        setReviewState({
          originalFilePath: file.path,
          preAnonymizedPath: result.preAnonymizedPath,
          detectionsPath: result.detectionsPath,
        });
      } else {
        console.error('Error iniciando revisión:', result.error);
        await window.anonidata.dialog.showInfo(
          `Error al iniciar la revisión: ${result.error}`,
          'Error'
        );
      }
    } catch (error) {
      console.error('Error iniciando revisión:', error);
      await window.anonidata.dialog.showInfo(
        `Error al iniciar la revisión: ${error}`,
        'Error'
      );
    } finally {
      setIsDetecting(null);
    }
  };

  const handleFinishReview = async (approvedIndices: number[]) => {
    if (!reviewState) return;

    try {
      const result = await window.anonidata.process.finalizeAnonymization(
        reviewState.originalFilePath,
        reviewState.detectionsPath,
        approvedIndices
      );

      if (result.success) {
        // Cerrar vista de revisión primero
        setReviewState(null);

        // Mostrar modal de completación igual que el proceso automático
        setCompletionData({
          type: 'success',
          successCount: 1,
          errorCount: 0,
          totalFiles: 1,
          processingTime: '0',
          warnings: result.warnings && result.warnings.length > 0 ? [{
            file: reviewState.originalFilePath.split('/').pop() || reviewState.originalFilePath,
            warnings: result.warnings
          }] : undefined,
        });
        setShowCompletionModal(true);
      } else {
        // Cerrar vista de revisión
        setReviewState(null);

        // Mostrar error en modal
        setCompletionData({
          type: 'error',
          successCount: 0,
          errorCount: 1,
          totalFiles: 1,
          processingTime: '0',
          errors: [{
            file: reviewState.originalFilePath.split('/').pop() || reviewState.originalFilePath,
            error: result.error || 'Error desconocido'
          }],
        });
        setShowCompletionModal(true);
      }
    } catch (error) {
      console.error('Error finalizando anonimización:', error);

      // Cerrar vista de revisión
      if (reviewState) {
        setReviewState(null);

        // Mostrar error crítico en modal
        setCompletionData({
          type: 'critical',
          successCount: 0,
          errorCount: 1,
          totalFiles: 1,
          processingTime: '0',
          message: error instanceof Error ? error.message : 'Error desconocido',
        });
        setShowCompletionModal(true);
      }
    }
  };

  const handleCancelReview = async () => {
    if (reviewState) {
      // Eliminar archivos temporales generados para la revisión
      try {
        const deleteDetections = window.anonidata.utils.deleteFile(reviewState.detectionsPath);
        const deletePreAnonymized = window.anonidata.utils.deleteFile(reviewState.preAnonymizedPath);

        const [detectionsDeleted, preAnonymizedDeleted] = await Promise.all([
          deleteDetections,
          deletePreAnonymized
        ]);

        if (!detectionsDeleted) {
          console.warn(`No se pudo eliminar el archivo de detecciones: ${reviewState.detectionsPath}`);
        }
        if (!preAnonymizedDeleted) {
          console.warn(`No se pudo eliminar el PDF temporal: ${reviewState.preAnonymizedPath}`);
        }

        console.log('Archivos temporales eliminados exitosamente');
      } catch (error) {
        console.error('Error al eliminar archivos temporales:', error);
      }
    }

    setReviewState(null);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Si estamos en modo revisión, mostrar ReviewScreen
  if (reviewState) {
    return (
      <ReviewScreen
        originalFilePath={reviewState.originalFilePath}
        preAnonymizedPath={reviewState.preAnonymizedPath}
        detectionsPath={reviewState.detectionsPath}
        onFinish={handleFinishReview}
        onCancel={handleCancelReview}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 to-cyan-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <header className="relative text-center mb-8">
          <button
            onClick={() => setShowAboutModal(true)}
            className="absolute right-0 top-0 w-10 h-10 flex items-center justify-center hover:scale-110 transition-transform duration-200 rounded-lg hover:shadow-lg"
            title="Acerca de AnoniData"
          >
            <img
              src={logoImage}
              alt="AnoniData Logo"
              className="w-8 h-8 object-contain"
            />
          </button>
          <h1 className="text-4xl font-bold text-gray-800 mb-2">AnoniData</h1>
          <p className="text-gray-600">
            Anonimización de PDFs conforme a RGPD by{' '}
            <button
              onClick={() => window.anonidata.utils.openExternal('https://x.com/TbanR')}
              className="text-teal-600 hover:text-teal-700 hover:underline transition-colors cursor-pointer"
            >
              @TbanR
            </button>
          </p>
        </header>

        {/* File Selection Area - Drag & Drop */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-4 border-dashed rounded-2xl p-12 mb-6 text-center transition-all duration-300 ${
            isDragActive
              ? 'border-teal-500 glass scale-105 shadow-2xl'
              : 'border-gray-300 bg-white shadow-md hover:shadow-lg'
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
              <p className="text-lg font-semibold text-teal-600 mb-3">
                Suelta los archivos aquí...
              </p>
            ) : (
              <>
                <p className="text-lg mb-3">
                  Arrastra archivos PDF aquí o
                </p>
                <button
                  onClick={handleSelectFiles}
                  className="btn-primary btn-ripple mb-3 animate-fade-in-up"
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

        {/* Process Button - Always visible above the list */}
        {files.length > 0 && (
          <div className="text-center mb-6">
            <button
              onClick={handleProcess}
              disabled={isProcessing || files.every((f) => f.status === 'completed')}
              className="btn-primary btn-ripple scale-on-hover"
            >
              {isProcessing ? (
                <span className="flex items-center justify-center gap-3">
                  <div className="spinner-rings"></div>
                  <div className="flex flex-col items-start">
                    <span className="text-gradient-shift font-bold">Procesando archivos</span>
                    {processingStep && (
                      <span className="text-sm text-teal-100 flex items-center gap-1">
                        {processingStep}
                        <span className="dots-pulse text-teal-200">
                          <span></span>
                          <span></span>
                          <span></span>
                        </span>
                      </span>
                    )}
                  </div>
                </span>
              ) : (
                'Anonimizar PDFs'
              )}
            </button>
          </div>
        )}

        {/* File List */}
        {files.length > 0 && (
          <div className="glass rounded-2xl shadow-xl p-6 mb-6 border border-gray-200/50">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-800">
                Archivos ({files.length})
              </h2>
              <button
                onClick={handleClear}
                className="text-sm text-gray-600 hover:text-red-600 transition-all scale-on-hover font-medium"
                disabled={isProcessing}
              >
                Limpiar lista
              </button>
            </div>

            <div className="space-y-3">
              {files.map((file, idx) => (
                <div
                  key={idx}
                  className={`list-item border-2 rounded-xl p-4 transition-all duration-300 ${
                    file.status === 'processing'
                      ? 'border-teal-400 bg-teal-50 shadow-xl ring-2 ring-teal-200 scale-[1.02]'
                      : 'border-gray-200 hover:border-teal-300 shadow-md hover:shadow-xl card-hover bg-white'
                  }`}
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
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-teal-100 text-teal-800">
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
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-xs text-gray-600">
                        <span className="flex items-center gap-2">
                          <div className="spinner-modern" style={{width: '12px', height: '12px', borderWidth: '2px'}}></div>
                          <span className="font-medium flex items-center gap-1">
                            {processingStep || 'Procesando documento'}
                            <span className="dots-pulse text-teal-600">
                              <span></span>
                              <span></span>
                              <span></span>
                            </span>
                          </span>
                        </span>
                        <span className="font-semibold">{file.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden shadow-inner">
                        <div
                          className="bg-gradient-to-r from-teal-500 via-cyan-500 to-teal-500 h-2.5 rounded-full transition-all duration-500 progress-wave"
                          style={{
                            width: `${file.progress || 50}%`,
                            backgroundSize: '200% 100%'
                          }}
                        />
                      </div>
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
                          <span className="font-medium">{file.result.stats.addressCount}</span> Direcciones
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

                  {file.status === 'pending' && (
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={() => handleStartReview(idx)}
                        disabled={isDetecting === idx}
                        className="px-3 py-1.5 bg-teal-600 text-white text-xs rounded hover:bg-teal-700 scale-on-hover disabled:bg-gray-400 disabled:cursor-not-allowed disabled:scale-100 transition-all duration-200 shadow-md hover:shadow-lg"
                      >
                        {isDetecting === idx ? (
                          <span className="flex items-center justify-center gap-2">
                            <div className="spinner-modern" style={{width: '14px', height: '14px', borderWidth: '2px'}}></div>
                            <span className="flex items-center gap-1">
                              Detectando PII
                              <span className="dots-pulse text-teal-200">
                                <span></span>
                                <span></span>
                                <span></span>
                              </span>
                            </span>
                          </span>
                        ) : (
                          'Revisión manual'
                        )}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results Summary */}
        {processResult && (
          <div className="mt-8 glass rounded-2xl shadow-xl p-6 border border-gray-200/50">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Resumen del Procesamiento
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-6 bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl shadow-md border border-green-200">
                <p className="text-4xl font-bold text-green-600 mb-1">
                  {processResult.results.filter((r) => r.status === 'success').length}
                </p>
                <p className="text-sm text-gray-600 font-medium">Archivos exitosos</p>
              </div>
              <div className="text-center p-6 bg-gradient-to-br from-red-50 to-rose-50 rounded-xl shadow-md border border-red-200">
                <p className="text-4xl font-bold text-red-600 mb-1">
                  {processResult.results.filter((r) => r.status === 'error').length}
                </p>
                <p className="text-sm text-gray-600 font-medium">Archivos con error</p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-sm text-gray-500">
          <p>
            Procesamiento 100% local - Sin telemetría - Conforme a RGPD
          </p>
          <p className="mt-2 text-xs">
            v{__APP_VERSION__} · by{' '}
            <button
              onClick={() => window.anonidata.utils.openExternal('https://x.com/TbanR')}
              className="text-teal-600 hover:text-teal-700 hover:underline transition-colors cursor-pointer"
            >
              @TbanR
            </button>
          </p>
        </footer>
      </div>

      {/* Modal de Completación */}
      {showCompletionModal && completionData && (
        <div className="modal-backdrop backdrop-blur-strong p-4">
          <div className="modal-content glass rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border-2 border-white/20">
            {/* Header */}
            <div className={`p-8 rounded-t-2xl ${
              completionData.type === 'success' ? 'bg-gradient-to-r from-green-500 to-green-600' :
              completionData.type === 'partial' ? 'bg-gradient-to-r from-yellow-500 to-orange-500' :
              'bg-gradient-to-r from-red-500 to-red-600'
            }`}>
              <div className="flex items-center justify-between text-white">
                <h2 className="text-3xl font-bold">
                  {completionData.type === 'success' && 'Proceso Completado'}
                  {completionData.type === 'partial' && 'Completado con Errores'}
                  {(completionData.type === 'error' || completionData.type === 'critical') && 'Error en el Procesamiento'}
                </h2>
              </div>
            </div>

            {/* Body */}
            <div className="p-8">
              {/* Estadísticas */}
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="text-center p-6 bg-gray-50 rounded-xl">
                  <div className="text-4xl font-bold text-gray-800 mb-2">
                    {completionData.totalFiles}
                  </div>
                  <div className="text-sm text-gray-600">Total de archivos</div>
                </div>
                <div className="text-center p-6 bg-green-50 rounded-xl">
                  <div className="text-4xl font-bold text-green-600 mb-2">
                    {completionData.successCount}
                  </div>
                  <div className="text-sm text-gray-600">Procesados</div>
                </div>
                <div className="text-center p-6 bg-gray-50 rounded-xl">
                  <div className="text-4xl font-bold text-gray-800 mb-2">
                    {completionData.processingTime}s
                  </div>
                  <div className="text-sm text-gray-600">Tiempo total</div>
                </div>
              </div>

              {/* Mensaje de Éxito */}
              {completionData.type === 'success' && (
                <div className="bg-teal-50 border-l-4 border-teal-500 p-6 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold text-teal-900 mb-3">
                    Revisión Manual Requerida
                  </h3>
                  <p className="text-teal-800 leading-relaxed">
                    Por favor, <strong>revise manualmente</strong> los archivos anonimizados para verificar que no queden datos personales sin excluir.
                  </p>
                  <p className="text-teal-800 leading-relaxed mt-2">
                    Es fundamental verificar que toda la información sensible haya sido correctamente anonimizada.
                  </p>
                </div>
              )}

              {/* Lista de Advertencias */}
              {completionData.warnings && completionData.warnings.length > 0 && (
                <div className="bg-amber-50 border-l-4 border-amber-500 p-6 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold text-amber-900 mb-4">
                    Advertencias ({completionData.warnings.length})
                  </h3>
                  <div className="space-y-3 max-h-60 overflow-y-auto">
                    {completionData.warnings.map((warn, idx) => (
                      <div key={idx} className="bg-white p-4 rounded-lg shadow-sm">
                        <div className="font-medium text-amber-900 mb-2">{warn.file}</div>
                        <div className="space-y-1">
                          {warn.warnings.map((warning, widx) => (
                            <div key={widx} className="text-sm text-amber-700">{warning}</div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Lista de Errores */}
              {completionData.errors && completionData.errors.length > 0 && (
                <div className="border-l-4 p-6 rounded-lg mb-6" style={{ backgroundColor: '#fff5f3', borderColor: '#FF6B54' }}>
                  <h3 className="text-lg font-semibold mb-4" style={{ color: '#ba3821' }}>
                    Errores Encontrados ({completionData.errorCount})
                  </h3>
                  <div className="space-y-3 max-h-60 overflow-y-auto">
                    {completionData.errors.map((err, idx) => (
                      <div key={idx} className="bg-white p-4 rounded-lg shadow-sm">
                        <div className="font-medium mb-1" style={{ color: '#ba3821' }}>{err.file}</div>
                        <div className="text-sm" style={{ color: '#d14932' }}>{err.error}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Mensaje Crítico */}
              {completionData.type === 'critical' && completionData.message && (
                <div className="border-l-4 p-6 rounded-lg mb-6" style={{ backgroundColor: '#fff5f3', borderColor: '#FF6B54' }}>
                  <h3 className="text-lg font-semibold mb-3" style={{ color: '#ba3821' }}>
                    Error Crítico
                  </h3>
                  <p className="leading-relaxed mb-3" style={{ color: '#d14932' }}>
                    Ocurrió un error inesperado durante el procesamiento:
                  </p>
                  <code className="block p-4 rounded text-sm" style={{ backgroundColor: '#ffe8e3', color: '#ba3821' }}>
                    {completionData.message}
                  </code>
                  <p className="leading-relaxed mt-3" style={{ color: '#d14932' }}>
                    Por favor, intente nuevamente o contacte soporte técnico.
                  </p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-8 pb-8">
              <button
                onClick={() => setShowCompletionModal(false)}
                className="w-full bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white font-semibold py-4 px-6 rounded-xl shadow-lg transition-all transform hover:scale-[1.02]"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal About AnoniData */}
      {showAboutModal && (
        <div className="modal-backdrop backdrop-blur-strong p-4">
          <div className="modal-content glass rounded-2xl shadow-2xl max-w-lg w-full border-2 border-white/20">
            {/* Header */}
            <div className="p-8 rounded-t-2xl bg-gradient-to-r from-teal-600 to-cyan-600">
              <div className="text-white text-center">
                <div className="flex justify-center mb-4">
                  <img
                    src={logoImage}
                    alt="AnoniData Logo"
                    className="w-20 h-20 object-contain"
                  />
                </div>
                <h2 className="text-3xl font-bold mb-2">AnoniData</h2>
                <p className="text-teal-100">Anonimización de PDFs conforme a RGPD</p>
              </div>
            </div>

            {/* Body */}
            <div className="p-8">
              <div className="space-y-6">
                {/* Versión */}
                <div className="text-center">
                  <p className="text-sm text-gray-500 mb-1">Versión</p>
                  <p className="text-2xl font-bold text-gray-800">{__APP_VERSION__}</p>
                </div>

                {/* Fecha de compilación */}
                <div className="text-center">
                  <p className="text-sm text-gray-500 mb-1">Fecha de compilación</p>
                  <p className="text-lg text-gray-700">{__BUILD_DATE__}</p>
                </div>

                {/* Contacto */}
                <div className="pt-6 border-t border-gray-200">
                  <div className="text-center">
                    <p className="text-sm text-gray-500 mb-3">Contacto</p>
                    <button
                      onClick={() => window.anonidata.utils.openExternal('https://x.com/TbanR')}
                      className="inline-flex items-center gap-2 text-teal-600 hover:text-teal-700 font-medium transition-colors cursor-pointer"
                    >
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                      </svg>
                      @TbanR
                    </button>
                  </div>
                </div>

                {/* Características */}
                <div className="pt-6 border-t border-gray-200">
                  <div className="grid grid-cols-1 gap-3 text-sm text-gray-600">
                    <div className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span>Procesamiento 100% local</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span>Sin telemetría ni conexión a internet</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span>Conforme al Reglamento General de Protección de Datos (RGPD)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span>Detección avanzada con IA (spaCy NER)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-8 pb-8">
              <button
                onClick={() => setShowAboutModal(false)}
                className="w-full bg-gradient-to-r from-teal-600 to-teal-700 hover:from-teal-700 hover:to-teal-800 text-white font-semibold py-3 px-6 rounded-xl shadow-lg transition-all transform hover:scale-[1.02]"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Componente de actualización automática */}
      <UpdateNotification />
    </div>
  );
}

export default App;
