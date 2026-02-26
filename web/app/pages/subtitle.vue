<script setup lang="ts">
import { assrtSearch } from '@/api/assrt'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const items = ref<API.AssrtSubItem[]>([])
const errMsg = ref<string | null>(null)
const inputKeyword = ref('')

const q = computed(() => (route.query.q as string) || '')
const tmdbName = computed(() => (route.query.tmdbName as string) || '')
const tmdbYear = computed(() => (route.query.tmdbYear as string) || '')

watch(() => q.value, (v) => {
  inputKeyword.value = v
  fetchData()
}, { immediate: false })

onMounted(() => {
  inputKeyword.value = q.value
  if (q.value.trim()) fetchData()
})

async function fetchData() {
  const query = q.value.trim()
  if (!query) {
    items.value = []
    return
  }
  loading.value = true
  errMsg.value = null
  try {
    const res = await assrtSearch({ q: query, cnt: 15 })
    const data = (res as any)?.data
    items.value = data?.items ?? []
  } catch (e: any) {
    errMsg.value = e?.message || '搜索失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

function onSearch() {
  const v = inputKeyword.value.trim()
  if (!v) return
  router.replace({ path: '/subtitle', query: { q: v, tmdbName: tmdbName.value, tmdbYear: tmdbYear.value } })
}

/** 点击字幕结果：跳转到 magnet 页，文件列表由 ASSRT 详情接口提供（不用 qB 解析） */
function goToMagnet(it: API.AssrtSubItem) {
  router.push({
    path: '/magnet',
    query: {
      subtitleId: String(it.id),
      tmdbName: tmdbName.value || (it.native_name ?? ''),
      tmdbYear: tmdbYear.value,
    },
  })
}
</script>

<template>
  <div class="px-2 md:px-0">
    <div class="flex flex-col gap-4 mb-4">
      <h1 class="text-lg font-semibold truncate min-w-0">ASSRT 字幕站 字幕</h1>
      <form class="flex gap-2" @submit.prevent="onSearch">
        <Input
          v-model="inputKeyword"
          class="flex-1 max-w-md h-9"
          placeholder="输入关键词搜索（至少 3 字）"
          type="search"
        />
        <Button type="submit" class="h-9">搜索</Button>
      </form>
      <p v-if="q" class="text-sm text-muted-foreground">当前搜索：{{ q }}</p>
    </div>
    <AppLoadingOverlay v-if="loading" />
    <div v-else-if="items.length > 0" class="rounded-md border border-border bg-card shadow-sm">
      <ul class="divide-y divide-border">
        <li
          v-for="it in items"
          :key="it.id"
          class="p-4 md:p-5 hover:bg-muted/50 cursor-pointer"
          @click="goToMagnet(it)"
        >
          <div class="text-sm font-medium break-words">
            {{ it.native_name || it.videoname || `字幕 #${it.id}` }}
          </div>
          <div class="mt-2 text-xs text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1">
            <span v-if="it.subtype">格式 {{ it.subtype }}</span>
            <span v-if="it.lang?.desc">语言 {{ it.lang.desc }}</span>
            <span v-if="it.release_site">来源 {{ it.release_site }}</span>
            <span v-if="it.upload_time">上传 {{ it.upload_time }}</span>
          </div>
        </li>
      </ul>
    </div>
    <AppEmpty v-else :title="errMsg ? '搜索失败' : '暂无结果'">
      <Button v-if="errMsg" size="sm" class="h-8" @click="fetchData">刷新</Button>
    </AppEmpty>
  </div>
</template>
