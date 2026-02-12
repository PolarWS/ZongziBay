<script setup lang="ts">
import type { NuxtError } from '#app'
import { Home, ArrowLeft } from 'lucide-vue-next'

const props = defineProps<{ error: NuxtError }>()

const status = computed(() => props.error.statusCode ?? props.error.status ?? 500)
const message = computed(() =>
  props.error.statusMessage ?? props.error.statusText ?? '出了点问题'
)

const statusLabel = computed(() => {
  const code = status.value
  if (code === 404) return '页面未找到'
  if (code >= 500) return '服务器错误'
  if (code >= 400) return '请求错误'
  return '错误'
})

const router = useRouter()

function goBack() {
  clearError()
  router.back()
}
</script>

<template>
  <NuxtLayout name="default">
    <div class="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-4 pt-16">
      <div class="text-center">
        <h1 class="text-[10rem] font-bold leading-none tabular-nums text-foreground/90 tracking-tighter">
          {{ status }}
        </h1>
        <p class="mt-2 text-lg font-medium text-foreground">{{ statusLabel }}</p>
        <p v-if="message" class="mt-1 text-sm text-muted-foreground">{{ message }}</p>
        <!-- <div class="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:gap-4">
          <NuxtLink
            to="/"
            class="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Home class="h-4 w-4" />
            返回首页
          </NuxtLink>
          <button
            type="button"
            class="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground underline-offset-4 hover:underline hover:text-foreground"
            @click="goBack"
          >
            <ArrowLeft class="h-4 w-4" />
            返回上一页
          </button>
        </div> -->
      </div>
    </div>
  </NuxtLayout>
</template>
