import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Vite Configuration — Production Optimized
 *
 * Optimizatsiyalar:
 *   1. manualChunks: React, Recharts, Lucide alohida vendor chunklarga ajratiladi
 *      → browser ular o'zgarmasa cache-dan oladi (long-term caching)
 *   2. terser minification: production build hajmi 30-40% kichrayadi
 *   3. modulePreload: sahifa ochilganda kerakli chunklar oldindan so'ralib turadi
 *   4. cssCodeSplit: CSS ham alohida chunk — faqat keraklisi yuklanadi
 *   5. reportCompressedSize: false → build vaqti tezroq
 */
export default defineConfig({
  plugins: [react()],

  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    hmr: {
      clientPort: 443,
      protocol: 'wss',
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
});