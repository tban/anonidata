import React, { useEffect, useState } from 'react';
import { listen } from '../lib/tauri-bridge';

interface UpdateState {
  downloading: boolean;
  progress: number;
  downloaded: number;
  total: number;
}

export const UpdateNotification: React.FC = () => {
  const [updateState, setUpdateState] = useState<UpdateState>({
    downloading: false,
    progress: 0,
    downloaded: 0,
    total: 0,
  });

  useEffect(() => {
    // Escuchar el inicio de la descarga
    const unlistenStart = listen<{total: number}>('updater-start', (event) => {
      console.log('Update download started', event.payload);
      setUpdateState({
        downloading: true,
        progress: 0,
        downloaded: 0,
        total: event.payload.total,
      });
    });

    // Escuchar el progreso
    const unlistenProgress = listen<{downloaded: number, total: number, percentage: number}>('updater-progress', (event) => {
      setUpdateState({
        downloading: true,
        progress: event.payload.percentage,
        downloaded: event.payload.downloaded,
        total: event.payload.total,
      });
    });

    return () => {
      unlistenStart.then(fn => fn());
      unlistenProgress.then(fn => fn());
    };
  }, []);

  if (!updateState.downloading) {
    return null;
  }

  // Formatear bytes a MB
  const formatMB = (bytes: number) => {
    return (bytes / (1024 * 1024)).toFixed(1);
  };

  return (
    <div className="fixed bottom-4 right-4 bg-stone-900/90 rounded-lg shadow-2xl border border-stone-850 p-5 max-w-md w-full z-50 glass text-stone-100 animate-fade-in-up">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-stone-200">Descargando actualización...</h3>
          <p className="text-sm text-stone-400 mt-1">
            {formatMB(updateState.downloaded)} MB / {formatMB(updateState.total)} MB
          </p>
        </div>
      </div>

      <div className="w-full bg-stone-800 rounded-full h-2.5 mt-4 overflow-hidden border border-stone-700">
        <div 
          className="bg-teal-500 h-2.5 rounded-full transition-all duration-300 ease-out" 
          style={{ width: `${Math.max(0, Math.min(100, updateState.progress))}%` }}
        ></div>
      </div>
      
      <div className="mt-2 text-right text-xs font-medium text-teal-400">
        {Math.round(updateState.progress)}%
      </div>
    </div>
  );
};
