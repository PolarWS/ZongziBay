import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  devtools: { enabled: false },
  app: {
    head: {
      title: 'ZongziBay'
    }
  },
  ssr: false,
  css: ['~/assets/css/tailwind.css', 'vue-sonner/style.css'],
  vite: {
    plugins: [
      tailwindcss(),
    ],
  },
  modules: [
    'shadcn-nuxt'
  ],
  shadcn: {
    prefix: '',
    componentDir: '@/components/ui'
  },
  devServer: {
    host: '0.0.0.0',
    port: 3001
  },
  compatibilityDate: '2025-05-15'
})