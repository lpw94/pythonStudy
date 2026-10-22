import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 对标 admin-web 里的 @/ → src/，vite 需要自己声明
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 必须是 5173：admin-api 的 CORS 白名单只放了 5173，换端口就得改后端 .env
    port: 5173,
    strictPort: true,
    // 显式绑 127.0.0.1：不指定时 Vite 在 Windows 上会只绑 ::1，
    // 导致用 127.0.0.1 访问连不上（后端 CORS 白名单里两个域名都有，显式绑最省事）
    host: '127.0.0.1',
  },
});
