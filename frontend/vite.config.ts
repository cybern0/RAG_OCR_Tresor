import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import { defineConfig, loadEnv } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss(), babel({ presets: [reactCompilerPreset()] })],
    server: {
      // En développement, /api est relayé tel quel vers FastAPI (l'API vit sous /api) : pas de CORS à gérer.
      // Autre port ou autre machine : VITE_PROXY_TARGET=http://localhost:3000 npm run dev
      proxy: { '/api': { target: env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true } },
    },
    build: {
      rollupOptions: {
        output: {
          // bibliothèques stables dans un fichier à part : mieux mises en cache entre deux livraisons
          manualChunks: (id: string) => (id.includes('node_modules') ? (/react-router|@remix-run/.test(id) ? 'router' : /@tanstack/.test(id) ? 'query' : undefined) : undefined),
        },
      },
    },
  }
})
