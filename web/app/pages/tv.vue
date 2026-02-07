<script setup lang="ts">
import { searchTvApiV1TmdbSearchTvGet } from '@/api/tmdb'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import AppPagination from '@/components/AppPagination.vue'

const route = useRoute()
const router = useRouter()
const q = computed(() => (route.query.q as string) || '')
const page = ref(Number(route.query.page) || 1)
const loading = ref(false)
const items = ref<API.TMDBTV[]>([])
const total = ref(0)
const itemsPerPage = 20
const totalForPagination = computed(() => total.value)

const fetchData = async () => {
  const query = q.value.trim()
  if (!query) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const res = await searchTvApiV1TmdbSearchTvGet({ query, page: page.value })
    items.value = res?.data?.items ?? []
    total.value = res?.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

watch(() => q.value, () => {
  page.value = 1
  router.replace({ path: route.path, query: { q: q.value, page: page.value } })
  fetchData()
})

watch(() => page.value, () => {
  router.replace({ path: route.path, query: { q: q.value, page: page.value } })
  fetchData()
})

onMounted(() => {
  fetchData()
})

const imgBase = 'https://image.tmdb.org/t/p/w300'

const goPirateBay = (it: API.TMDBTV) => {
  const q =
    (it.original_name && it.original_name.trim()) ||
    (it.name && it.name.trim()) ||
    ''
  if (!q) return
  const tmdbName = (it.name && it.name.trim()) || (it.original_name && it.original_name.trim()) || ''
  router.push({ path: '/piratebay', query: { q, tmdbName } })
}
</script>

<template>
  <div class="px-2 md:px-0">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-lg font-semibold">剧集搜索：{{ q || '—' }}</h1>
      <div class="text-sm text-muted-foreground">第 {{ page }} 页</div>
    </div>
    <div class="relative">
      <AppLoadingOverlay v-if="loading" />
      <div :class="{ 'opacity-50': loading }">
        <div v-if="items.length > 0" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div
            v-for="it in items"
            :key="it.id"
            class="group relative rounded-xl border border-border bg-card shadow-sm overflow-hidden cursor-pointer transition-all duration-300 hover:shadow-md hover:-translate-y-1 hover:border-primary/50"
            @click="goPirateBay(it)"
          >
            <div class="aspect-[2/3] overflow-hidden bg-muted">
              <img 
                v-if="it.poster_path" 
                :src="imgBase + it.poster_path" 
                alt="" 
                class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                loading="lazy"
              />
              <div v-else class="w-full h-full flex items-center justify-center bg-muted text-muted-foreground">
                No Poster
              </div>
            </div>
            <div class="p-4 space-y-1 bg-card flex flex-col h-[170px]">
              <div class="text-base font-semibold truncate shrink-0 group-hover:text-primary transition-colors">{{ it.name || it.original_name || '未命名' }}</div>
              <div class="text-xs text-muted-foreground font-mono shrink-0">{{ it.first_air_date || '—' }}</div>
              <div class="pt-2 text-xs text-muted-foreground/80 line-clamp-4 leading-relaxed overflow-hidden flex-1">{{ it.overview || '暂无简介' }}</div>
            </div>
          </div>
        </div>
        <AppEmpty v-else-if="!loading" title="暂无结果" description="请调整关键词后重试" />
      </div>
    </div>
    <AppPagination
      v-model:page="page"
      :items-per-page="itemsPerPage"
      :total="totalForPagination"
    />
  </div>
</template>
