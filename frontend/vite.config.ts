import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Vite Configuration — Universal (local + Docker + production)
 *
 * MUHIT STRATEGIYASI:
 *   Barcha muhitlarda VITE_API_URL="" (bo'sh) — brauzer /api/... ga nisbiy so'rov yuboradi.
 *   Dev server / Nginx uni backend ga proksi qiladi.
 *
 *   ┌─────────────────────────────────────────────────────────────────┐
 *   │ Muhit         │ Browser URL │ Proksi                            │
 *   ├─────────────────────────────────────────────────────────────────┤
 *   │ Lokal dev     │ localhost   │ Vite → http://localhost:8000      │
 *   │ Docker dev    │ localhost   │ Vite → http://backend:8000        │
 *   │ Server dev    │ zxzx.uz     │ Nginx → http://backend:8000       │
 *   │ Production    │ zxzx.uz     │ Nginx → http://backend:8000       │
 *   └─────────────────────────────────────────────────────────────────┘
 *
 * ENV SOZLASH:
 *   BACKEND_URL     — Vite proksi uchun backend manzili (VITE_ prefiksi YO'Q — bundledan tashqari)
 *                     Docker: "http://backend:8000"   Lokal: "http://localhost:8000"
 *   VITE_HMR_CLIENT_PORT — Faqat HTTPS proksi orqali ishlaganda kerak (server: 443)
 *
 * Optimizatsiyalar:
 *   1. manualChunks: React, Recharts, Lucide alohida vendor chunklarga ajratiladi
 *   2. terser minification: production build hajmi 30-40% kichrayadi
 *   3. cssCodeSplit: CSS ham alohida chunk
 *   4. reportCompressedSize: false → build vaqti tezroq
 */
export default defineConfig(({ mode }) => {
  // process.env ni to'ldirish (docker-compose environment → Node process.env)
  const env = loadEnv(mode, process.cwd(), '');

  // Proksi maqsad: BACKEND_URL → Docker "http://backend:8000", local "http://localhost:8000"
  const backendTarget = env.BACKEND_URL || 'http://localhost:8000';

  // HMR: HTTPS proksi orqali ishlaganda clientPort=443 kerak (masalan, server da Nginx HTTPS)
  // Lokal ishlatganda bu o'rnatilmagan — Vite standart ws:// ishlatadi
  const hmrConfig = env.VITE_HMR_CLIENT_PORT
    ? { clientPort: parseInt(env.VITE_HMR_CLIENT_PORT, 10), protocol: 'wss' as const }
    : true;

  return {
  plugins: [react()],

  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    hmr: hmrConfig,

    // ── Proksi: barcha API va WS so'rovlarini backend ga yo'naltiradi ──────
    // Bu faqat Vite DEV SERVER uchun ishlaydi (npm run dev / Docker dev).
    // Production build da Nginx nginx.conf orqali bir xil ishni bajaradi.
    proxy: {
      // REST API
      '/api': {
        target:      backendTarget,
        changeOrigin: true,
        secure:       false,
      },
      // WebSocket (live feed)
      '/ws': {
        target:      backendTarget.replace(/^http/, 'ws'),
        changeOrigin: true,
        ws:           true,
      },
      // Health check va metrics (docs va monitoring uchun)
      '/health': {
        target:      backendTarget,
        changeOrigin: true,
      },
      '/docs': {
        target:      backendTarget,
        changeOrigin: true,
      },
      '/metrics': {
        target:      backendTarget,
        changeOrigin: true,
      },
    },
  },

  build: {
    // Terser — production uchun eng kichik bundle
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,   // console.log larni olib tashlaydi (production)
        drop_debugger: true,
      },
    },

    // CSS ham alohida chunklarga bo'linadi
    cssCodeSplit: true,

    // Build vaqtini tezlashtiradi
    reportCompressedSize: false,

    // Chunk bo'lish strategiyasi
    rollupOptions: {
      output: {
        // Vendor chunklar: browser ular o'zgarmasa cache-dan foydalanadi
        manualChunks: {
          // React core — eng kam o'zgaradigan kutubxona
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Charts — katta kutubxona, alohida chunk
          'vendor-charts': ['recharts'],
          // Icons — yaxshi bo'linmasa 200KB+ bo'lishi mumkin
          'vendor-icons': ['lucide-react'],
        },

        // Chunk fayl nomlari (hash bilan — long-term cache)
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },

    // Chunk hajmi limiti (kB) — katta bo'lsa ogohlantiradi
    chunkSizeWarningLimit: 600,
  },
  }; // ← defineConfig callback return
});