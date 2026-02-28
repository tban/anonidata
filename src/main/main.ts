const { app, BrowserWindow, ipcMain, dialog, session, nativeImage, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
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
let pythonBackendReady: boolean = false;
let appUpdater: AppUpdater | null = null;

function createApplicationMenu() {
  const template: any[] = [
    {
      label: 'AnoniData',
      submenu: [
        {
          label: 'Acerca de AnoniData',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.send('show-about-modal');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Salir',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

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
    icon: isDev
      ? path.join(app.getAppPath(), 'build/icon.icns')
      : path.join((process as any).resourcesPath, '../icon.icns'),
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

    // Configurar icono del Dock en macOS después de que la ventana esté lista
    if (process.platform === 'darwin' && app.dock) {
      // Usar PNG en desarrollo ya que es más compatible con nativeImage
      const iconPath = isDev
        ? path.join(__dirname, '../../build/icon.png')
        : path.join((process as any).resourcesPath, '../icon.icns');

      log.info(`Intentando cargar icono del Dock desde: ${iconPath}`);

      try {
        const iconImage = nativeImage.createFromPath(iconPath);
        if (!iconImage.isEmpty()) {
          app.dock.setIcon(iconImage);
          log.info(`✓ Icono del Dock configurado correctamente`);
        } else {
          log.error(`Error: nativeImage está vacío para: ${iconPath}`);
        }
      } catch (error) {
        log.error('Error configurando icono del Dock:', error);
      }
    }
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

// Iniciar proceso Python y esperar señal READY
function startPythonBackend(): Promise<ChildProcessType> {
  return new Promise((resolve, reject) => {
    const backendExe = process.platform === 'win32' ? 'anonidata-backend.exe' : 'anonidata-backend';
    const pythonPath = isDev
      ? path.join(app.getAppPath(), 'backend/main.py')
      : path.join((process as any).resourcesPath, backendExe);

    log.info(`Iniciando backend Python: ${pythonPath}`);
    log.info(`Plataforma: ${process.platform}, isDev: ${isDev}`);

    const pythonExecutable = isDev
      ? (process.platform === 'win32'
        ? path.join(app.getAppPath(), 'backend/venv/Scripts/python.exe')
        : path.join(app.getAppPath(), 'backend/venv/bin/python3'))
      : pythonPath;
    const args = isDev ? [pythonPath] : [];

    // Verificar que el ejecutable existe antes de intentar spawn
    if (!fs.existsSync(pythonExecutable)) {
      const errorMsg = `Backend no encontrado en: ${pythonExecutable}`;
      log.error(errorMsg);

      // Listar contenido de resourcesPath para diagnóstico
      if (!isDev) {
        try {
          const resourceFiles = fs.readdirSync((process as any).resourcesPath);
          log.error(`Contenido de resourcesPath: ${JSON.stringify(resourceFiles)}`);
        } catch (e) {
          log.error('No se pudo listar resourcesPath');
        }
      }

      reject(new Error(errorMsg));
      return;
    }

    log.info(`Ejecutando: ${pythonExecutable} ${args.join(' ')}`);

    pythonProcess = spawn(pythonExecutable, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let readyReceived = false;
    let stdoutBuffer = '';

    // Timeout de 2 minutos para inicio (necesario para Windows con PyInstaller)
    const startupTimeout = setTimeout(() => {
      if (!readyReceived) {
        log.error('Timeout esperando inicio del backend Python (2 minutos)');
        reject(new Error('Backend Python no respondió en 2 minutos'));
      }
    }, 120000);

    if (pythonProcess.stdout) {
      pythonProcess.stdout.on('data', (data: Buffer) => {
        const output = data.toString();
        stdoutBuffer += output;

        // Intentar parsear cada línea como JSON
        const lines = stdoutBuffer.split('\n');
        stdoutBuffer = lines.pop() || ''; // Guardar última línea incompleta

        for (const line of lines) {
          if (line.trim()) {
            try {
              const json = JSON.parse(line);
              // Detectar señal READY
              if (json.status === 'ready' && !readyReceived) {
                readyReceived = true;
                pythonBackendReady = true;
                clearTimeout(startupTimeout);
                log.info('✓ Backend Python listo y esperando solicitudes');
                resolve(pythonProcess);
              }
            } catch (e) {
              // No es JSON, solo log normal
              log.info(`[Python] ${line}`);
            }
          }
        }
      });
    }

    if (pythonProcess.stderr) {
      pythonProcess.stderr.on('data', (data: Buffer) => {
        log.error(`[Python Error] ${data.toString()}`);
      });
    }

    pythonProcess.on('close', (code: number) => {
      pythonBackendReady = false;
      log.info(`Proceso Python cerrado con código: ${code}`);
      if (!readyReceived) {
        clearTimeout(startupTimeout);
        reject(new Error(`Backend Python cerrado antes de estar listo (código: ${code})`));
      }
    });

    pythonProcess.on('error', (error: Error) => {
      pythonBackendReady = false;
      clearTimeout(startupTimeout);
      log.error(`Error iniciando backend Python: ${error.message}`);
      reject(error);
    });
  });
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

    return new Promise(async (resolve, reject) => {
      if (!pythonProcess || pythonProcess.exitCode !== null || !pythonBackendReady) {
        try {
          log.info('Iniciando backend Python...');
          await startPythonBackend();
        } catch (error: any) {
          reject(new Error(`Error iniciando backend: ${error.message}`));
          return;
        }
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

    return new Promise(async (resolve, reject) => {
      if (!pythonProcess || pythonProcess.exitCode !== null || !pythonBackendReady) {
        try {
          log.info('Iniciando backend Python...');
          await startPythonBackend();
        } catch (error: any) {
          reject(new Error(`Error iniciando backend: ${error.message}`));
          return;
        }
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
    async (_event: any, originalFile: string, detectionsPath: string, approvedIndices: number[], options?: { isImagePdf?: boolean }) => {
      log.info(`Finalizando anonimización para: ${originalFile} (Es PDF imagen: ${options?.isImagePdf})`);

      return new Promise(async (resolve, reject) => {
        if (!pythonProcess || pythonProcess.exitCode !== null || !pythonBackendReady) {
          try {
            log.info('Iniciando backend Python...');
            await startPythonBackend();
          } catch (error: any) {
            reject(new Error(`Error iniciando backend: ${error.message}`));
            return;
          }
        }

        const request = {
          action: 'finalize_anonymization',
          originalFile: originalFile,
          detectionsPath: detectionsPath,
          approvedIndices: approvedIndices,
          isImagePdf: options?.isImagePdf,
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

  ipcMain.handle('utils:deleteFile', async (_event: any, filePath: string) => {
    const fs = require('fs').promises;
    try {
      await fs.unlink(filePath);
      log.info(`Archivo eliminado: ${filePath}`);
      return true;
    } catch (error: any) {
      log.error(`Error eliminando archivo ${filePath}:`, error.message);
      return false;
    }
  });

  ipcMain.handle('utils:readPdfFile', async (_event: any, filePath: string) => {
    const fs = require('fs').promises;
    try {
      log.info(`Leyendo archivo PDF: ${filePath}`);
      const buffer = await fs.readFile(filePath);
      // Convertir Buffer de Node.js a ArrayBuffer para el renderer
      return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    } catch (error: any) {
      log.error(`Error leyendo archivo PDF ${filePath}:`, error.message);
      throw error;
    }
  });

  ipcMain.handle('utils:checkPdfType', async (_event: any, filePath: string) => {
    log.info(`Verificando tipo PDF: ${filePath}`);

    return new Promise(async (resolve, reject) => {
      if (!pythonProcess || pythonProcess.exitCode !== null || !pythonBackendReady) {
        try {
          await startPythonBackend();
        } catch (error: any) {
          reject(new Error(`Error iniciando backend: ${error.message}`));
          return;
        }
      }

      const request = {
        action: 'check_pdf_type',
        files: [filePath], // Backend espera lista
      };

      if (pythonProcess.stdin) {
        pythonProcess.stdin.write(JSON.stringify(request) + '\n');
      }

      let resolved = false;

      const dataHandler = (data: Buffer) => {
        if (resolved) return;

        const chunk = data.toString();
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.trim() && line.includes('{') && line.includes('"success"')) {
            try {
              const response = JSON.parse(line);
              // Verificar si es respuesta a nuestro tipo de mensaje (check_pdf_type devuelve results con 'type')
              // O simplente confiamos en el orden si no hay concurrencia masiva.
              // Como la comunicación es FIFO y el backend procesa secuencial, esto está bien por ahora.
              // Pero check_pdf_type devuelve success y results.
              if (response.success !== undefined) {
                // Si es el mensaje ready inicial o un log, ignoramos si no cuadra?
                // El backend responde 1 a 1.

                resolved = true;
                if (pythonProcess.stdout) {
                  pythonProcess.stdout.removeListener('data', dataHandler);
                }

                if (response.success && response.results && response.results.length > 0) {
                  resolve(response.results[0].type); // Retornar solo 'text' o 'image'
                } else if (!response.success) {
                  // Si falló backend, retornamos error o default? 
                  // Mejor reject para manejar fallback en frontend si se quiere
                  reject(new Error(response.error || 'Backend error'));
                } else {
                  // success true pero results vacio?
                  reject(new Error('Respuesta vacía del backend'));
                }
                return;
              }
            } catch (e) {
              // ignore
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
          reject(new Error('Timeout verificando tipo PDF'));
        }
      }, 30000); // 30s timeout
    });
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
  createApplicationMenu();
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
