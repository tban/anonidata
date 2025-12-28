const { contextBridge, ipcRenderer, webUtils } = require('electron');

// Tipos para TypeScript
export interface AnoniDataAPI {
  dialog: {
    openFile: () => Promise<string[]>;
    showInfo: (message: string, title?: string) => Promise<boolean>;
  };
  process: {
    anonymize: (files: string[]) => Promise<ProcessResult>;
    detectOnly: (filePath: string, options?: { skipDetection?: boolean }) => Promise<DetectOnlyResult>;
    finalizeAnonymization: (
      originalFile: string,
      detectionsPath: string,
      approvedIndices: number[],
      options?: { isImagePdf?: boolean }
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
    deleteFile: (filePath: string) => Promise<boolean>;
    readPdfFile: (filePath: string) => Promise<ArrayBuffer>;
    checkPdfType: (filePath: string) => Promise<'text' | 'image'>;
  };
  updater: {
    checkForUpdates: () => Promise<UpdateInfo>;
    downloadUpdate: () => Promise<boolean>;
    installUpdate: () => Promise<void>;
    openDownloadPage: () => Promise<void>;
    onUpdateAvailable: (callback: (info: UpdateAvailableInfo) => void) => void;
    onDownloadProgress: (callback: (progress: DownloadProgress) => void) => void;
    onUpdateDownloaded: (callback: (info: UpdateDownloadedInfo) => void) => void;
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
  warnings?: string[];
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
  warnings?: string[];
}

export interface LoadDetectionsResult {
  success: boolean;
  detections?: any[];
  error?: string;
}

export interface UpdateInfo {
  available: boolean;
  version?: string;
  downloadUrl?: string;
  releaseNotes?: string;
}

export interface UpdateAvailableInfo {
  version: string;
  releaseNotes?: string;
}

export interface DownloadProgress {
  percent: number;
  transferred: number;
  total: number;
}

export interface UpdateDownloadedInfo {
  version: string;
}

// Exponer API segura al renderer
const api: AnoniDataAPI = {
  dialog: {
    openFile: () => ipcRenderer.invoke('dialog:openFile'),
    showInfo: (message: string, title?: string) => ipcRenderer.invoke('dialog:showInfo', message, title),
  },
  process: {
    anonymize: (files: string[]) => ipcRenderer.invoke('process:anonymize', files),
    detectOnly: (filePath: string, options?: { skipDetection?: boolean }) => ipcRenderer.invoke('process:detectOnly', filePath, options),
    finalizeAnonymization: (originalFile: string, detectionsPath: string, approvedIndices: number[], options?: { isImagePdf?: boolean }) =>
      ipcRenderer.invoke('process:finalizeAnonymization', originalFile, detectionsPath, approvedIndices, options),
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
    deleteFile: (filePath: string) => ipcRenderer.invoke('utils:deleteFile', filePath),
    readPdfFile: (filePath: string) => ipcRenderer.invoke('utils:readPdfFile', filePath),
    checkPdfType: (filePath: string) => ipcRenderer.invoke('utils:checkPdfType', filePath),
  },
  updater: {
    checkForUpdates: () => ipcRenderer.invoke('updater:checkForUpdates'),
    downloadUpdate: () => ipcRenderer.invoke('updater:downloadUpdate'),
    installUpdate: () => ipcRenderer.invoke('updater:installUpdate'),
    openDownloadPage: () => ipcRenderer.invoke('updater:openDownloadPage'),
    onUpdateAvailable: (callback: (info: UpdateAvailableInfo) => void) => {
      ipcRenderer.on('updater:update-available', (_event: any, info: UpdateAvailableInfo) => callback(info));
    },
    onDownloadProgress: (callback: (progress: DownloadProgress) => void) => {
      ipcRenderer.on('updater:download-progress', (_event: any, progress: DownloadProgress) => callback(progress));
    },
    onUpdateDownloaded: (callback: (info: UpdateDownloadedInfo) => void) => {
      ipcRenderer.on('updater:update-downloaded', (_event: any, info: UpdateDownloadedInfo) => callback(info));
    },
  },
};

// Inyectar webUtils directamente para que funcione con drag & drop
contextBridge.exposeInMainWorld('electronWebUtils', {
  getPathForFile: (file: File) => webUtils.getPathForFile(file),
});

// Exponer ipcRenderer para escuchar eventos del menú
contextBridge.exposeInMainWorld('electron', {
  ipcRenderer: {
    on: (channel: string, func: (...args: any[]) => void) => {
      ipcRenderer.on(channel, (_event: any, ...args: any[]) => func(...args));
    },
    removeListener: (channel: string, func: (...args: any[]) => void) => {
      ipcRenderer.removeListener(channel, func);
    },
  },
});

contextBridge.exposeInMainWorld('anonidata', api);

// Declaración global para TypeScript
declare global {
  interface Window {
    anonidata: AnoniDataAPI;
    electronWebUtils: {
      getPathForFile: (file: File) => string;
    };
    electron: {
      ipcRenderer: {
        on: (channel: string, func: (...args: any[]) => void) => void;
        removeListener: (channel: string, func: (...args: any[]) => void) => void;
      };
    };
  }

  // Extender File para incluir la propiedad path de Electron
  interface File {
    path?: string;
  }
}
