import React, { useState, useCallback, useEffect } from 'react';
import { ProcessResult } from '../preload/preload';
import { ReviewScreen } from './screens/ReviewScreen';
import { UpdateNotification } from './components/UpdateNotification';
import logoImage from './assets/logo.png';
import { anonidata, listen } from './lib/tauri-bridge';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { ask } from '@tauri-apps/plugin-dialog';
import { SettingsModal, AppSettings } from './components/SettingsModal';

interface FileItem {
  path: string;
  name: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'error' | 'ocr_processing';
  progress: number;
  result?: any;
  pdfType?: 'text' | 'image' | 'text_ocr' | 'detecting';
  ocrOption?: 'yes' | 'no';
  step?: string;
  pages?: number;
}

interface ReviewState {
  originalFilePath: string;
  preAnonymizedPath: string;
  detectionsPath: string;
  pdfType: 'text' | 'image' | 'text_ocr' | 'detecting';
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
  const [ocrPromptFiles, setOcrPromptFiles] = useState<string[]>([]);
  const [bulkOcrDecision, setBulkOcrDecision] = useState<'yes' | 'no' | null>(null);
  const [redactionStrategy, setRedactionStrategy] = useState<'black_box' | 'text_label'>('black_box');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const bulkOcrDecisionRef = React.useRef<'yes' | 'no' | null>(null);

  const reviewStateRef = React.useRef<ReviewState | null>(null);
  const filesRef = React.useRef<FileItem[]>([]);
  const handleCancelReviewRef = React.useRef<() => Promise<void>>();
  const autoReviewedFilesRef = React.useRef<Set<string>>(new Set());
  const processedPathsRef = React.useRef<Set<string>>(new Set());

  useEffect(() => {
    bulkOcrDecisionRef.current = bulkOcrDecision;
  }, [bulkOcrDecision]);

  useEffect(() => {
    reviewStateRef.current = reviewState;
  }, [reviewState]);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

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

  // Listener para el menú de la aplicación
  useEffect(() => {
    const unlistenAbout = listen('show-about-modal', () => {
      setShowAboutModal(true);
    });

    const unlistenUpdates = listen('check-updates', () => {
      console.log('App: check-updates menu event received');
      window.dispatchEvent(new CustomEvent('trigger-check-updates'));
    });

    return () => {
      unlistenAbout.then((fn) => fn());
      unlistenUpdates.then((fn) => fn());
    };
  }, []);

  // Cargar configuración de usuario al iniciar
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const storedSettings = await anonidata.store.get('app_settings') as AppSettings | null;
        if (storedSettings?.defaultRedactionStrategy) {
          setRedactionStrategy(storedSettings.defaultRedactionStrategy);
        }
      } catch (e) {
        console.error('Error loading initial settings:', e);
      }
    };
    loadSettings();
  }, []);

  // Listener para recibir actualizaciones de progreso en tiempo real del backend
  useEffect(() => {
    interface ProgressPayload {
      status: string;
      file: string;
      progress: number;
      step: string;
    }

    const unlisten = listen<ProgressPayload>('backend-progress', (event) => {
      const payload = event.payload;
      if (payload && payload.file) {
        setFiles((prev) =>
          prev.map((f) => {
            if (f.path === payload.file) {
              return {
                ...f,
                progress: payload.progress,
                step: payload.step,
              };
            }
            return f;
          })
        );
      }
    });

    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  // Función para detectar si un PDF es de texto o imagen usando el backend para consistencia
  const detectPdfType = useCallback(
    async (filePath: string): Promise<{ type: 'text' | 'image'; pages?: number }> => {
      try {
        // Usar directamente el backend (PyMuPDF) que tiene el mismo criterio que el proceso de anonimización
        const result = await anonidata.utils.checkPdfType(filePath);
        if (result) {
          // Por robustez, soportar si es un objeto (Tauri / Electron actualizado) o si es directamente el string (Electron anterior)
          const type = typeof result === 'string' ? result : result.type;
          const pages = typeof result === 'string' ? undefined : result.pages;
          if (type === 'image' || type === 'text') {
            return {
              type: type as 'image' | 'text',
              pages: pages,
            };
          }
        }
        return { type: 'text' };
      } catch (error) {
        console.error('Error detectando tipo PDF con backend:', error);
        // Fallback seguro a text para permitir intento de procesado
        return { type: 'text' };
      }
    },
    []
  );

  const processSingleOcrDecision = useCallback(async (filePath: string, decision: 'yes' | 'no') => {
    if (decision === 'yes') {
      // Poner el archivo en estado de procesamiento OCR
      setFiles((prev) =>
        prev.map((f) => (f.path === filePath ? { ...f, status: 'ocr_processing' } : f))
      );

      try {
        // Ejecutar OCR en español en el backend
        const result = await anonidata.utils.applyOcr(filePath, 'spa');

        if (result.success && result.ocrPdfPath) {
          // Obtener el nuevo tamaño
          let size = 0;
          try {
            size = await anonidata.utils.getFileSize(result.ocrPdfPath);
          } catch (e) {
            console.error('Error getting size for OCR PDF:', e);
          }

          const ocrFileName = result.ocrPdfPath.split(/[/\\]/).pop() || result.ocrPdfPath;

          // Reemplazar la entrada original por el nuevo PDF de texto convertido
          setFiles((prev) =>
            prev.map((f) =>
              f.path === filePath
                ? {
                    ...f,
                    path: result.ocrPdfPath,
                    name: ocrFileName,
                    size: size || f.size,
                    status: 'pending',
                    pdfType: 'text_ocr',
                    ocrOption: 'yes',
                  }
                : f
            )
          );
        } else {
          console.error('OCR application failed:', result.error);
          setFiles((prev) =>
            prev.map((f) => (f.path === filePath ? { ...f, status: 'error', ocrOption: 'no' } : f))
          );
          await anonidata.dialog.showInfo(
            `Error al aplicar OCR: ${result.error || 'Error desconocido'}`,
            'Error'
          );
        }
      } catch (error) {
        console.error('Error applying OCR:', error);
        setFiles((prev) =>
          prev.map((f) => (f.path === filePath ? { ...f, status: 'error', ocrOption: 'no' } : f))
        );
        await anonidata.dialog.showInfo(`Error al aplicar OCR: ${error}`, 'Error');
      }
    } else {
      setFiles((prev) => prev.map((f) => (f.path === filePath ? { ...f, ocrOption: 'no' } : f)));
    }
  }, []);

  const handleOcrDecision = useCallback(
    async (filePath: string, decision: 'yes' | 'no' | 'yes_all' | 'no_all') => {
      const isAll = decision === 'yes_all' || decision === 'no_all';
      const finalDecision: 'yes' | 'no' =
        decision === 'yes' || decision === 'yes_all' ? 'yes' : 'no';

      if (isAll) {
        setBulkOcrDecision(finalDecision);
        bulkOcrDecisionRef.current = finalDecision;

        // Hacer una copia local de la cola para procesar
        const filesToProcess = [...ocrPromptFiles];

        // Limpiar cola de prompts inmediatamente para cerrar el modal
        setOcrPromptFiles([]);

        // Procesar secuencialmente
        for (const path of filesToProcess) {
          await processSingleOcrDecision(path, finalDecision);
        }
      } else {
        setOcrPromptFiles((prev) => prev.filter((p) => p !== filePath));
        await processSingleOcrDecision(filePath, finalDecision);
      }
    },
    [ocrPromptFiles, processSingleOcrDecision]
  );

  const processFilePdfTypeDetection = useCallback(
    async (file: FileItem) => {
      try {
        const { type: pdfType, pages } = await detectPdfType(file.path);

        // Mostrar 100% brevemente para una transición visual suave
        setFiles((prev) =>
          prev.map((f) =>
            f.path === file.path ? { ...f, progress: 100, step: 'Formato clasificado' } : f
          )
        );

        // Esperar a que la transición de la barra de progreso a 100% termine (400ms)
        await new Promise((resolve) => setTimeout(resolve, 400));

        setFiles((prev) => prev.map((f) => (f.path === file.path ? { ...f, pdfType, pages } : f)));

        if (pdfType === 'image') {
          processSingleOcrDecision(file.path, 'yes');
        }
      } catch (e) {
        console.error('Error detectando tipo de PDF:', e);
      }
    },
    [detectPdfType, processSingleOcrDecision]
  );

  const handleSelectFiles = useCallback(async () => {
    setBulkOcrDecision(null);
    bulkOcrDecisionRef.current = null;
    const filePaths = await anonidata.dialog.openFile();
    if (filePaths.length > 0) {
      const newFilesPromises = filePaths.map(async (filePath) => {
        const fileName = filePath.split(/[/\\]/).pop() || filePath;
        let size = 0;
        try {
          size = await anonidata.utils.getFileSize(filePath);
        } catch (e) {
          console.error('Error getting file size for selected file:', e);
        }
        return {
          path: filePath,
          name: fileName,
          size,
          status: 'pending' as const,
          progress: 0,
          pdfType: 'detecting' as const,
        };
      });

      const newFiles = await Promise.all(newFilesPromises);
      const uniqueNewFiles = newFiles.filter(f => {
        if (processedPathsRef.current.has(f.path)) return false;
        processedPathsRef.current.add(f.path);
        return true;
      });

      if (uniqueNewFiles.length > 0) {
        setFiles((prev) => [...prev, ...uniqueNewFiles]);

        // Detectar tipo de PDF para cada archivo en paralelo
        uniqueNewFiles.forEach((file) => {
          processFilePdfTypeDetection(file);
        });
      }
    }
  }, [processFilePdfTypeDetection]);

  // Procesar archivos a partir de sus rutas absolutas (Tauri 2 native drag-drop)
  const handleDroppedPaths = useCallback(
    async (filePaths: string[]) => {
      try {
        setBulkOcrDecision(null);
        bulkOcrDecisionRef.current = null;

        const newFilesPromises = filePaths.map(async (filePath) => {
          const fileName = filePath.split(/[/\\]/).pop() || filePath;
          let size = 0;
          try {
            size = await anonidata.utils.getFileSize(filePath);
          } catch (e) {
            console.error('Error getting file size for dropped file:', e);
          }

          return {
            path: filePath,
            name: fileName,
            size,
            status: 'pending' as const,
            progress: 0,
            pdfType: 'detecting' as const,
          };
        });

        const newFiles = await Promise.all(newFilesPromises);
        const uniqueNewFiles = newFiles.filter(f => {
          if (processedPathsRef.current.has(f.path)) return false;
          processedPathsRef.current.add(f.path);
          return true;
        });

        if (uniqueNewFiles.length > 0) {
          setFiles((prev) => [...prev, ...uniqueNewFiles]);

          // Detectar tipo de PDF para cada archivo en paralelo
          uniqueNewFiles.forEach((file) => {
            processFilePdfTypeDetection(file);
          });
        }
      } catch (err) {
        console.error('Error processing dropped paths:', err);
      }
    },
    [processFilePdfTypeDetection]
  );

  // Listener para arrastrar y soltar archivos desde el OS usando la API nativa de Tauri 2
  useEffect(() => {
    let unlistenFn: (() => void) | undefined;

    const setupDragDrop = async () => {
      try {
        const { getCurrentWebview } = await import('@tauri-apps/api/webview');
        const webview = getCurrentWebview();

        const unlisten = await webview.onDragDropEvent((event) => {
          if (event.payload.type === 'drop') {
            setIsDragActive(false);
            const paths = event.payload.paths;
            const pdfPaths = paths.filter((p) => p.toLowerCase().endsWith('.pdf'));

            if (pdfPaths.length > 0) {
              handleDroppedPaths(pdfPaths);
            }
          } else if (event.payload.type === 'enter') {
            setIsDragActive(true);
          } else if (event.payload.type === 'leave' || event.payload.type === 'cancel') {
            setIsDragActive(false);
          }
        });

        unlistenFn = unlisten;
      } catch (err) {
        console.error('Error setting up drag-drop listener:', err);
      }
    };

    setupDragDrop();

    return () => {
      if (unlistenFn) {
        unlistenFn();
      }
    };
  }, [handleDroppedPaths]);

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

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragActive(false);

      // Evitar que el drag-and-drop del navegador interfiera con el evento nativo de Tauri 2
      const isTauri =
        typeof window !== 'undefined' &&
        ((window as any).__tauri_ipc__ !== undefined ||
          (window as any).__TAURI_INTERNALS__ !== undefined ||
          (window as any).__TAURI__ !== undefined);
      if (isTauri) {
        return;
      }

      setBulkOcrDecision(null);
      bulkOcrDecisionRef.current = null;

      const droppedFiles = Array.from(e.dataTransfer.files);
      const pdfFiles = droppedFiles.filter(
        (file) => file.type === 'application/pdf' || file.name.endsWith('.pdf')
      );

      // En Tauri, los File objects del drag-drop del navegador no tienen 'path'.
      // Usamos el nombre del archivo como fallback. Para rutas completas,
      // se recomienda usar el evento tauri://drag-drop.
      const newFiles: FileItem[] = pdfFiles.map((file: any) => {
        // En Tauri webview, file.path puede estar disponible en algunos casos
        const filePath = file.path || file.name;

        return {
          path: filePath,
          name: file.name,
          size: file.size,
          status: 'pending' as const,
          progress: 0,
          pdfType: 'detecting' as const,
        };
      });

      const uniqueNewFiles = newFiles.filter(f => {
        if (processedPathsRef.current.has(f.path)) return false;
        processedPathsRef.current.add(f.path);
        return true;
      });

      if (uniqueNewFiles.length > 0) {
        setFiles((prev) => [...prev, ...uniqueNewFiles]);

        // Detectar tipo de PDF para cada archivo en paralelo
        uniqueNewFiles.forEach((file) => {
          processFilePdfTypeDetection(file);
        });
      }
    },
    [processFilePdfTypeDetection]
  );

  const handleProcess = async () => {
    if (files.length === 0) return;

    const processableFiles = files.filter((f) => f.pdfType !== 'detecting');
    const detectingFiles = files.filter((f) => f.pdfType === 'detecting');

    // Si hay archivos aún detectando, esperar
    if (detectingFiles.length > 0) {
      setCompletionData({
        type: 'partial',
        successCount: 0,
        errorCount: 0,
        totalFiles: files.length,
        processingTime: '0',
        warnings: [
          {
            file: 'Detección en progreso',
            warnings: [
              'Hay archivos pendientes de detección. Por favor, espere a que se complete la detección de todos los archivos.',
            ],
          },
        ],
      });
      setShowCompletionModal(true);
      return;
    }

    // Si no hay archivos procesables
    if (processableFiles.length === 0) {
      return;
    }

    setIsProcessing(true);
    setProcessResult(null);

    const startTime = Date.now();

    try {
      const filePaths = processableFiles.map((f) => f.path);

      // Actualizar estado a processing para todos los archivos
      setFiles((prev) =>
        prev.map((f) => {
          return { ...f, status: 'processing' as const, progress: 0 };
        })
      );

      // Simular pasos de procesamiento para mejor UX
      const steps = [
        'Analizando documentos...',
        'Detectando datos personales...',
        'Procesando anonimizaciones...',
        'Generando PDFs finales...',
      ];

      let stepIndex = 0;
      const stepInterval = setInterval(() => {
        if (stepIndex < steps.length) {
          setProcessingStep(steps[stepIndex]);
          stepIndex++;
        }
      }, 1500);

      // Construir las opciones específicas de OCR por archivo
      const fileOptions: Record<string, { enable_ocr?: boolean }> = {};
      files.forEach((f) => {
        if (f.ocrOption !== undefined) {
          fileOptions[f.path] = { enable_ocr: f.ocrOption === 'yes' };
        }
      });

      const result = await anonidata.process.anonymize(filePaths, { 
        fileOptions,
        redaction_strategy: redactionStrategy
      });

      clearInterval(stepInterval);
      setProcessingStep('');

      const endTime = Date.now();
      const processingTimeSeconds = ((endTime - startTime) / 1000).toFixed(2);

      // Actualizar resultados para archivos procesados
      setFiles((prev) =>
        prev.map((f) => {
          const resultIdx = processableFiles.findIndex((pf) => pf.path === f.path);
          if (resultIdx >= 0 && result.results[resultIdx]) {
            const fileResult = result.results[resultIdx];
            return {
              ...f,
              status: fileResult.status === 'success' ? 'completed' : 'error',
              progress: 100,
              result: fileResult,
            };
          }
          return f;
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
          warnings: r.warnings || [],
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
            error: r.error || 'Error desconocido',
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
            error: r.error || 'Error desconocido',
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
      setFiles((prev) => prev.map((f) => ({ ...f, status: 'error' as const })));

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

  const handleClear = async () => {
    if (
      isProcessing ||
      files.some((f) => f.status === 'ocr_processing' || f.status === 'processing')
    ) {
      try {
        await anonidata.utils.restartBackend();
        console.log('Backend sidecar restarted due to manual cancellation.');
      } catch (error) {
        console.error('Error restarting backend:', error);
      }
    }
    setFiles([]);
    processedPathsRef.current.clear();
    setProcessResult(null);
    setIsProcessing(false);
    setBulkOcrDecision(null);
    bulkOcrDecisionRef.current = null;
  };

  const handleStartReview = useCallback(async (fileIndex: number) => {
    const file = filesRef.current[fileIndex];
    if (!file) return;
    setIsDetecting(fileIndex);

    try {
      const options = {
        enable_ocr: file.ocrOption !== 'no',
      };
      const result = await anonidata.process.detectOnly(file.path, options);

      // Parsear defensivamente si result viene como string
      let parsedResult = result;
      if (typeof result === 'string') {
        try {
          parsedResult = JSON.parse(result);
        } catch (e) {
          console.error('Failed to parse detectOnly result:', e);
        }
      }

      const success = parsedResult?.success;
      const preAnonymizedPath =
        parsedResult?.preAnonymizedPath || parsedResult?.pre_anonymized_path;
      const detectionsPath = parsedResult?.detectionsPath || parsedResult?.detections_path;

      if (success && preAnonymizedPath && detectionsPath) {
        setReviewState({
          originalFilePath: file.path,
          preAnonymizedPath: preAnonymizedPath,
          detectionsPath: detectionsPath,
          pdfType: file.pdfType || 'text',
        });
      } else {
        const errorMsg = parsedResult?.error || 'Respuesta inválida del backend';
        console.error('Error iniciando revisión:', errorMsg);
        await anonidata.dialog.showInfo(`Error al iniciar la revisión: ${errorMsg}`, 'Error');
      }
    } catch (error) {
      console.error('Error iniciando revisión:', error);
      await anonidata.dialog.showInfo(`Error al iniciar la revisión: ${error}`, 'Error');
    } finally {
      setIsDetecting(null);
    }
  }, []);

  // Monitorizar archivos cargados para abrir revisión manual automáticamente si es solo un archivo
  useEffect(() => {
    // Si algún archivo ya no está en la lista de archivos actual, eliminarlo de la lista de auto-revisados
    const currentPaths = new Set(files.map((f) => f.path));
    for (const path of autoReviewedFilesRef.current) {
      if (!currentPaths.has(path)) {
        autoReviewedFilesRef.current.delete(path);
      }
    }

    if (files.length === 1) {
      const singleFile = files[0];

      const isReady =
        singleFile.pdfType !== 'detecting' &&
        singleFile.status === 'pending' &&
        isDetecting === null &&
        reviewState === null &&
        !isProcessing &&
        !autoReviewedFilesRef.current.has(singleFile.path);

      if (isReady) {
        // Para archivos de imagen, esperar a que el usuario tome una decisión sobre el OCR
        const needsOcrDecision =
          singleFile.pdfType === 'image' && singleFile.ocrOption === undefined;
        if (!needsOcrDecision) {
          autoReviewedFilesRef.current.add(singleFile.path);
          handleStartReview(0);
        }
      }
    }
  }, [files, isDetecting, reviewState, isProcessing, handleStartReview]);

  const handleFinishReview = async (approvedIndices: number[], strategy: 'black_box' | 'text_label') => {
    if (!reviewState) return;

    try {
      const result = await anonidata.process.finalizeAnonymization(
        reviewState.originalFilePath,
        reviewState.detectionsPath,
        approvedIndices,
        { 
          isImagePdf: reviewState.pdfType === 'image',
          redaction_strategy: strategy
        }
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
          warnings:
            result.warnings && result.warnings.length > 0
              ? [
                  {
                    file:
                      reviewState.originalFilePath.split('/').pop() || reviewState.originalFilePath,
                    warnings: result.warnings,
                  },
                ]
              : undefined,
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
          errors: [
            {
              file: reviewState.originalFilePath.split('/').pop() || reviewState.originalFilePath,
              error: result.error || 'Error desconocido',
            },
          ],
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
        const deleteDetections = anonidata.utils.deleteFile(reviewState.detectionsPath);
        const deletePreAnonymized = anonidata.utils.deleteFile(reviewState.preAnonymizedPath);

        const [detectionsDeleted, preAnonymizedDeleted] = await Promise.all([
          deleteDetections,
          deletePreAnonymized,
        ]);

        if (!detectionsDeleted) {
          console.warn(
            `No se pudo eliminar el archivo de detecciones: ${reviewState.detectionsPath}`
          );
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

  useEffect(() => {
    handleCancelReviewRef.current = handleCancelReview;
  }, [handleCancelReview]);

  // Listener para el evento de solicitud de cierre de la ventana
  useEffect(() => {
    let unlisten: (() => void) | undefined;

    const setupCloseListener = async () => {
      const appWindow = getCurrentWindow();
      const unsubscribe = await appWindow.onCloseRequested(async (event) => {
        // Siempre prevenimos el cierre predeterminado primero
        event.preventDefault();

        if (reviewStateRef.current) {
          // Si estamos en la pantalla de revisión manual, cancelar la revisión
          if (handleCancelReviewRef.current) {
            await handleCancelReviewRef.current();
          }
        } else {
          // Verificar si hay archivos en estado 'pending'
          const hasPending = filesRef.current.some((f) => f.status === 'pending');
          if (hasPending) {
            const confirmed = await ask(
              'Hay archivos pendientes de procesamiento. ¿Estás seguro de que deseas cerrar la aplicación?',
              {
                title: 'Confirmar cierre',
                kind: 'warning',
                okLabel: 'Sí',
                cancelLabel: 'No',
              }
            );
            if (confirmed) {
              await appWindow.destroy();
            }
          } else {
            // Si no hay archivos pendientes, cerrar directamente
            await appWindow.destroy();
          }
        }
      });
      unlisten = unsubscribe;
    };

    setupCloseListener().catch((err) => {
      console.error('Error al configurar listener de cierre de ventana:', err);
    });

    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  // Si estamos en modo revisión, mostrar ReviewScreen
  if (reviewState) {
    return (
      <ReviewScreen
        originalFilePath={reviewState.originalFilePath}
        preAnonymizedPath={reviewState.preAnonymizedPath}
        detectionsPath={reviewState.detectionsPath}
        defaultStrategy={redactionStrategy}
        onFinish={handleFinishReview}
        onCancel={handleCancelReview}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-stone-900 to-zinc-950 text-stone-100 selection:bg-teal-500/30">
      <div className="container mx-auto px-4 py-4">
        {/* Header - Layout Flex para alinear icono grande y texto */}
        <header className="flex items-center gap-6 mb-6 relative">
          <button
            onClick={() => setShowAboutModal(true)}
            className="flex-shrink-0 w-24 h-24 flex items-center justify-center hover:scale-105 transition-transform duration-200 rounded-2xl hover:shadow-lg bg-stone-900/40 backdrop-blur-md shadow-lg border border-stone-800/80"
            title="Acerca de AnoniData"
          >
            <img src={logoImage} alt="AnoniData Logo" className="w-16 h-16 object-contain" />
          </button>

          <div className="flex-1 text-center">
            <h1 className="text-4xl font-bold text-stone-100 mb-2 tracking-tight">AnoniData</h1>
            <p className="text-stone-400">Anonimización de PDFs conforme a RGPD</p>
          </div>

          <div className="flex-shrink-0 w-24 flex justify-end">
            <button
              onClick={() => setShowSettingsModal(true)}
              className="text-stone-400 hover:text-white transition-colors p-3 rounded-full hover:bg-stone-800/60 hover:shadow-lg border border-transparent hover:border-stone-700/50 bg-stone-900/20 backdrop-blur-sm"
              title="Ajustes"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
          </div>
        </header>

        {/* File Selection Area - Drag & Drop */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-4 border-dashed rounded-2xl p-8 mb-4 text-center transition-all duration-300 ${
            isDragActive
              ? 'border-teal-500 bg-teal-950/20 shadow-teal-500/10 scale-105 shadow-2xl'
              : 'border-stone-800 bg-stone-900/30 hover:border-stone-700/60 shadow-md hover:shadow-lg'
          }`}
        >
          <div className="text-stone-300">
            <svg
              className="mx-auto h-16 w-16 mb-4 text-stone-500"
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
                <p className="text-lg mb-3">Arrastra archivos PDF aquí o</p>
                <button
                  onClick={handleSelectFiles}
                  className="btn-primary btn-ripple mb-3 animate-fade-in-up"
                >
                  Seleccionar PDFs
                </button>
              </>
            )}
            <p className="text-sm text-stone-500">
              Procesamiento 100% local - Tus datos nunca salen de tu ordenador
            </p>
          </div>
        </div>



        {/* Process Button - Always visible above the list */}
        {files.length > 0 && (
          <div className="text-center mb-6">
            <button
              onClick={handleProcess}
              disabled={
                isProcessing ||
                files.some((f) => f.pdfType === 'detecting' || f.status === 'processing') ||
                files.every((f) => f.status === 'completed')
              }
              className={`btn-primary btn-ripple scale-on-hover ${
                files.some((f) => f.pdfType === 'detecting') && !isProcessing
                  ? 'opacity-70 cursor-not-allowed'
                  : ''
              }`}
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
          <div className="glass rounded-2xl shadow-xl p-6 mb-6 border border-stone-800/60">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-stone-200">Archivos ({files.length})</h2>
              <button
                onClick={handleClear}
                className="text-sm text-stone-400 hover:text-red-400 transition-all scale-on-hover font-medium"
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
                      ? 'border-teal-500 bg-teal-950/20 shadow-xl ring-2 ring-teal-900/60 scale-[1.02]'
                      : 'border-stone-850 hover:border-teal-500/40 shadow-md hover:shadow-xl card-hover bg-stone-900/40'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-stone-200 truncate">{file.name}</p>
                      <p className="text-xs text-stone-400 flex items-center gap-2">
                        <span>{formatBytes(file.size)}</span>
                        {file.pages !== undefined && (
                          <>
                            <span className="text-stone-600">•</span>
                            <span>
                              {file.pages} {file.pages === 1 ? 'página' : 'páginas'}
                            </span>
                          </>
                        )}
                        {file.pdfType === 'detecting' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-stone-950/50 text-stone-400 border border-stone-900/40 text-xs font-medium animate-pulse">
                            🔍 Analizando tipo...
                          </span>
                        )}
                        {file.pdfType === 'text' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-950/50 text-blue-400 border border-blue-900/40 text-xs font-medium">
                            📄 Texto
                          </span>
                        )}
                        {file.pdfType === 'text_ocr' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/50 text-emerald-400 border border-emerald-900/40 text-xs font-medium">
                            📝 Texto OCR
                          </span>
                        )}
                        {file.pdfType === 'image' && (
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                              file.ocrOption === 'yes'
                                ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-900/40'
                                : file.ocrOption === 'no'
                                  ? 'bg-red-950/50 text-red-400 border border-red-900/40'
                                  : 'bg-amber-950/50 text-amber-400 border border-amber-900/40'
                            }`}
                          >
                            🖼️ Imagen {file.ocrOption === 'yes' && '(OCR)'}
                            {file.ocrOption === 'no' && '(Sin OCR)'}
                          </span>
                        )}
                      </p>
                    </div>
                    <div className="ml-4">
                      {file.status === 'pending' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-stone-800 text-stone-300 border border-stone-700/50">
                          Pendiente
                        </span>
                      )}
                      {file.status === 'ocr_processing' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-amber-950/60 text-amber-400 border border-amber-900/40 animate-pulse">
                          Aplicando OCR...
                        </span>
                      )}
                      {file.status === 'processing' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-teal-950/60 text-teal-400 border border-teal-900/40">
                          Procesando...
                        </span>
                      )}
                      {file.status === 'completed' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-950/60 text-green-400 border border-green-900/40">
                          ✓ Completado
                        </span>
                      )}
                      {file.status === 'error' && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-950/60 text-red-400 border border-red-900/40">
                          ✗ Error
                        </span>
                      )}
                    </div>
                  </div>

                  {file.status === 'ocr_processing' && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-xs text-stone-400">
                        <span className="flex items-center gap-2">
                          <div
                            className="spinner-modern"
                            style={{ width: '12px', height: '12px', borderWidth: '2px' }}
                          ></div>
                          <span className="font-medium">
                            {file.step || 'Convirtiendo PDF a texto editable (OCR)...'}
                          </span>
                        </span>
                        <span className="font-semibold">{file.progress || 0}%</span>
                      </div>
                      <div className="w-full bg-stone-800 rounded-full h-2.5 overflow-hidden shadow-inner">
                        <div
                          className="bg-amber-500 h-2.5 rounded-full transition-all duration-500"
                          style={{ width: `${file.progress || 0}%` }}
                        ></div>
                      </div>
                    </div>
                  )}

                  {file.status === 'processing' && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-xs text-stone-400">
                        <span className="flex items-center gap-2">
                          <div
                            className="spinner-modern"
                            style={{ width: '12px', height: '12px', borderWidth: '2px' }}
                          ></div>
                          <span className="font-medium flex items-center gap-1">
                            {file.step || processingStep || 'Procesando documento'}
                            <span className="dots-pulse text-teal-400">
                              <span></span>
                              <span></span>
                              <span></span>
                            </span>
                          </span>
                        </span>
                        <span className="font-semibold">{file.progress || 0}%</span>
                      </div>
                      <div className="w-full bg-stone-800 rounded-full h-2.5 overflow-hidden shadow-inner">
                        <div
                          className="bg-gradient-to-r from-teal-500 via-cyan-500 to-teal-500 h-2.5 rounded-full transition-all duration-500 progress-wave"
                          style={{
                            width: `${file.progress || 0}%`,
                            backgroundSize: '200% 100%',
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {file.pdfType === 'detecting' && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-xs text-stone-400">
                        <span className="flex items-center gap-2">
                          <div
                            className="spinner-modern"
                            style={{ width: '12px', height: '12px', borderWidth: '2px' }}
                          ></div>
                          <span className="font-medium flex items-center gap-1">
                            {file.step || 'Analizando tipo de PDF...'}
                            <span className="dots-pulse text-teal-400">
                              <span></span>
                              <span></span>
                              <span></span>
                            </span>
                          </span>
                        </span>
                        <span className="font-semibold">{file.progress || 0}%</span>
                      </div>
                      <div className="w-full bg-stone-800 rounded-full h-2.5 overflow-hidden shadow-inner">
                        <div
                          className="bg-gradient-to-r from-teal-500 via-cyan-500 to-teal-500 h-2.5 rounded-full transition-all duration-500 progress-wave"
                          style={{
                            width: `${file.progress || 0}%`,
                            backgroundSize: '200% 100%',
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {file.result && file.status === 'completed' && (
                    <div className="mt-3 pt-3 border-t border-stone-850">
                      <p className="text-xs text-stone-400 mb-2">Datos redactados:</p>
                      <div className="grid grid-cols-3 gap-2 text-xs text-stone-300">
                        <div>
                          <span className="font-medium">{file.result.stats.dniCount}</span> DNI/NIE
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.nameCount}</span> Nombres
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.addressCount}</span>{' '}
                          Direcciones
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.phoneCount}</span>{' '}
                          Teléfonos
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.emailCount}</span> Emails
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.signatureCount}</span>{' '}
                          Firmas
                        </div>
                        <div>
                          <span className="font-medium">{file.result.stats.qrCount}</span> QR Codes
                        </div>
                      </div>
                      <p className="text-xs text-stone-500 mt-2">
                        Guardado en: {file.result.outputFile}
                      </p>
                    </div>
                  )}

                  {file.status === 'pending' && (
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={() => handleStartReview(idx)}
                        disabled={isDetecting === idx || file.pdfType === 'detecting'}
                        className="px-3 py-1.5 bg-teal-600 text-white text-xs rounded hover:bg-teal-500 scale-on-hover disabled:bg-stone-800 disabled:text-stone-500 disabled:cursor-not-allowed disabled:scale-100 transition-all duration-200 shadow-md hover:shadow-lg border border-teal-500/20 disabled:border-stone-800"
                      >
                        {isDetecting === idx ? (
                          <span className="flex items-center justify-center gap-2">
                            <div
                              className="spinner-modern"
                              style={{ width: '14px', height: '14px', borderWidth: '2px' }}
                            ></div>
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

                  {isDetecting === idx && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-xs text-stone-400">
                        <span className="flex items-center gap-2">
                          <div
                            className="spinner-modern"
                            style={{ width: '12px', height: '12px', borderWidth: '2px' }}
                          ></div>
                          <span className="font-medium flex items-center gap-1">
                            {file.step || 'Detectando PII'}
                            <span className="dots-pulse text-teal-400">
                              <span></span>
                              <span></span>
                              <span></span>
                            </span>
                          </span>
                        </span>
                        <span className="font-semibold">{file.progress || 0}%</span>
                      </div>
                      <div className="w-full bg-stone-800 rounded-full h-2.5 overflow-hidden shadow-inner">
                        <div
                          className="bg-gradient-to-r from-teal-500 via-cyan-500 to-teal-500 h-2.5 rounded-full transition-all duration-500 progress-wave"
                          style={{
                            width: `${file.progress || 0}%`,
                            backgroundSize: '200% 100%',
                          }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results Summary */}
        {processResult && (
          <div className="mt-8 glass rounded-2xl shadow-xl p-6 border border-stone-800/60">
            <h2 className="text-xl font-semibold text-stone-200 mb-4">Resumen del Procesamiento</h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-6 bg-gradient-to-br from-green-950/20 to-emerald-950/20 rounded-xl shadow-md border border-green-900/40">
                <p className="text-4xl font-bold text-green-400 mb-1">
                  {processResult.results.filter((r) => r.status === 'success').length}
                </p>
                <p className="text-sm text-stone-400 font-medium">Archivos exitosos</p>
              </div>
              <div className="text-center p-6 bg-gradient-to-br from-red-950/20 to-rose-950/20 rounded-xl shadow-md border border-red-900/40">
                <p className="text-4xl font-bold text-red-400 mb-1">
                  {processResult.results.filter((r) => r.status === 'error').length}
                </p>
                <p className="text-sm text-stone-400 font-medium">Archivos con error</p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-sm text-stone-500">
          <p>Procesamiento 100% local - Sin telemetría - Conforme a RGPD</p>
          <p className="mt-2 text-xs text-stone-500">
            v{__APP_VERSION__} · by{' '}
            <button
              onClick={() => anonidata.utils.openExternal('https://x.com/TbanR')}
              className="text-teal-400 hover:text-teal-300 hover:underline transition-colors cursor-pointer"
            >
              @TbanR
            </button>
          </p>
        </footer>
      </div>

      {/* Modal de Completación */}
      {showCompletionModal && completionData && (
        <div className="modal-backdrop backdrop-blur-strong p-4">
          <div className="modal-content glass rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border-2 border-stone-800/80">
            {/* Header */}
            <div
              className={`p-8 rounded-t-2xl ${
                completionData.type === 'success' &&
                completionData.warnings &&
                completionData.warnings.length > 0
                  ? 'bg-gradient-to-r from-amber-600 to-orange-600'
                  : completionData.type === 'success'
                    ? 'bg-gradient-to-r from-green-600 to-green-700'
                    : completionData.type === 'partial'
                      ? 'bg-gradient-to-r from-amber-600 to-orange-600'
                      : 'bg-gradient-to-r from-red-600 to-rose-700'
              }`}
            >
              <div className="flex items-center justify-between text-white">
                <h2 className="text-3xl font-bold">
                  {completionData.type === 'success' &&
                  completionData.warnings &&
                  completionData.warnings.length > 0
                    ? 'Completado con Advertencias'
                    : completionData.type === 'success'
                      ? 'Proceso Completado'
                      : completionData.type === 'partial'
                        ? 'Completado con Errores'
                        : 'Error en el Procesamiento'}
                </h2>
              </div>
            </div>

            {/* Body */}
            <div className="p-8">
              {/* Estadísticas */}
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="text-center p-6 bg-stone-900/50 border border-stone-850 rounded-xl">
                  <div className="text-4xl font-bold text-stone-100 mb-2">
                    {completionData.totalFiles}
                  </div>
                  <div className="text-sm text-stone-400">Total de archivos</div>
                </div>
                <div className="text-center p-6 bg-green-950/20 border border-green-900/30 rounded-xl">
                  <div className="text-4xl font-bold text-green-400 mb-2">
                    {completionData.successCount}
                  </div>
                  <div className="text-sm text-stone-400">Procesados</div>
                </div>
                <div className="text-center p-6 bg-stone-900/50 border border-stone-850 rounded-xl">
                  <div className="text-4xl font-bold text-stone-100 mb-2">
                    {completionData.processingTime}s
                  </div>
                  <div className="text-sm text-stone-400">Tiempo total</div>
                </div>
              </div>

              {/* Mensaje de Éxito */}
              {completionData.type === 'success' && (
                <div className="bg-teal-950/20 border-l-4 border-teal-500 p-6 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold text-teal-400 mb-3">
                    Revisión Manual Requerida
                  </h3>
                  <p className="text-teal-300 leading-relaxed">
                    Por favor, <strong>revise manualmente</strong> los archivos anonimizados para
                    verificar que no queden datos personales sin excluir.
                  </p>
                  <p className="text-teal-300 leading-relaxed mt-2">
                    Es fundamental verificar que toda la información sensible haya sido
                    correctamente anonimizada.
                  </p>
                </div>
              )}

              {/* Lista de Advertencias */}
              {completionData.warnings && completionData.warnings.length > 0 && (
                <div className="bg-amber-950/20 border-l-4 border-amber-500 p-6 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold text-amber-400 mb-4">
                    Advertencias ({completionData.warnings.length})
                  </h3>
                  <div className="space-y-3 max-h-60 overflow-y-auto">
                    {completionData.warnings.map((warn, idx) => (
                      <div
                        key={idx}
                        className="bg-stone-900 p-4 rounded-lg shadow-sm border border-stone-850"
                      >
                        <div className="font-medium text-amber-400 mb-2">{warn.file}</div>
                        <div className="space-y-1">
                          {warn.warnings.map((warning, widx) => (
                            <div key={widx} className="text-sm text-amber-300">
                              {warning}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Lista de Errores */}
              {completionData.errors && completionData.errors.length > 0 && (
                <div className="bg-red-950/20 border-l-4 border-red-500 p-6 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold mb-4 text-red-400">
                    Errores Encontrados ({completionData.errorCount})
                  </h3>
                  <div className="space-y-3 max-h-60 overflow-y-auto">
                    {completionData.errors.map((err, idx) => (
                      <div
                        key={idx}
                        className="bg-stone-900 p-4 rounded-lg shadow-sm border border-stone-850"
                      >
                        <div className="font-medium mb-1 text-red-400">{err.file}</div>
                        <div className="text-sm text-red-300">{err.error}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Mensaje Crítico */}
              {completionData.type === 'critical' && completionData.message && (
                <div className="bg-red-950/20 border-l-4 border-red-500 p-6 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold mb-3 text-red-400">Error Crítico</h3>
                  <p className="leading-relaxed mb-3 text-red-300">
                    Ocurrió un error inesperado durante el procesamiento:
                  </p>
                  <code className="block p-4 rounded text-sm bg-red-950/40 text-red-400 border border-red-900/30 font-mono">
                    {completionData.message}
                  </code>
                  <p className="leading-relaxed mt-3 text-red-300">
                    Por favor, intente nuevamente o contacte soporte técnico.
                  </p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-8 pb-8">
              <button
                onClick={() => setShowCompletionModal(false)}
                className="w-full bg-gradient-to-r from-teal-500 to-teal-600 hover:from-teal-600 hover:to-teal-700 text-white font-semibold py-4 px-6 rounded-xl shadow-lg transition-all transform hover:scale-[1.02]"
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
          <div className="modal-content glass rounded-2xl shadow-2xl max-w-lg w-full border-2 border-stone-800/80">
            {/* Header */}
            <div className="p-8 rounded-t-2xl bg-gradient-to-r from-teal-700 to-cyan-700">
              <div className="text-white text-center">
                <div className="flex justify-center mb-4">
                  <img src={logoImage} alt="AnoniData Logo" className="w-20 h-20 object-contain" />
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
                  <p className="text-sm text-stone-500 mb-1">Versión</p>
                  <p className="text-2xl font-bold text-stone-200">{__APP_VERSION__}</p>
                </div>

                {/* Fecha de compilación */}
                <div className="text-center">
                  <p className="text-sm text-stone-500 mb-1">Fecha de compilación</p>
                  <p className="text-lg text-stone-300">{__BUILD_DATE__}</p>
                </div>

                {/* Contacto */}
                <div className="pt-6 border-t border-stone-800">
                  <div className="text-center">
                    <p className="text-sm text-stone-500 mb-3">Contacto</p>
                    <button
                      onClick={() => anonidata.utils.openExternal('https://x.com/TbanR')}
                      className="inline-flex items-center gap-2 text-teal-400 hover:text-teal-300 font-medium transition-colors cursor-pointer"
                    >
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                      </svg>
                      @TbanR
                    </button>
                  </div>
                </div>

                {/* Características */}
                <div className="pt-6 border-t border-stone-800">
                  <div className="grid grid-cols-1 gap-3 text-sm text-stone-400">
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">✓</span>
                      <span>Procesamiento 100% local</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">✓</span>
                      <span>Sin telemetría ni conexión a internet</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">✓</span>
                      <span>Conforme al Reglamento General de Protección de Datos (RGPD)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-emerald-400">✓</span>
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
                className="w-full bg-gradient-to-r from-teal-500 to-teal-600 hover:from-teal-600 hover:to-teal-700 text-white font-semibold py-3 px-6 rounded-xl shadow-lg transition-all transform hover:scale-[1.02]"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}



      {/* Componente de actualización automática */}
      <UpdateNotification />

      {/* Modal de Configuración */}
      {showSettingsModal && (
        <SettingsModal
          onClose={() => setShowSettingsModal(false)}
          onSettingsSaved={(newSettings) => {
            setRedactionStrategy(newSettings.defaultRedactionStrategy);
          }}
        />
      )}
    </div>
  );
}

export default App;
