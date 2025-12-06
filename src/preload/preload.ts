const { contextBridge, ipcRenderer, webUtils } = require('electron');

// Tipos para TypeScript
export interface AnoniDataAPI {
  dialog: {
    openFile: () => Promise<string[]>;
    showInfo: (message: string, title?: string) => Promise<boolean>;
  };
  process: {
    anonymize: (files: string[]) => Promise<ProcessResult>;
    detectOnly: (filePath: string) => Promise<DetectOnlyResult>;
    finalizeAnonymization: (
      originalFile: string,
      detectionsPath: string,
      approvedIndices: number[]
    ) => Promise<FinalizeResult>;
  };
  review: {
    loadDetections: (detectionsPath: string) => Promise<LoadDetectionsResult>;
    saveDetections: (detectionsPath: string, detections: any[]) => Promise<boolean>;
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
    openExternal: (url: string) => Promise<void>;
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

export interface DetectOnlyResult {
  success: boolean;
  preAnonymizedPath?: string;
  detectionsPath?: string;
  totalDetections?: number;
  error?: string;
}

export interface FinalizeResult {
  success: boolean;
  anonymizedPath?: string;
  totalApproved?: number;
  totalRejected?: number;
  error?: string;
}

export interface LoadDetectionsResult {
  success: boolean;
  detections?: any[];
  error?: string;
}

// Exponer API segura al renderer
const api: AnoniDataAPI = {
  dialog: {
    openFile: () => ipcRenderer.invoke('dialog:openFile'),
    showInfo: (message: string, title?: string) => ipcRenderer.invoke('dialog:showInfo', message, title),
  },
  process: {
    anonymize: (files: string[]) => ipcRenderer.invoke('process:anonymize', files),
    detectOnly: (filePath: string) => ipcRenderer.invoke('process:detectOnly', filePath),
    finalizeAnonymization: (originalFile: string, detectionsPath: string, approvedIndices: number[]) =>
      ipcRenderer.invoke('process:finalizeAnonymization', originalFile, detectionsPath, approvedIndices),
  },
  review: {
    loadDetections: (detectionsPath: string) => ipcRenderer.invoke('review:loadDetections', detectionsPath),
    saveDetections: (detectionsPath: string, detections: any[]) => ipcRenderer.invoke('review:saveDetections', detectionsPath, detections),
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
    openExternal: (url: string) => ipcRenderer.invoke('utils:openExternal', url),
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
