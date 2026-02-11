<template>
  <div class="px-2 md:px-0">
    <div class="flex items-center justify-between mb-4 gap-4">
      <h1 class="text-lg font-semibold truncate min-w-0">电影搜索：{{ q || '—' }}</h1>
      <div class="text-sm text-muted-foreground shrink-0">第 {{ page }} 页</div>
    </div>
    <AppLoadingOverlay v-if="loading" />
    <div v-else-if="items.length > 0" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
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
            无数据
          </div>
        </div>
        <div class="p-3 sm:p-4 space-y-1 bg-card flex flex-col min-h-[140px] sm:min-h-[170px]">
          <div class="text-base font-semibold truncate shrink-0 group-hover:text-primary transition-colors">{{ it.title || it.original_title || '未命名' }}</div>
          <div class="text-xs text-muted-foreground font-mono shrink-0">{{ it.release_date || '—' }}</div>
          <div class="pt-2 text-xs text-muted-foreground/80 line-clamp-4 leading-relaxed overflow-hidden flex-1">{{ it.overview || '暂无简介' }}</div>
        </div>
      </div>
    </div>
    <AppEmpty v-else title="暂无结果" description="请调整关键词后重试" />
    <AppPagination
      v-model:page="page"
      :items-per-page="itemsPerPage"
      :total="totalForPagination"
    />
  </div>
</template>

<script setup lang="ts">
import { searchMovieApiV1TmdbSearchMovieGet } from '@/api/tmdb'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import AppPagination from '@/components/AppPagination.vue'

const route = useRoute()
const router = useRouter()

// ref / reactive 声明
const page = ref(Number(route.query.page) || 1)
const loading = ref(false)
const items = ref<API.TMDBMovie[]>([])
const total = ref(0)
const itemsPerPage = 20

// TMDB 海报基础 URL
const imgBase = 'https://image.tmdb.org/t/p/w300'

// computed
const q = computed(() => (route.query.q as string) || '')
const totalForPagination = computed(() => total.value)

// watch
watch(() => q.value, () => {
  page.value = 1
  router.replace({ path: route.path, query: { q: q.value, page: page.value } })
  fetchData()
})

watch(() => page.value, () => {
  router.replace({ path: route.path, query: { q: q.value, page: page.value } })
  fetchData()
})

// 生命周期
onMounted(() => {
  fetchData()
})

// 根据关键词加载电影列表
const fetchData = async () => {
  const query = q.value.trim()
  if (!query) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const res = await searchMovieApiV1TmdbSearchMovieGet({ query, page: page.value })
    items.value = res?.data?.items ?? []
    total.value = res?.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

// 跳转到海盗湾搜索页
const goPirateBay = (it: API.TMDBMovie) => {
  const q =
    (it.original_title && it.original_title.trim()) ||
    (it.title && it.title.trim()) ||
    ''
  if (!q) return
  const tmdbName = (it.title && it.title.trim()) || (it.original_title && it.original_title.trim()) || ''
  router.push({ path: '/piratebay', query: { q, tmdbName } })
}
</script>
