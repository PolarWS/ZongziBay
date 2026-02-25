<script setup lang="ts">
import {
  searchMovieApiV1TmdbSearchMovieGet,
  getMovieEnglishTitleApiV1TmdbMovieMovieIdEnglishTitleGet,
} from '@/api/tmdb'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import AppPagination from '@/components/AppPagination.vue'

const route = useRoute()
const router = useRouter()

// 顶部选择的搜索来源：海盗湾 | 动漫花园
const searchSource = ref<'piratebay' | 'anime'>('piratebay')

const page = ref(Number(route.query.page) || 1)
const loading = ref(false)
const items = ref<API.TMDBMovie[]>([])
const total = ref(0)
const itemsPerPage = 20

const imgBase = 'https://image.tmdb.org/t/p/w300'

const q = computed(() => (route.query.q as string) || '')
const totalForPagination = computed(() => total.value)

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

const getOriginalKeyword = (it: API.TMDBMovie) =>
  (it.original_title && it.original_title.trim()) || (it.title && it.title.trim()) || ''
const getChineseName = (it: API.TMDBMovie) =>
  (it.title && it.title.trim()) || (it.original_title && it.original_title.trim()) || ''

// 根据顶部选中的来源跳转；海盗湾优先使用 TMDB 英文标题
const goSearch = async (it: API.TMDBMovie) => {
  if (searchSource.value === 'piratebay') {
    let q = ''
    const id = it.id
    if (id != null && Number.isFinite(Number(id))) {
      try {
        const res = await getMovieEnglishTitleApiV1TmdbMovieMovieIdEnglishTitleGet({ movie_id: id })
        q = (res?.data?.english_title || '').trim()
      } catch {
        // 忽略接口异常，回退到原始名
      }
    }
    if (!q) q = getOriginalKeyword(it)
    if (!q) return
    const tmdbYear = it.release_date?.slice(0, 4) || ''
    router.push({ path: '/piratebay', query: { q, tmdbName: getChineseName(it), tmdbYear } })
  } else {
    const name = (it.title && it.title.trim()) || (it.original_title && it.original_title.trim()) || ''
    if (!name) return
    const tmdbYear = it.release_date?.slice(0, 4) || ''
    router.push({ path: '/anime', query: { q: name, tmdbName: name, tmdbYear } })
  }
}
</script>

<template>
  <div class="px-2 md:px-0">
    <div class="flex flex-col gap-3 mb-4 sm:flex-row sm:items-center sm:justify-between">
      <h1 class="text-lg font-semibold truncate min-w-0">电影搜索：{{ q || '—' }}</h1>
      <div class="flex items-center gap-2 sm:gap-4 shrink-0 flex-wrap">
        <span class="text-sm text-muted-foreground order-2 sm:order-1">第 {{ page }} 页</span>
        <div class="flex rounded-lg border border-border p-0.5 bg-muted/50 order-1 sm:order-2">
          <button
            type="button"
            class="px-2.5 py-1.5 sm:px-3 text-sm font-medium rounded-md transition-colors cursor-pointer"
            :class="searchSource === 'piratebay' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="searchSource = 'piratebay'"
          >
            海盗湾
          </button>
          <button
            type="button"
            class="px-2.5 py-1.5 sm:px-3 text-sm font-medium rounded-md transition-colors cursor-pointer"
            :class="searchSource === 'anime' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="searchSource = 'anime'"
          >
            动漫花园
          </button>
        </div>
      </div>
    </div>
    <AppLoadingOverlay v-if="loading" />
    <div v-else-if="items.length > 0" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      <div
        v-for="it in items"
        :key="it.id"
        class="group relative rounded-xl border border-border bg-card shadow-sm overflow-hidden transition-all duration-300 hover:shadow-md hover:-translate-y-1 hover:border-primary/50 cursor-pointer flex flex-col h-full"
        @click="goSearch(it)"
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
        <div class="p-3 sm:p-4 space-y-1 bg-card flex flex-col flex-1 min-h-0">
          <div class="text-base font-semibold break-words line-clamp-3 leading-snug group-hover:text-primary transition-colors">{{ it.title || it.original_title || '未命名' }}</div>
          <div class="text-xs text-muted-foreground font-mono shrink-0">{{ it.release_date || '—' }}</div>
          <div class="pt-2 text-xs text-muted-foreground/80 line-clamp-4 leading-relaxed overflow-hidden flex-1 min-h-0">{{ it.overview || '暂无简介' }}</div>
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
