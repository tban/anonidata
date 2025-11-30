const { contextBridge, ipcRenderer, webUtils } = require('electron');

// Tipos para TypeScript
export interface AnoniDataAPI {
  dialog: {
    openFile: () => Promise<string[]>;
  };
  process: {
    anonymize: (files: string[]) => Promise<ProcessResult>;
  };
  app: {
    getVersion: () => Promise<string>;
  };
  store: {
    get: (key: string) => Promise<any>;
    set: (key: string, value: any) => Promise<boolean>;
  };
  utils: {
    getFilePath: (file: File) => string;
  };
}

export interface ProcessResult {
  success: boolean;
  results: FileResult[];
  error?: string;
}

export interface FileResult {
  inputFile: string;
  outputFile: string;
  status: 'success' | 'error';
  stats: {
    dniCount: number;
    nameCount: number;
    addressCount: number;
    phoneCount: number;
    emailCount: number;
    signatureCount: number;
    qrCount: number;
  };
  error?: string;
  processingTime: number;
}

// Exponer API segura al renderer
const api: AnoniDataAPI = {
  dialog: {
    openFile: () => ipcRenderer.invoke('dialog:openFile'),
  },
  process: {
    anonymize: (files: string[]) => ipcRenderer.invoke('process:anonymize', files),
  },
  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
  },
  store: {
    get: (key: string) => ipcRenderer.invoke('store:get', key),
    set: (key: string, value: any) => ipcRenderer.invoke('store:set', key, value),
  },
  utils: {
    getFilePath: (file: File) => webUtils.getPathForFile(file),
  },
};

// Inyectar webUtils directamente para que funcione con drag & drop
contextBridge.exposeInMainWorld('electronWebUtils', {
  getPathForFile: (file: File) => webUtils.getPathForFile(file),
});

contextBridge.exposeInMainWorld('anonidata', api);

// Declaración global para TypeScript
declare global {
  interface Window {
    anonidata: AnoniDataAPI;
    electronWebUtils: {
      getPathForFile: (file: File) => string;
    };
  }

  // Extender File para incluir la propiedad path de Electron
  interface File {
    path?: string;
  }
}
