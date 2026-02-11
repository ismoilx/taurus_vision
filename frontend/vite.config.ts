import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  
  server: {
    host: '0.0.0.0', // Allow external connections (Docker)
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true, // Required for Docker on some systems
    },
  },
  
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
})
