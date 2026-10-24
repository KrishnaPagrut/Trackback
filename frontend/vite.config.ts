import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: Object.fromEntries(
      ['/api', '/r', '/tm', '/tg', '/m', '/pings', '/challenges', '/.well-known/trackback']
        .map(path => [path, 'http://127.0.0.1:8000']),
    ),
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
