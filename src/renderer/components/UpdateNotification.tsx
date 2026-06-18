import React, { useEffect, useState } from 'react';
import { platform } from '@tauri-apps/plugin-os';
import { anonidata } from '../lib/tauri-bridge';
import { listen } from '@tauri-apps/api/event';

interface UpdateState {
  available: boolean;
  version?: string;
  downloadUrl?: string;
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
  const [currentPlatform, setCurrentPlatform] = useState<string>('');

  const isWindows = currentPlatform === 'windows';
  const isMac = currentPlatform === 'macos';

  useEffect(() => {
    // Detectar plataforma
    const detectPlatform = async () => {
      try {
        const os = await platform();
        setCurrentPlatform(os);
      } catch (error) {
        console.error('Error detectando plataforma:', error);
      }
    };
    detectPlatform();

    // Verificar actualizaciones al iniciar
    handleCheckForUpdates(false);

    // Escuchar evento de búsqueda manual del menú
    let unlisten: any;
    const setupMenuListener = async () => {
      try {
        unlisten = await listen('check-updates', () => {
          handleCheckForUpdates(true);
        });
      } catch (error) {
        console.error('Error configurando menu listener de actualizaciones:', error);
      }
    };
    setupMenuListener();

    return () => {
      if (unlisten) {
        unlisten();
      }
    };
  }, []);

  const handleCheckForUpdates = async (manual: boolean) => {
    try {
      const currentVersion = await anonidata.app.getVersion();
      console.log('Versión actual:', currentVersion);
      
      const response = await fetch('https://api.github.com/repos/tban/anonidata/releases/latest');
      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status}`);
      }

      const data = await response.json();
      const latestVersion = data.tag_name.replace(/^v/, '');

      // Comparar versiones
      const isNewer = compareVersions(latestVersion, currentVersion) > 0;

      if (isNewer) {
        // Buscar asset según plataforma
        let downloadUrl = data.html_url;
        if (isWindows) {
          const exeAsset = data.assets.find((asset: any) => asset.name.endsWith('.exe'));
          if (exeAsset) downloadUrl = exeAsset.browser_download_url;
        } else if (isMac) {
          const dmgAsset = data.assets.find((asset: any) => asset.name.endsWith('.dmg'));
          if (dmgAsset) downloadUrl = dmgAsset.browser_download_url;
        }

        setUpdateState({
          available: true,
          version: latestVersion,
          downloadUrl: downloadUrl,
          downloading: false,
          readyToInstall: false,
        });
        setClosed(false);
      } else {
        console.log('La aplicación está actualizada');
        if (manual) {
          await anonidata.dialog.showInfo(
            `La aplicación está actualizada.\n\nYa tienes la versión más reciente (v${currentVersion}).`,
            'Buscar actualizaciones'
          );
        }
      }
    } catch (error: any) {
      console.error('Error verificando actualizaciones:', error);
      if (manual) {
        await anonidata.dialog.showInfo(
          `Ocurrió un error al buscar actualizaciones: ${error.message || error}`,
          'Error'
        );
      }
    }
  };

  const compareVersions = (v1: string, v2: string): number => {
    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);

    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
      const num1 = parts1[i] || 0;
      const num2 = parts2[i] || 0;

      if (num1 > num2) return 1;
      if (num1 < num2) return -1;
    }
    return 0;
  };

  const handleDownload = async () => {
    const url = updateState.downloadUrl || 'https://github.com/tban/anonidata/releases/latest';
    try {
      await anonidata.utils.openExternal(url);
    } catch (error) {
      console.error('Error abriendo url de descarga:', error);
    }
    setClosed(true);
  };

  const handleClose = () => {
    setClosed(true);
  };

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
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="mb-3 text-sm text-gray-600">
        Una nueva versión de AnoniData está disponible. Haz clic abajo para descargarla en tu equipo.
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleDownload}
          className="flex-1 bg-teal-600 hover:bg-teal-700 text-white font-medium py-2 px-4 rounded-md transition-colors text-center cursor-pointer"
        >
          Descargar ahora
        </button>
        <button
          onClick={handleClose}
          className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium transition-colors cursor-pointer"
        >
          Más tarde
        </button>
      </div>
    </div>
  );
};
