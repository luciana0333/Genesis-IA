import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// El backend Python (server.py) expone la API en el puerto 8000.
// Se puede apuntar a otro host con GENESIS_API_URL=http://host:puerto.
const API_URL = process.env.GENESIS_API_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API_URL, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
  },
});
