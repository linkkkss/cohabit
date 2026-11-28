import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    // allow tunnel domains (localhost.run / cloudflared)
    allowedHosts: true,
    // The editor writes atomically through short-lived temp dirs; watching them
    // can raise EBUSY on Windows and take the dev server down.
    watch: {
      ignored: ['**/.*.tmpdir/**', '**/*.tmpdir/**', '**/*.tmp', '**/~$*'],
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    allowedHosts: true,
  },
})
