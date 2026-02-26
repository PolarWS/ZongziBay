<script setup lang="ts">
import {
  getTrendingMoviesApiV1TmdbTrendingMovieGet,
  getTrendingTvApiV1TmdbTrendingTvGet,
  getPopularMoviesApiV1TmdbPopularMovieGet,
  getPopularTvApiV1TmdbPopularTvGet,
  getTopRatedMoviesApiV1TmdbTopRatedMovieGet,
  getTopRatedTvApiV1TmdbTopRatedTvGet,
  getMovieEnglishTitleApiV1TmdbMovieMovieIdEnglishTitleGet,
  getTvEnglishTitleApiV1TmdbTvTvIdEnglishTitleGet,
} from '@/api/tmdb'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import AppPagination from '@/components/AppPagination.vue'

const route = useRoute()
const router = useRouter()

const LIST_KINDS = ['trending_week', 'trending_day', 'popular', 'top_rated'] as const
const isValidList = (v: string): v is (typeof LIST_KINDS)[number] =>
  LIST_KINDS.includes(v as (typeof LIST_KINDS)[number])

// 从路由恢复状态
const initFromRoute = () => {
  const t = (route.query.type as string) || 'movie'
  const l = (route.query.list as string) || 'trending_week'
  const p = Math.max(1, Number(route.query.page) || 1)
  mediaType.value = t === 'tv' ? 'tv' : 'movie'
  listKind.value = isValidList(l) ? l : 'trending_week'
  page.value = p
}

// 媒体类型：电影 | 剧集
const mediaType = ref<'movie' | 'tv'>('movie')
// 列表类型：热播(周) | 热播(日) | 热门 | 高分
const listKind = ref<'trending_week' | 'trending_day' | 'popular' | 'top_rated'>('trending_week')
// 点击卡片时的搜索来源：海盗湾 | 动漫花园 | ASSRT字幕站（可从设置页偏好恢复）
const DEFAULT_SEARCH_SOURCE_KEY = 'zongzi_default_search_source'
const searchSource = ref<'piratebay' | 'anime' | 'assrt'>('piratebay')

const page = ref(1)

// 把当前筛选和页码同步到 URL，便于刷新保留
const syncRoute = () => {
  router.replace({
    path: route.path,
    query: {
      type: mediaType.value,
      list: listKind.value,
      page: page.value > 1 ? String(page.value) : undefined,
    },
  })
}
const loading = ref(false)
const items = ref<(API.TMDBMovie | API.TMDBTV)[]>([])
const total = ref(0)
const itemsPerPage = 20

const imgBase = 'https://image.tmdb.org/t/p/w300'

// 电影：原始名 / 中文名
const getMovieOriginal = (it: API.TMDBMovie) =>
  (it.original_title && it.original_title.trim()) || (it.title && it.title.trim()) || ''
const getMovieChineseName = (it: API.TMDBMovie) =>
  (it.title && it.title.trim()) || (it.original_title && it.original_title.trim()) || ''

// 剧集：原始名 / 中文名
const getTvOriginal = (it: API.TMDBTV) =>
  (it.original_name && it.original_name.trim()) || (it.name && it.name.trim()) || ''
const getTvChineseName = (it: API.TMDBTV) =>
  (it.name && it.name.trim()) || (it.original_name && it.original_name.trim()) || ''

// 根据当前 mediaType + listKind + page 拉取列表
const fetchList = async () => {
  loading.value = true
  items.value = []
  try {
    const p = page.value
    if (mediaType.value === 'movie') {
      if (listKind.value === 'trending_week') {
        const res = await getTrendingMoviesApiV1TmdbTrendingMovieGet({ page: p, window: 'week' })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      } else if (listKind.value === 'trending_day') {
        const res = await getTrendingMoviesApiV1TmdbTrendingMovieGet({ page: p, window: 'day' })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      } else if (listKind.value === 'popular') {
        const res = await getPopularMoviesApiV1TmdbPopularMovieGet({ page: p })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      } else {
        const res = await getTopRatedMoviesApiV1TmdbTopRatedMovieGet({ page: p })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      }
    } else {
      if (listKind.value === 'trending_week') {
        const res = await getTrendingTvApiV1TmdbTrendingTvGet({ page: p, window: 'week' })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      } else if (listKind.value === 'trending_day') {
        const res = await getTrendingTvApiV1TmdbTrendingTvGet({ page: p, window: 'day' })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      } else if (listKind.value === 'popular') {
        const res = await getPopularTvApiV1TmdbPopularTvGet({ page: p })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      } else {
        const res = await getTopRatedTvApiV1TmdbTopRatedTvGet({ page: p })
        items.value = res?.data?.items ?? []
        total.value = res?.data?.total ?? 0
      }
    }
  } finally {
    loading.value = false
  }
}

// 点击电影卡片：按 searchSource 跳转海盗湾 / 动漫花园 / ASSRT字幕站
const goMovieSearch = async (it: API.TMDBMovie) => {
  const tmdbYear = it.release_date?.slice(0, 4) || ''
  const chineseName = getMovieChineseName(it)
  if (searchSource.value === 'piratebay') {
    let q = ''
    const id = it.id
    if (id != null && Number.isFinite(Number(id))) {
      try {
        const res = await getMovieEnglishTitleApiV1TmdbMovieMovieIdEnglishTitleGet({ movie_id: id })
        q = (res?.data?.english_title || '').trim()
      } catch {
        // 忽略
      }
    }
    if (!q) q = getMovieOriginal(it)
    if (!q) return
    router.push({ path: '/piratebay', query: { q, tmdbName: chineseName, tmdbYear } })
  } else if (searchSource.value === 'assrt') {
    const name = chineseName || getMovieOriginal(it)
    if (!name) return
    router.push({ path: '/subtitle', query: { q: name, tmdbName: chineseName, tmdbYear } })
  } else {
    const name = chineseName || getMovieOriginal(it)
    if (!name) return
    router.push({ path: '/anime', query: { q: name, tmdbName: name, tmdbYear } })
  }
}

// 点击剧集卡片：按 searchSource 跳转海盗湾 / 动漫花园 / ASSRT字幕站
const goTvSearch = async (it: API.TMDBTV) => {
  const tmdbYear = it.first_air_date?.slice(0, 4) || ''
  const chineseName = getTvChineseName(it)
  if (searchSource.value === 'piratebay') {
    let q = ''
    const id = it.id
    if (id != null && Number.isFinite(Number(id))) {
      try {
        const res = await getTvEnglishTitleApiV1TmdbTvTvIdEnglishTitleGet({ tv_id: id })
        q = (res?.data?.english_title || '').trim()
      } catch {
        // 忽略
      }
    }
    if (!q) q = getTvOriginal(it)
    if (!q) return
    router.push({ path: '/piratebay', query: { q, tmdbName: chineseName, tmdbYear } })
  } else if (searchSource.value === 'assrt') {
    const name = chineseName || getTvOriginal(it)
    if (!name) return
    router.push({ path: '/subtitle', query: { q: name, tmdbName: chineseName, tmdbYear } })
  } else {
    const name = chineseName || getTvOriginal(it)
    if (!name) return
    router.push({ path: '/anime', query: { q: name, tmdbName: name, tmdbYear } })
  }
}

const onCardClick = (it: API.TMDBMovie | API.TMDBTV) => {
  if (mediaType.value === 'movie') {
    goMovieSearch(it as API.TMDBMovie)
  } else {
    goTvSearch(it as API.TMDBTV)
  }
}

const listKindLabel = computed(() => {
  const m: Record<string, string> = {
    trending_week: '热播(周)',
    trending_day: '热播(日)',
    popular: '热门',
    top_rated: '高分',
  }
  return m[listKind.value] ?? listKind.value
})

watch([mediaType, listKind], () => {
  page.value = 1
  syncRoute()
  fetchList()
})

watch(() => page.value, () => {
  syncRoute()
  fetchList()
})

onMounted(() => {
  const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(DEFAULT_SEARCH_SOURCE_KEY) : null
  if (saved === 'piratebay' || saved === 'anime' || saved === 'assrt') searchSource.value = saved
  initFromRoute()
  syncRoute()
  fetchList()
})
</script>

<template>
  <div class="px-2 md:px-0">
    <h1 class="text-lg font-semibold mb-4">推荐</h1>

    <!-- 筛选条件：左右排版，大屏一行、小屏自动换行 -->
    <div class="flex flex-wrap items-center gap-x-6 gap-y-3 mb-5 p-4 rounded-xl border border-border bg-muted/30">
      <!-- 左侧：类型 + 列表 -->
      <div class="flex flex-wrap items-center gap-x-5 gap-y-3">
        <div class="flex items-center gap-2">
          <span class="text-sm text-muted-foreground shrink-0 w-8">类型</span>
          <div class="flex rounded-lg border border-border p-0.5 bg-background">
            <button
              type="button"
              class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
              :class="mediaType === 'movie' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
              @click="mediaType = 'movie'"
            >
              电影
            </button>
            <button
              type="button"
              class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
              :class="mediaType === 'tv' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
              @click="mediaType = 'tv'"
            >
              剧集
            </button>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-sm text-muted-foreground shrink-0 w-8">列表</span>
          <div class="flex flex-wrap gap-1 rounded-lg border border-border p-0.5 bg-background">
            <button
              v-for="k in (['trending_week', 'trending_day', 'popular', 'top_rated'] as const)"
              :key="k"
              type="button"
              class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
              :class="listKind === k ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
              @click="listKind = k"
            >
              {{ k === 'trending_week' ? '热播(周)' : k === 'trending_day' ? '热播(日)' : k === 'popular' ? '热门' : '高分' }}
            </button>
          </div>
        </div>
      </div>
      <!-- 右侧：点击跳转（大屏有左边线区分） -->
      <div class="flex items-center gap-2 sm:border-l sm:border-border sm:pl-5 sm:ml-1">
        <span class="text-sm text-muted-foreground shrink-0">跳转</span>
        <div class="flex rounded-lg border border-border p-0.5 bg-background">
          <button
            type="button"
            class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
            :class="searchSource === 'piratebay' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="searchSource = 'piratebay'"
          >
            海盗湾
          </button>
          <button
            type="button"
            class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
            :class="searchSource === 'anime' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="searchSource = 'anime'"
          >
            动漫花园
          </button>
          <button
            type="button"
            class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
            :class="searchSource === 'assrt' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="searchSource = 'assrt'"
          >
            ASSRT字幕站
          </button>
        </div>
      </div>
    </div>

    <!-- 当前列表标题 -->
    <p class="text-sm text-muted-foreground mb-3">
      {{ mediaType === 'movie' ? '电影' : '剧集' }} · {{ listKindLabel }}
    </p>

    <AppLoadingOverlay v-if="loading" />
    <div
      v-else-if="items.length > 0"
      class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4"
    >
      <div
        v-for="(it, idx) in items"
        :key="(mediaType === 'movie' ? (it as API.TMDBMovie).id : (it as API.TMDBTV).id) + '-' + idx"
        class="group relative rounded-xl border border-border bg-card shadow-sm overflow-hidden transition-all duration-300 hover:shadow-md hover:-translate-y-1 hover:border-primary/50 cursor-pointer flex flex-col h-full"
        @click="onCardClick(it)"
      >
        <div class="aspect-[2/3] overflow-hidden bg-muted">
          <img
            v-if="it.poster_path"
            :src="imgBase + it.poster_path"
            alt=""
            class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
          <div
            v-else
            class="w-full h-full flex items-center justify-center bg-muted text-muted-foreground text-sm"
          >
            无海报
          </div>
        </div>
        <div class="p-3 sm:p-4 space-y-1 bg-card flex flex-col flex-1 min-h-0">
          <div class="text-base font-semibold break-words line-clamp-3 leading-snug group-hover:text-primary transition-colors">
            {{ mediaType === 'movie' ? (it as API.TMDBMovie).title || (it as API.TMDBMovie).original_title || '未命名' : (it as API.TMDBTV).name || (it as API.TMDBTV).original_name || '未命名' }}
          </div>
          <div class="text-xs text-muted-foreground font-mono shrink-0">
            {{ mediaType === 'movie' ? (it as API.TMDBMovie).release_date || '—' : (it as API.TMDBTV).first_air_date || '—' }}
          </div>
          <div class="pt-2 text-xs text-muted-foreground/80 line-clamp-4 leading-relaxed overflow-hidden flex-1 min-h-0">
            {{ it.overview || '暂无简介' }}
          </div>
        </div>
      </div>
    </div>
    <AppEmpty v-else title="暂无数据" description="切换类型或稍后再试" />
    <AppPagination
      v-if="items.length > 0 && total > itemsPerPage"
      v-model:page="page"
      :items-per-page="itemsPerPage"
      :total="total"
    />
  </div>
</template>
