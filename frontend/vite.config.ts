import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  
  server: {
    host: '0.0.0.0', // Docker ichida tashqi so'rovlarni qabul qilish uchun
    port: 5173,      // Cloudflare Tunnel yo'naltirilgan port
    strictPort: true,
    
    // MUAMMONI HAL QILUVCHI ASOSIY QISM:
    allowedHosts: [
      'zxzx.uz',     // Sizning domeningiz
      '.zxzx.uz'    // Barcha subdomenlar (masalan, api.zxzx.uz) uchun
    ],
    
    watch: {
      usePolling: true, // Ubuntu/Docker'da fayl o'zgarishlarini sezish uchun
    },
  },
  
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
})