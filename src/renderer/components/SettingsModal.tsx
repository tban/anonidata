import React, { useState, useEffect } from 'react';
import { anonidata } from '../lib/tauri-bridge';

interface SettingsModalProps {
  onClose: () => void;
  onSettingsSaved: (settings: AppSettings) => void;
}

export interface AppSettings {
  autoCheckUpdates: boolean;
  defaultRedactionStrategy: 'black_box' | 'text_label';
}

const DEFAULT_SETTINGS: AppSettings = {
  autoCheckUpdates: true,
  defaultRedactionStrategy: 'black_box'
};

export const SettingsModal: React.FC<SettingsModalProps> = ({ onClose, onSettingsSaved }) => {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const storedSettings = await anonidata.store.get('app_settings');
        if (storedSettings) {
          setSettings({
            ...DEFAULT_SETTINGS,
            ...(storedSettings as any)
          });
        }
      } catch (error) {
        console.error('Error loading settings:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await anonidata.store.set('app_settings', settings);
      onSettingsSaved(settings);
      onClose();
    } catch (error) {
      console.error('Error saving settings:', error);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-stone-900 border border-stone-800 rounded-2xl p-6 shadow-2xl max-w-md w-full glass-dark">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-stone-100 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-teal-500">
              <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
            Preferencias
          </h2>
          <button
            onClick={onClose}
            className="text-stone-400 hover:text-white transition-colors p-1"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="space-y-6">
          {/* Opciones Generales */}
          <div className="bg-stone-950/50 p-4 rounded-xl border border-stone-800/80">
            <h3 className="text-sm font-semibold text-stone-300 mb-4 uppercase tracking-wider">General</h3>
            
            <div className="flex items-center justify-between">
              <label className="flex items-start gap-3 cursor-pointer group flex-1">
                <div className="relative flex items-center justify-center mt-1">
                  <input
                    type="checkbox"
                    checked={settings.autoCheckUpdates}
                    onChange={(e) => setSettings({ ...settings, autoCheckUpdates: e.target.checked })}
                    className="peer sr-only"
                  />
                  <div className="w-5 h-5 rounded border border-stone-600 bg-stone-900 peer-checked:bg-teal-500 peer-checked:border-teal-500 transition-colors"></div>
                  <svg className="absolute w-3 h-3 text-white pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity" viewBox="0 0 14 10" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1 5L4.5 8.5L13 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <div>
                  <div className="text-sm font-medium text-stone-200 group-hover:text-teal-400 transition-colors">
                    Buscar actualizaciones automáticamente
                  </div>
                  <div className="text-xs text-stone-400 mt-0.5">
                    Verifica si hay nuevas versiones disponibles al iniciar la aplicación.
                  </div>
                </div>
              </label>

              <button
                type="button"
                onClick={() => {
                  anonidata.app.checkUpdatesManual().catch((e) => console.error("Error checking updates manually:", e));
                  onClose();
                }}
                className="ml-4 px-3 py-1.5 text-xs font-medium text-teal-400 bg-teal-950/30 border border-teal-900/50 rounded-lg hover:bg-teal-900/50 hover:text-teal-300 transition-all flex items-center gap-1.5 whitespace-nowrap"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-9.5l5.67-5.67"/>
                </svg>
                Comprobar ahora
              </button>
            </div>
          </div>

          {/* Opciones de Anonimización */}
          <div className="bg-stone-950/50 p-4 rounded-xl border border-stone-800/80">
            <h3 className="text-sm font-semibold text-stone-300 mb-4 uppercase tracking-wider">Anonimización por defecto</h3>
            
            <div className="space-y-3">
              <label className="flex items-start gap-3 cursor-pointer group">
                <div className="relative flex items-center justify-center mt-1">
                  <input
                    type="radio"
                    name="redactionStrategy"
                    value="black_box"
                    checked={settings.defaultRedactionStrategy === 'black_box'}
                    onChange={() => setSettings({ ...settings, defaultRedactionStrategy: 'black_box' })}
                    className="peer sr-only"
                  />
                  <div className="w-4 h-4 rounded-full border border-stone-600 bg-stone-900 peer-checked:border-teal-500 transition-colors"></div>
                  <div className="absolute w-2 h-2 rounded-full bg-teal-500 pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity"></div>
                </div>
                <div>
                  <div className="text-sm font-medium text-stone-200 group-hover:text-teal-400 transition-colors">
                    Tachón (Caja negra)
                  </div>
                  <div className="text-xs text-stone-400 mt-0.5">
                    Oculta los datos con un rectángulo opaco (recomendado para imágenes y documentos escaneados).
                  </div>
                </div>
              </label>

              <label className="flex items-start gap-3 cursor-pointer group">
                <div className="relative flex items-center justify-center mt-1">
                  <input
                    type="radio"
                    name="redactionStrategy"
                    value="text_label"
                    checked={settings.defaultRedactionStrategy === 'text_label'}
                    onChange={() => setSettings({ ...settings, defaultRedactionStrategy: 'text_label' })}
                    className="peer sr-only"
                  />
                  <div className="w-4 h-4 rounded-full border border-stone-600 bg-stone-900 peer-checked:border-teal-500 transition-colors"></div>
                  <div className="absolute w-2 h-2 rounded-full bg-teal-500 pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity"></div>
                </div>
                <div>
                  <div className="text-sm font-medium text-stone-200 group-hover:text-teal-400 transition-colors">
                    Texto [ANONIMIZADO]
                  </div>
                  <div className="text-xs text-stone-400 mt-0.5">
                    Reemplaza los datos personales por la palabra [ANONIMIZADO] en texto real.
                  </div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <div className="mt-8 flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-stone-800 text-stone-200 hover:bg-stone-700 rounded-lg transition-colors text-sm font-medium"
            disabled={isSaving}
          >
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-5 py-2 bg-gradient-to-r from-teal-500 to-emerald-600 text-white rounded-lg transition-all hover:shadow-[0_0_15px_rgba(20,184,166,0.4)] hover:scale-[1.02] active:scale-[0.98] text-sm font-semibold flex items-center gap-2"
          >
            {isSaving ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                Guardando...
              </>
            ) : (
              'Guardar Preferencias'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
