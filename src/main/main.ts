const { app, BrowserWindow, ipcMain, dialog, session } = require('electron');
const path = require('path');
const log = require('electron-log');
const Store = require('electron-store');
const { spawn } = require('child_process');

// Types
type BrowserWindowType = any;
type ChildProcessType = any;

// Simple isDev check - verificar si está empaquetado
const isDev = !app.isPackaged;

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
      sandbox: true,
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

  createWindow();
  startPythonBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
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
