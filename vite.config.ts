import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Leer versión del package.json
const packageJson = require('./package.json');

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist/renderer',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@renderer': path.resolve(__dirname, './src/renderer'),
      '@main': path.resolve(__dirname, './src/main'),
    },
  },
  server: {
    port: 3000,
  },
  define: {
    '__APP_VERSION__': JSON.stringify(packageJson.version),
    // Generar fecha de compilación en el momento de define (se ejecuta cada vez que se hace build)
    '__BUILD_DATE__': JSON.stringify(new Date().toLocaleString('es-ES', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })),
  },
});
