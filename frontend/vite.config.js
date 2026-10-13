import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Las llamadas a /api se redirigen al backend Flask (puerto 5000)
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:5000' } },
})
