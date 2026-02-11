<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { ChevronLeft, Home, LogOut, Settings } from 'lucide-vue-next'
import NotificationBell from '@/components/NotificationBell.vue'

const router = useRouter()
const route = useRoute()
const isHome = computed(() => route.path === '/')
const { logout } = useAuth()
</script>

<template>
  <div class="flex flex-col min-h-screen bg-background text-foreground bg-grid">
    <header class="fixed top-0 left-0 right-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
      <div class="max-w-7xl mx-auto flex h-16 items-center px-4 sm:px-6 lg:px-8">
        <div class="mr-4 flex gap-2" v-if="!isHome">
          <Button variant="ghost" size="icon" @click="router.back()">
            <ChevronLeft class="h-5 w-5" />
            <span class="sr-only">Back</span>
          </Button>
          <Button variant="ghost" size="icon" as-child>
            <NuxtLink to="/">
              <Home class="h-5 w-5" />
              <span class="sr-only">Home</span>
            </NuxtLink>
          </Button>
        </div>
        <div class="flex-1" />
        <div class="flex items-center gap-2">
          <NotificationBell />
          <Button variant="ghost" size="icon" @click="logout">
            <LogOut class="h-5 w-5" />
            <span class="sr-only">退出登录</span>
          </Button>
          <Button variant="ghost" size="icon">
            <Settings class="h-5 w-5" />
            <span class="sr-only">Settings</span>
          </Button>
        </div>
      </div>
    </header>
    <main class="flex-1 pt-16">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <slot />
      </div>
    </main>
  </div>
</template>

<style scoped>
:global(html) {
  overflow-x: hidden;
}

:global(body) {
  margin: 0;
  padding: 0;
  overflow-x: hidden;
  overflow-y: auto;
}
</style>
