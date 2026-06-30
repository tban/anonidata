import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Leer versión del package.json
const packageJson = require('./package.json');

// Leer número de build de version_local.json (temporal, inyectado por el script de build)
let buildNumber = 0;
try {
  const versionLocal = require('./src/version_local.json');
  buildNumber = versionLocal.build || 0;
} catch (e) {
  // En desarrollo/dev, el archivo temporal local no existirá, se asume 0
  buildNumber = 0;
}

export default defineConfig({
  plugins: [react()],
  base: './',
  publicDir: 'public',
  build: {
    outDir: 'dist/renderer',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        // No generar polyfills para process, global, etc.
        inlineDynamicImports: false,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@renderer': path.resolve(__dirname, './src/renderer'),
    },
  },
  server: {
    port: 3000,
    strictPort: true,
  },
  define: {
    '__APP_VERSION__': JSON.stringify(packageJson.version),
    '__BUILD_NUMBER__': buildNumber,
    // Generar fecha de compilación en el momento de define (se ejecuta cada vez que se hace build)
    '__BUILD_DATE__': JSON.stringify(new Date().toLocaleString('es-ES', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })),
    // Proveer variables globales para compatibilidad con librerías
    'process.env.NODE_ENV': JSON.stringify('production'),
    'global': 'globalThis',
  },
});
