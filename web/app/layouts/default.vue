<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { ChevronLeft, Home, LogOut, Settings } from 'lucide-vue-next'
import NotificationBell from '@/components/NotificationBell.vue'

const router = useRouter()
const route = useRoute()
const isHome = computed(() => route.path === '/')
const { logout } = useAuth()
const { showZongzibayChan, init: initChan } = useZongzibayChan()
onMounted(() => { initChan() })
</script>

<template>
  <div class="relative flex flex-col min-h-screen bg-background text-foreground bg-grid">
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
          <Button variant="ghost" size="icon" as-child>
            <NuxtLink to="/settings">
              <Settings class="h-5 w-5" />
              <span class="sr-only">Settings</span>
            </NuxtLink>
          </Button>
        </div>
      </div>
    </header>
    <main class="flex-1 pt-16 relative z-[1]">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <slot />
      </div>
    </main>

    <!-- 右下角角色图片 -->
    <img
      v-if="showZongzibayChan"
      src="~/assets/img/zongzibay-chan-01.png"
      alt="zongzibay-chan"
      class="character-img"
    />
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

/* 右下角角色图片 */
.character-img {
  position: fixed;
  bottom: 0;
  right: 0;
  max-height: 28vh;
  max-width: 20vw;
  width: auto;
  height: auto;
  object-fit: contain;
  pointer-events: none;
  z-index: 0;
  opacity: 0.95;
  transition: opacity 0.3s ease, transform 0.3s ease;
  filter: drop-shadow(0 0 20px rgba(0, 0, 0, 0.05));
}

@media (max-width: 640px) {
  .character-img {
    max-height: 22vh;
    max-width: 30vw;
    opacity: 0.5;
  }
}
</style>
