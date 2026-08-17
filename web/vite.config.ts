import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/* Build straight into ../static, which the FastAPI app already serves and the
 * Dockerfile already copies. The deployment story does not change: there is
 * still one container serving one directory. */
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../static',
    emptyOutDir: true,
    /* The page is opened by an 80-year-old on a mid-range Android phone over
     * Malaysian mobile data. One file, no chunk waterfall. */
    rollupOptions: { output: { manualChunks: undefined } },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8100',
      '/ws': { target: 'ws://127.0.0.1:8100', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
} as Parameters<typeof defineConfig>[0]);
