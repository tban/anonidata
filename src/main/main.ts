const { app, BrowserWindow, ipcMain, dialog, session } = require('electron');
const path = require('path');
const log = require('electron-log');
const Store = require('electron-store');
const { spawn } = require('child_process');
import { AppUpdater } from './updater';

// Types
type BrowserWindowType = any;
type ChildProcessType = any;

// Simple isDev check - verificar si está empaquetado
// En desarrollo: electron se ejecuta desde node_modules
// En producción: app está empaquetado
const isDev = process.env.NODE_ENV !== 'production' && /[\\/]electron[\\/]/.test(process.execPath);

// Configuración de logging
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

// Store para configuración persistente
const store = new Store({
  defaults: {
    windowBounds: { width: 1200, height: 800 },
    settings: {
      autoCleanTemp: true,
      logLevel: 'info',
      maxFileSize: 52428800, // 50MB
    },
  },
});

let mainWindow: any = null;
let pythonProcess: ChildProcessType = null;
let appUpdater: AppUpdater | null = null;

function createWindow() {
  const { width, height } = store.get('windowBounds') as { width: number; height: number };

  mainWindow = new BrowserWindow({
    width,
    height,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false, // Deshabilitado para permitir webUtils.getPathForFile()
    },
    title: 'AnoniData',
    show: false,
  });

  // Cargar la app
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    if (mainWindow) mainWindow.show();
  });

  mainWindow.on('close', () => {
    if (mainWindow) {
      const bounds = mainWindow.getBounds();
      store.set('windowBounds', bounds);
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Iniciar proceso Python
function startPythonBackend() {
  const pythonPath = isDev
    ? path.join(app.getAppPath(), 'backend/main.py')
    : path.join((process as any).resourcesPath, 'anonidata-backend');

  log.info(`Iniciando backend Python: ${pythonPath}`);

  const pythonExecutable = isDev
    ? path.join(app.getAppPath(), 'backend/venv/bin/python3')
    : pythonPath;
  const args = isDev ? [pythonPath] : [];

  pythonProcess = spawn(pythonExecutable, args, {
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  if (pythonProcess.stdout) {
    pythonProcess.stdout.on('data', (data: Buffer) => {
      log.info(`[Python] ${data.toString()}`);
    });
  }

  if (pythonProcess.stderr) {
    pythonProcess.stderr.on('data', (data: Buffer) => {
      log.error(`[Python Error] ${data.toString()}`);
    });
  }

  pythonProcess.on('close', (code: number) => {
    log.info(`Proceso Python cerrado con código: ${code}`);
  });

  return pythonProcess;
}

// App lifecycle
app.on('ready', () => {
  // Seguridad: Bloquear navegación externa
  app.on('web-contents-created', (_event: any, contents: any) => {
    contents.on('will-navigate', (event: any, navigationUrl: string) => {
      const parsedUrl = new URL(navigationUrl);
      if (parsedUrl.origin !== 'http://localhost:3000' && !navigationUrl.startsWith('file://')) {
        event.preventDefault();
        log.warn(`Navegación bloqueada a: ${navigationUrl}`);
      }
    });

    contents.setWindowOpenHandler(({ url }: { url: string }) => {
      log.warn(`Intento de abrir ventana externa bloqueado: ${url}`);
      return { action: 'deny' as const };
    });
  });

  // Bloquear requests externas en producción
  if (!isDev) {
    session.defaultSession.webRequest.onBeforeRequest({ urls: ['*://*/*'] }, (details: any, callback: any) => {
      const url = new URL(details.url);
      if (url.protocol === 'file:' || url.hostname === 'localhost') {
        callback({});
      } else {
        log.warn(`Request externa bloqueada: ${details.url}`);
        callback({ cancel: true });
      }
    });
  }

  // IPC Handlers
  ipcMain.handle('dialog:openFile', async (_event: any) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile', 'multiSelections'],
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    return result.filePaths;
  });

  ipcMain.handle('dialog:showInfo', async (_event: any, message: string, title?: string) => {
    await dialog.showMessageBox(mainWindow, {
      type: 'warning',
      title: title || 'Información',
      message: message,
      buttons: ['Entendido'],
    });
    return true;
  });

  ipcMain.handle('process:anonymize', async (_event: any, files: string[]) => {
    log.info(`Procesando ${files.length} archivos`);

    return new Promise((resolve, reject) => {
      if (!pythonProcess || pythonProcess.exitCode !== null) {
        pythonProcess = startPythonBackend();
      }

      const request = {
        action: 'anonymize',
        files: files,
        settings: store.get('settings'),
      };

      if (pythonProcess.stdin) {
        pythonProcess.stdin.write(JSON.stringify(request) + '\n');
      }

      let responseData = '';

      const dataHandler = (data: Buffer) => {
        responseData += data.toString();
        try {
          const response = JSON.parse(responseData);
          if (pythonProcess.stdout) {
            pythonProcess.stdout.removeListener('data', dataHandler);
          }

          if (response.success) {
            resolve(response);
          } else {
            reject(new Error(response.error));
          }
        } catch (e) {
          // Esperando más datos
        }
      };

      if (pythonProcess.stdout) {
        pythonProcess.stdout.on('data', dataHandler);
      }

      setTimeout(() => {
        if (pythonProcess.stdout) {
          pythonProcess.stdout.removeListener('data', dataHandler);
        }
        reject(new Error('Timeout procesando archivos'));
      }, 300000); // 5 minutos timeout
    });
  });

  ipcMain.handle('process:detectOnly', async (_event: any, filePath: string) => {
    log.info(`Detectando PII en: ${filePath}`);

    return new Promise((resolve, reject) => {
      if (!pythonProcess || pythonProcess.exitCode !== null) {
        pythonProcess = startPythonBackend();
      }

      const request = {
        action: 'detect_only',
        file: filePath,
        settings: store.get('settings'),
      };

      if (pythonProcess.stdin) {
        pythonProcess.stdin.write(JSON.stringify(request) + '\n');
      }

      let responseData = '';
      let resolved = false;

      const dataHandler = (data: Buffer) => {
        if (resolved) return;

        const chunk = data.toString();
        // Filtrar solo líneas que parecen JSON
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.trim() && line.includes('{') && line.includes('"success"')) {
            try {
              const response = JSON.parse(line);
              if (response.success !== undefined) {
                resolved = true;
                if (pythonProcess.stdout) {
                  pythonProcess.stdout.removeListener('data', dataHandler);
                }

                if (response.success) {
                  resolve(response);
                } else {
                  reject(new Error(response.error));
                }
                return;
              }
            } catch (e) {
              // No es JSON válido, continuar
            }
          }
        }
      };

      if (pythonProcess.stdout) {
        pythonProcess.stdout.on('data', dataHandler);
      }

      setTimeout(() => {
        if (!resolved && pythonProcess.stdout) {
          pythonProcess.stdout.removeListener('data', dataHandler);
          reject(new Error('Timeout detectando PII'));
        }
      }, 300000);
    });
  });

  ipcMain.handle(
    'process:finalizeAnonymization',
    async (_event: any, originalFile: string, detectionsPath: string, approvedIndices: number[]) => {
      log.info(`Finalizando anonimización para: ${originalFile}`);

      return new Promise((resolve, reject) => {
        if (!pythonProcess || pythonProcess.exitCode !== null) {
          pythonProcess = startPythonBackend();
        }

        const request = {
          action: 'finalize_anonymization',
          originalFile: originalFile,
          detectionsPath: detectionsPath,
          approvedIndices: approvedIndices,
          settings: store.get('settings'),
        };

        if (pythonProcess.stdin) {
          pythonProcess.stdin.write(JSON.stringify(request) + '\n');
        }

        let responseData = '';
        let resolved = false;

        const dataHandler = (data: Buffer) => {
          if (resolved) return;

          const chunk = data.toString();
          // Filtrar solo líneas que parecen JSON
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.trim() && line.includes('{') && line.includes('"success"')) {
              try {
                const response = JSON.parse(line);
                if (response.success !== undefined) {
                  resolved = true;
                  if (pythonProcess.stdout) {
                    pythonProcess.stdout.removeListener('data', dataHandler);
                  }

                  if (response.success) {
                    resolve(response);
                  } else {
                    reject(new Error(response.error));
                  }
                  return;
                }
              } catch (e) {
                // No es JSON válido, continuar
              }
            }
          }
        };

        if (pythonProcess.stdout) {
          pythonProcess.stdout.on('data', dataHandler);
        }

        setTimeout(() => {
          if (!resolved && pythonProcess.stdout) {
            pythonProcess.stdout.removeListener('data', dataHandler);
            reject(new Error('Timeout finalizando anonimización'));
          }
        }, 300000);
      });
    }
  );

  ipcMain.handle('review:loadDetections', async (_event: any, detectionsPath: string) => {
    try {
      const fs = require('fs').promises;
      const data = await fs.readFile(detectionsPath, 'utf-8');
      const detections = JSON.parse(data);
      return { success: true, detections };
    } catch (error: any) {
      log.error(`Error cargando detecciones: ${error.message}`);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('review:saveDetections', async (_event: any, detectionsPath: string, detections: any[]) => {
    try {
      const fs = require('fs').promises;
      await fs.writeFile(detectionsPath, JSON.stringify(detections, null, 2), 'utf-8');
      log.info(`Detecciones guardadas: ${detectionsPath} (${detections.length} detecciones)`);
      return true;
    } catch (error: any) {
      log.error(`Error guardando detecciones: ${error.message}`);
      return false;
    }
  });

  ipcMain.handle('app:getVersion', (_event: any) => {
    return app.getVersion();
  });

  ipcMain.handle('store:get', (_event: any, key: string) => {
    return store.get(key);
  });

  ipcMain.handle('store:set', (_event: any, key: string, value: any) => {
    store.set(key, value);
    return true;
  });

  ipcMain.handle('utils:openExternal', async (_event: any, url: string) => {
    const { shell } = require('electron');
    try {
      await shell.openExternal(url);
    } catch (error) {
      log.error(`Error abriendo URL externa: ${url}`, error);
      throw error;
    }
  });

  // IPC Handlers para actualización automática
  ipcMain.handle('updater:checkForUpdates', async () => {
    if (!appUpdater) return { available: false };
    return await appUpdater.checkForUpdates();
  });

  ipcMain.handle('updater:downloadUpdate', async () => {
    if (!appUpdater) return false;
    return await appUpdater.downloadUpdate();
  });

  ipcMain.handle('updater:installUpdate', () => {
    if (appUpdater) {
      appUpdater.quitAndInstall();
    }
  });

  ipcMain.handle('updater:openDownloadPage', () => {
    if (appUpdater) {
      appUpdater.openDownloadPage();
    }
  });

  createWindow();
  startPythonBackend();

  // Inicializar sistema de actualizaciones
  appUpdater = new AppUpdater(mainWindow, isDev);

  // Verificar actualizaciones 5 segundos después del inicio (solo en producción)
  if (!isDev) {
    setTimeout(() => {
      if (appUpdater) {
        appUpdater.checkForUpdates();
      }
    }, 5000);
  }
});

app.on('window-all-closed', () => {
  // Siempre cerrar la aplicación cuando se cierra la ventana
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  if (pythonProcess && pythonProcess.exitCode === null) {
    pythonProcess.kill();
  }
});

// Manejo de errores globales
process.on('uncaughtException', (error) => {
  log.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (error) => {
  log.error('Unhandled Rejection:', error);
});
