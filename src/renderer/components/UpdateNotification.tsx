import React, { useEffect, useState } from 'react';
import type { UpdateInfo, UpdateAvailableInfo, DownloadProgress, UpdateDownloadedInfo } from '../../preload/preload';

interface UpdateState {
  available: boolean;
  version?: string;
  downloading: boolean;
  progress?: number;
  readyToInstall: boolean;
  error?: string;
}

export const UpdateNotification: React.FC = () => {
  const [updateState, setUpdateState] = useState<UpdateState>({
    available: false,
    downloading: false,
    readyToInstall: false,
  });

  const [closed, setClosed] = useState(false);

  const isWindows = process.platform === 'win32';
  const isMac = process.platform === 'darwin';

  useEffect(() => {
    // Escuchar evento: actualización disponible
    window.anonidata.updater.onUpdateAvailable((info: UpdateAvailableInfo) => {
      setUpdateState((prev) => ({
        ...prev,
        available: true,
        version: info.version,
      }));
      setClosed(false);
    });

    // Escuchar evento: progreso de descarga (solo Windows)
    window.anonidata.updater.onDownloadProgress((progress: DownloadProgress) => {
      setUpdateState((prev) => ({
        ...prev,
        downloading: true,
        progress: progress.percent,
      }));
    });

    // Escuchar evento: descarga completada (solo Windows)
    window.anonidata.updater.onUpdateDownloaded((info: UpdateDownloadedInfo) => {
      setUpdateState((prev) => ({
        ...prev,
        downloading: false,
        readyToInstall: true,
        version: info.version,
      }));
    });
  }, []);

  const handleCheckForUpdates = async () => {
    try {
      const result: UpdateInfo = await window.anonidata.updater.checkForUpdates();
      if (result.available) {
        setUpdateState({
          available: true,
          version: result.version,
          downloading: false,
          readyToInstall: false,
        });
        setClosed(false);
      } else {
        // Mostrar mensaje de que está actualizado (opcional)
        console.log('La aplicación está actualizada');
      }
    } catch (error) {
      console.error('Error verificando actualizaciones:', error);
      setUpdateState((prev) => ({
        ...prev,
        error: 'Error verificando actualizaciones',
      }));
    }
  };

  const handleDownload = async () => {
    if (isWindows) {
      // Windows: Descargar automáticamente
      setUpdateState((prev) => ({ ...prev, downloading: true, progress: 0 }));
      await window.anonidata.updater.downloadUpdate();
    } else if (isMac) {
      // macOS: Abrir página de descargas
      await window.anonidata.updater.openDownloadPage();
      setClosed(true);
    }
  };

  const handleInstall = async () => {
    // Solo Windows
    await window.anonidata.updater.installUpdate();
  };

  const handleClose = () => {
    setClosed(true);
  };

  // No mostrar si no hay actualización disponible o si el usuario cerró la notificación
  if ((!updateState.available && !updateState.readyToInstall) || closed) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 bg-white rounded-lg shadow-2xl border border-gray-200 p-4 max-w-md z-50">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">Actualización disponible</h3>
          {updateState.version && (
            <p className="text-sm text-gray-600">Versión {updateState.version}</p>
          )}
        </div>
        <button
          onClick={handleClose}
          className="text-gray-400 hover:text-gray-600 transition-colors"
          aria-label="Cerrar"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Estado: Descargando (solo Windows) */}
      {updateState.downloading && updateState.progress !== undefined && (
        <div className="mb-3">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Descargando...</span>
            <span>{updateState.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${updateState.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Estado: Lista para instalar (solo Windows) */}
      {updateState.readyToInstall && isWindows && (
        <div className="mb-3">
          <p className="text-sm text-gray-600">
            La actualización está lista. La aplicación se reiniciará para completar la instalación.
          </p>
        </div>
      )}

      {/* Botones de acción */}
      <div className="flex gap-2">
        {!updateState.downloading && !updateState.readyToInstall && (
          <>
            {isWindows && (
              <button
                onClick={handleDownload}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
              >
                Descargar e instalar
              </button>
            )}
            {isMac && (
              <button
                onClick={handleDownload}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
              >
                Ir a descargas
              </button>
            )}
            <button
              onClick={handleClose}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium transition-colors"
            >
              Más tarde
            </button>
          </>
        )}

        {updateState.readyToInstall && isWindows && (
          <>
            <button
              onClick={handleInstall}
              className="flex-1 bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
            >
              Reiniciar ahora
            </button>
            <button
              onClick={handleClose}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium transition-colors"
            >
              Más tarde
            </button>
          </>
        )}
      </div>

      {/* Error (si ocurre) */}
      {updateState.error && (
        <p className="text-sm text-red-600 mt-2">{updateState.error}</p>
      )}
    </div>
  );
};
