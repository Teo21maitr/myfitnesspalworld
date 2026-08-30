import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
// `defineConfig` de Vitest étend celui de Vite avec la clé `test`.
import { defineConfig } from 'vitest/config'

/**
 * L'adresse de l'API est figée **dans le bundle** au moment de la
 * construction : elle ne se corrige pas ensuite, elle se reconstruit.
 *
 * Sans cette garde, `npm run build` sans `VITE_API_BASE_URL` produit un bundle
 * parfaitement valide qui appelle `http://localhost:8001` — c'est-à-dire qui ne
 * parle qu'à la machine du développeur. Rien n'échoue, ni à la construction, ni
 * au démarrage : l'application se charge et chaque requête tombe.
 *
 * C'est le seul instant où ce défaut est rattrapable.
 */
/**
 * Relais de l'API, pour que le développement se comporte comme la production.
 *
 * En production, nginx sert l'application **et** relaie `/api/` vers le
 * backend : tout vit sous une seule origine. Sans le même relais ici, le
 * développement resterait la seule configuration à parler à deux origines —
 * exactement l'écart qui a laissé passer trois pannes de cookies jusqu'en
 * production.
 */
const apiProxy = {
  '/api': {
    target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8001',
    changeOrigin: true,
  },
}

export default defineConfig(() => {
  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
        manifest: {
          name: 'MyFitnessPalworld',
          short_name: 'MFPworld',
          description: 'Suivi alimentaire et nutritionnel',
          lang: 'fr',
          dir: 'ltr',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#ffffff',
          theme_color: '#1d4ed8',
          icons: [
            { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
            { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
            {
              src: 'pwa-maskable-512x512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
        },
        workbox: {
          // L'app shell est mise en cache pour rester consultable hors ligne ;
          // aucune écriture métier n'est possible sans réseau (spec 01 §25).
          globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
          navigateFallback: '/index.html',
        },
        devOptions: {
          enabled: false,
        },
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      // Nécessaire pour que le HMR fonctionne depuis un conteneur Docker.
      watch: { usePolling: process.env.DOCKER === 'true' },
      proxy: apiProxy,
    },
    // `vite preview` sert le bundle construit — c'est lui que Playwright
    // interroge. Il a sa propre configuration de relais.
    preview: { proxy: apiProxy },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      restoreMocks: true,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      // `e2e/` appartient à Playwright : ses specs ne doivent pas être
      // collectées par Vitest.
      exclude: ['node_modules', 'dist', 'dev-dist', 'e2e'],
    },
  }
})
