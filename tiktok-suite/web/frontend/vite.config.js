import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 开发模式代理 /api 到 FastAPI
    proxy: {
      '/api': 'http://127.0.0.1:8790',
    },
  },
  build: {
    outDir: 'dist',
  },
});
