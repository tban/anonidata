import { invoke } from '@tauri-apps/api/core';
import { open, message } from '@tauri-apps/plugin-dialog';
import { openUrl } from '@tauri-apps/plugin-opener';
import { load } from '@tauri-apps/plugin-store';
import { listen } from '@tauri-apps/api/event';

export const anonidata = {
  dialog: {
    openFile: async (): Promise<string[]> => {
      const result = await open({
        multiple: true,
        filters: [{ name: 'PDF', extensions: ['pdf'] }]
      });
      if (!result) return [];
      if (typeof result === 'string') return [result];
      return result;
    },
    showInfo: async (msg: string, title?: string): Promise<boolean> => {
      await message(msg, { title: title || 'Información', kind: 'warning' });
      return true;
    },
  },

  process: {
    anonymize: (files: string[], options?: any) =>
      invoke<any>('anonymize', { files, options }),
    detectOnly: (filePath: string, options?: any) =>
      invoke<any>('detect_only', { filePath, options }),
    finalizeAnonymization: (
      originalFile: string,
      detectionsPath: string,
      approvedIndices: number[],
      options?: any
    ) =>
      invoke<any>('finalize_anonymization', {
        originalFile, detectionsPath, approvedIndices, options
      }),
  },

  review: {
    loadDetections: (path: string) =>
      invoke<any>('load_detections', { path }),
    saveDetections: (path: string, detections: any[]) =>
      invoke<boolean>('save_detections', { path, detections }),
  },

  app: {
    getVersion: () => invoke<string>('get_app_version'),
  },

  store: {
    get: async (key: string) => {
      const store = await load('settings.json', { autoSave: true });
      return store.get(key);
    },
    set: async (key: string, value: any) => {
      const store = await load('settings.json', { autoSave: true });
      await store.set(key, value);
      await store.save();
      return true;
    },
  },

  utils: {
    openExternal: (url: string) => openUrl(url),
    deleteFile: (path: string) => invoke<boolean>('delete_file', { path }),
    readPdfFile: (path: string) => invoke<ArrayBuffer>('read_pdf_file', { path }),
    checkPdfType: (path: string) => invoke<any>('check_pdf_type', { path }),
    applyOcr: (path: string, language: string) => invoke<any>('apply_ocr', { path, language }),
    restartBackend: () => invoke<boolean>('restart_backend'),
    getFileSize: (path: string) => invoke<number>('get_file_size', { path }),
    fetchUrlBackend: (url: string) => invoke<any>('fetch_url_backend', { url }),
  },
};

// Re-export listen for event subscriptions
export { listen } from '@tauri-apps/api/event';
export { platform } from '@tauri-apps/plugin-os';
