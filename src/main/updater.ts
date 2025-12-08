import { autoUpdater } from 'electron-updater';
import { app, BrowserWindow, dialog } from 'electron';
import log from 'electron-log';

interface UpdateInfo {
  available: boolean;
  version?: string;
  downloadUrl?: string;
  releaseNotes?: string;
}

export class AppUpdater {
  private mainWindow: BrowserWindow | null = null;
  private isDev: boolean;

  constructor(mainWindow: BrowserWindow | null, isDev: boolean) {
    this.mainWindow = mainWindow;
    this.isDev = isDev;

    // Configurar electron-updater
    autoUpdater.logger = log;
    (autoUpdater.logger as any).transports.file.level = 'info';

    // Desactivar auto-download en macOS (sin certificado)
    autoUpdater.autoDownload = process.platform === 'win32';

    // Configurar feed de GitHub Releases
    autoUpdater.setFeedURL({
      provider: 'github',
      owner: 'tban',
      repo: 'anonidata',
    });

    this.setupListeners();
  }

  private setupListeners() {
    // Evento: Actualización disponible
    autoUpdater.on('update-available', (info) => {
      log.info('Actualización disponible:', info.version);
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('updater:update-available', {
          version: info.version,
          releaseNotes: info.releaseNotes,
        });
      }
    });

    // Evento: No hay actualización
    autoUpdater.on('update-not-available', (info) => {
      log.info('La aplicación está actualizada:', app.getVersion());
    });

    // Evento: Error al buscar actualización
    autoUpdater.on('error', (err) => {
      log.error('Error en auto-updater:', err);
    });

    // Evento: Progreso de descarga (solo Windows)
    autoUpdater.on('download-progress', (progressObj) => {
      const message = `Descargando: ${Math.round(progressObj.percent)}%`;
      log.info(message);
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('updater:download-progress', {
          percent: Math.round(progressObj.percent),
          transferred: progressObj.transferred,
          total: progressObj.total,
        });
      }
    });

    // Evento: Descarga completada (solo Windows)
    autoUpdater.on('update-downloaded', (info) => {
      log.info('Actualización descargada, lista para instalar');
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        this.mainWindow.webContents.send('updater:update-downloaded', {
          version: info.version,
        });
      }
    });
  }

  // Verificar actualizaciones manualmente
  async checkForUpdates(): Promise<UpdateInfo> {
    if (this.isDev) {
      log.info('Modo desarrollo: actualizaciones deshabilitadas');
      return { available: false };
    }

    try {
      if (process.platform === 'win32') {
        // Windows: Usar electron-updater con Squirrel
        const result = await autoUpdater.checkForUpdates();
        if (result && result.updateInfo) {
          const available = result.updateInfo.version !== app.getVersion();
          return {
            available,
            version: result.updateInfo.version,
            releaseNotes: Array.isArray(result.updateInfo.releaseNotes)
              ? result.updateInfo.releaseNotes.join('\n')
              : (result.updateInfo.releaseNotes || undefined),
          };
        }
        return { available: false };
      } else if (process.platform === 'darwin') {
        // macOS: Check manual via GitHub API (sin certificado)
        const currentVersion = app.getVersion();
        const updateInfo = await this.checkGitHubReleases(currentVersion);
        return updateInfo;
      } else {
        log.info('Plataforma no soportada para actualizaciones');
        return { available: false };
      }
    } catch (error) {
      log.error('Error verificando actualizaciones:', error);
      return { available: false };
    }
  }

  // Check manual de GitHub Releases (para macOS sin certificado)
  private async checkGitHubReleases(currentVersion: string): Promise<UpdateInfo> {
    try {
      const response = await fetch('https://api.github.com/repos/tban/anonidata/releases/latest');

      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.status}`);
      }

      const data: any = await response.json();
      const latestVersion = data.tag_name.replace(/^v/, ''); // Remover 'v' del tag

      // Comparar versiones
      const isNewer = this.compareVersions(latestVersion, currentVersion) > 0;

      if (isNewer) {
        // Buscar asset DMG para macOS
        const dmgAsset = data.assets.find((asset: any) =>
          asset.name.endsWith('.dmg') && asset.name.includes('darwin')
        );

        return {
          available: true,
          version: latestVersion,
          downloadUrl: dmgAsset?.browser_download_url || data.html_url,
          releaseNotes: data.body || undefined,
        };
      }

      return { available: false };
    } catch (error) {
      log.error('Error fetching GitHub releases:', error);
      return { available: false };
    }
  }

  // Comparar versiones semánticas (1.2.3)
  private compareVersions(v1: string, v2: string): number {
    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);

    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
      const num1 = parts1[i] || 0;
      const num2 = parts2[i] || 0;

      if (num1 > num2) return 1;
      if (num1 < num2) return -1;
    }

    return 0;
  }

  // Descargar actualización (solo Windows con Squirrel)
  async downloadUpdate(): Promise<boolean> {
    if (process.platform !== 'win32') {
      log.warn('downloadUpdate solo funciona en Windows');
      return false;
    }

    try {
      await autoUpdater.downloadUpdate();
      return true;
    } catch (error) {
      log.error('Error descargando actualización:', error);
      return false;
    }
  }

  // Instalar y reiniciar (solo Windows)
  quitAndInstall(): void {
    if (process.platform !== 'win32') {
      log.warn('quitAndInstall solo funciona en Windows');
      return;
    }

    // Cerrar todos los procesos y reiniciar
    autoUpdater.quitAndInstall(false, true);
  }

  // Abrir página de descargas de GitHub (para macOS)
  openDownloadPage(): void {
    const { shell } = require('electron');
    const url = 'https://github.com/tban/anonidata/releases/latest';
    shell.openExternal(url);
    log.info('Abriendo página de descargas:', url);
  }
}
