<script setup lang="ts">
import {
  getTrendingMoviesApiV1TmdbTrendingMovieGet,
  getTrendingTvApiV1TmdbTrendingTvGet,
  getPopularMoviesApiV1TmdbPopularMovieGet,
  getPopularTvApiV1TmdbPopularTvGet,
  getTopRatedMoviesApiV1TmdbTopRatedMovieGet,
  getTopRatedTvApiV1TmdbTopRatedTvGet,
  getTopRatedAnimeApiV1TmdbTopRatedAnimeGet,
  getMovieEnglishTitleApiV1TmdbMovieMovieIdEnglishTitleGet,
  getTvEnglishTitleApiV1TmdbTvTvIdEnglishTitleGet,
} from '@/api/tmdb'
import { getBangumiCalendarApiV1BangumiCalendarGet, getBangumiSeasonApiV1BangumiSeasonGet } from '@/api/bangumi'
import { Info, Star, ChevronDown } from 'lucide-vue-next'
import AppEmpty from '@/components/AppEmpty.vue'
import AppPagination from '@/components/AppPagination.vue'
import AppSkeletonGrid from '@/components/AppSkeletonGrid.vue'
import MediaDetailDialog from '@/components/MediaDetailDialog.vue'
import BangumiDetailDialog from '@/components/BangumiDetailDialog.vue'
import {
  getRecommendListCache,
  peekRecommendListCache,
  setRecommendListCache,
  RECOMMEND_CACHE_TTL_PAST_MS,
  RECOMMEND_CACHE_TTL_LIVE_MS,
  type RecommendListCacheEntry,
} from '@/utils/recommendListCache'

const route = useRoute()
const router = useRouter()

// 是否播放入场动画：仅首次进入页面时为 true；用户切换筛选/翻页后置为 false，避免卡片重复播放动画
const animateOnMount = ref(true)

// 全页共用一个 IntersectionObserver，避免本周新番百余张卡片各建一个观察器
const revealCallbacks = new WeakMap<Element, () => void>()
let sharedRevealIo: IntersectionObserver | null = null

const getSharedRevealIo = () => {
  if (typeof IntersectionObserver === 'undefined') return null
  if (!sharedRevealIo) {
    sharedRevealIo = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const cb = revealCallbacks.get(entry.target)
          if (!cb) continue
          cb()
          sharedRevealIo?.unobserve(entry.target)
          revealCallbacks.delete(entry.target)
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.05 },
    )
  }
  return sharedRevealIo
}

// 滚动入场指令：元素进入视口后按索引错开淡入上移，形成「一个个出现」的 stagger 效果
const vReveal = {
  mounted(el: HTMLElement, binding: { value?: number }) {
    // 已出现过（非首次加载）：直接展示，不再播放入场动画
    if (!animateOnMount.value) return
    const idx = typeof binding.value === 'number' ? binding.value : 0
    // 每 12 个循环一次，逐个错开 ~45ms，避免下方卡片累积延迟过久
    const delay = (idx % 12) * 45
    el.classList.add('reveal-init')

    const reveal = () => {
      el.style.transitionDelay = `${delay}ms`
      el.classList.remove('reveal-init')
      el.classList.add('reveal-in')
      // 动画结束后清理内联延迟与 will-change，避免影响卡片 hover 等其它过渡
      window.setTimeout(() => {
        el.style.transitionDelay = ''
        el.style.willChange = ''
      }, delay + 600)
    }

    const io = getSharedRevealIo()
    if (!io) {
      reveal()
      return
    }
    revealCallbacks.set(el, reveal)
    io.observe(el)
  },
  unmounted(el: HTMLElement) {
    sharedRevealIo?.unobserve(el)
    revealCallbacks.delete(el)
  },
}

const { imgBase, loadImageDomain } = useTmdbImage()

// 详情模态框状态
const detailOpen = ref(false)
const detailItem = ref<API.TMDBMovie | API.TMDBTV | null>(null)

// 打开详情模态框（阻止冒泡，避免触发卡片跳转）
const openDetail = (it: API.TMDBMovie | API.TMDBTV) => {
  detailItem.value = it
  detailOpen.value = true
}

// 番剧详情模态框状态（数据源为 Bangumi）
const bangumiDetailOpen = ref(false)
const bangumiDetailId = ref<number | null>(null)
const bangumiDetailFallback = ref<API.BangumiCalendarItem | null>(null)

const openBangumiDetail = (it: API.BangumiCalendarItem) => {
  bangumiDetailId.value = it.id ?? null
  bangumiDetailFallback.value = it
  bangumiDetailOpen.value = true
}

// 格式化评分，无有效评分返回空
const formatRating = (v: number | null | undefined) =>
  typeof v === 'number' && v > 0 ? v.toFixed(1) : ''

// 电影/剧集可用的列表类型；动漫使用独立的列表类型
const MOVIE_TV_KINDS = ['trending_week', 'trending_day', 'popular', 'top_rated'] as const
const ANIME_KINDS = ['calendar_week', 'season', 'top_rated'] as const
const SEASON_KEYS = ['winter', 'spring', 'summer', 'autumn'] as const
type SeasonKey = (typeof SEASON_KEYS)[number]

// 根据月份得到当前季度（冬1–3 / 春4–6 / 夏7–9 / 秋10–12）
const seasonFromMonth = (m: number): SeasonKey => {
  if (m <= 3) return 'winter'
  if (m <= 6) return 'spring'
  if (m <= 9) return 'summer'
  return 'autumn'
}

const seasonIndex = (s: SeasonKey) => SEASON_KEYS.indexOf(s)

const now = new Date()
const currentYear = now.getFullYear()
const currentSeason = seasonFromMonth(now.getMonth() + 1)

const seasonYear = ref(currentYear)
const seasonKey = ref<SeasonKey>(currentSeason)

// 年份选项：近 20 年（含当前年，不含未来）
const seasonYearOptions = computed(() =>
  Array.from({ length: 20 }, (_, i) => currentYear - i),
)

/** 某年某季是否已到（含当前季）；未来季不可选 */
const isSeasonAvailable = (year: number, s: SeasonKey) => {
  if (year < currentYear) return true
  if (year > currentYear) return false
  return seasonIndex(s) <= seasonIndex(currentSeason)
}

const availableSeasons = computed(() =>
  SEASON_KEYS.filter((s) => isSeasonAvailable(seasonYear.value, s)),
)

/** 若当前选中的季节尚未到来，回退到该年可选的最新一季 */
const clampSeasonToAvailable = () => {
  if (isSeasonAvailable(seasonYear.value, seasonKey.value)) return false
  const opts = availableSeasons.value
  seasonKey.value = opts.length ? opts[opts.length - 1]! : currentSeason
  return true
}

const seasonLabel = (s: SeasonKey) =>
  s === 'winter' ? '1月' : s === 'spring' ? '4月' : s === 'summer' ? '7月' : '10月'

const seasonTitle = (s: SeasonKey) =>
  s === 'winter' ? '冬番（1–3月）' : s === 'spring' ? '春番（4–6月）' : s === 'summer' ? '夏番（7–9月）' : '秋番（10–12月）'

// 年份下拉（与任务列表分页下拉同一套 UI）
const yearMenuOpen = ref(false)
const yearMenuRef = ref<HTMLElement | null>(null)

const closeYearMenu = (e: MouseEvent) => {
  const el = yearMenuRef.value
  if (!el || !(e.target instanceof Node) || el.contains(e.target)) return
  yearMenuOpen.value = false
}

// 媒体类型：电影 | 剧集 | 动漫
const mediaType = ref<'movie' | 'tv' | 'anime'>('movie')
// 列表类型（跨类型的并集，取值由 listKinds 约束）
const listKind = ref<string>('trending_week')

// 是否展示按星期分组的周历（本周新番 / 季度新番）
const isCalendarView = computed(
  () => mediaType.value === 'anime' && (listKind.value === 'calendar_week' || listKind.value === 'season'),
)

// 当前类型下可选的列表种类
const listKinds = computed<readonly string[]>(() =>
  mediaType.value === 'anime' ? ANIME_KINDS : MOVIE_TV_KINDS
)

// 该类型默认的列表种类
const defaultKindFor = (t: 'movie' | 'tv' | 'anime') =>
  t === 'anime' ? 'calendar_week' : 'trending_week'

// 从路由恢复状态
const initFromRoute = () => {
  const t = (route.query.type as string) || 'movie'
  const l = (route.query.list as string) || ''
  const p = Math.max(1, Number(route.query.page) || 1)
  mediaType.value = t === 'tv' ? 'tv' : t === 'anime' ? 'anime' : 'movie'
  listKind.value = listKinds.value.includes(l) ? l : defaultKindFor(mediaType.value)
  page.value = p
  const y = Number(route.query.year)
  if (Number.isFinite(y) && y >= 1980 && y <= currentYear) seasonYear.value = y
  const s = route.query.season as string
  if (SEASON_KEYS.includes(s as SeasonKey)) seasonKey.value = s as SeasonKey
  clampSeasonToAvailable()
}
// 点击卡片时的搜索来源：海盗湾 | 动漫花园 | ASSRT字幕站（可从设置页偏好恢复）
const DEFAULT_SEARCH_SOURCE_KEY = 'zongzi_default_search_source'
const searchSource = ref<'piratebay' | 'anime' | 'assrt'>('piratebay')
// 切到动漫时会强制跳转动漫花园；切回电影/剧集时恢复此前选择
let searchSourceBeforeAnime: 'piratebay' | 'anime' | 'assrt' | null = null

const applyAnimeSearchSource = () => {
  if (searchSource.value === 'anime') return
  searchSourceBeforeAnime = searchSource.value
  searchSource.value = 'anime'
}

const restoreSearchSourceAfterAnime = () => {
  if (searchSourceBeforeAnime == null) return
  searchSource.value = searchSourceBeforeAnime
  searchSourceBeforeAnime = null
}

const page = ref(1)

// 把当前筛选和页码同步到 URL，便于刷新保留
const syncRoute = () => {
  router.replace({
    path: route.path,
    query: {
      type: mediaType.value,
      list: listKind.value,
      page: page.value > 1 ? String(page.value) : undefined,
      year: listKind.value === 'season' ? String(seasonYear.value) : undefined,
      season: listKind.value === 'season' ? seasonKey.value : undefined,
    },
  })
}
const loading = ref(false)
const items = ref<(API.TMDBMovie | API.TMDBTV)[]>([])
// 番剧「本周新番」按星期分组数据（来自 Bangumi 每日放送）
const calendar = ref<API.BangumiCalendarDay[]>([])
const total = ref(0)
const itemsPerPage = 20

// 列表持久缓存（localStorage）：刷新后仍可命中；当前季会后台刷新
type ListCacheEntry = RecommendListCacheEntry
let fetchSeq = 0

const listCacheKey = () => {
  let key = `${mediaType.value}|${listKind.value}|${page.value}`
  if (mediaType.value === 'anime' && listKind.value === 'season') {
    key += `|${seasonYear.value}|${seasonKey.value}`
  }
  return key
}

const applyListCache = (entry: ListCacheEntry) => {
  items.value = entry.items
  calendar.value = entry.calendar
  total.value = entry.total
}

const listEntryHasData = (entry: ListCacheEntry) =>
  entry.items.length > 0 || entry.calendar.some((d) => (d.items?.length ?? 0) > 0)

/**
 * 仅缓存成功结果。
 * - 请求抛错不会走到这里
 * - 空结果不覆盖已有「有数据」的缓存，避免短暂失败/异常空包冲掉可用数据
 */
const commitListCache = (key: string, entry: ListCacheEntry) => {
  if (!listEntryHasData(entry)) {
    const prev = peekRecommendListCache(key)
    if (prev && listEntryHasData(prev)) return
  }
  setRecommendListCache(key, entry)
}

/** 本周新番 / 当前季度：可能随时有新番，优先刷新 */
const isLiveAnimeList = () => {
  if (mediaType.value !== 'anime') return false
  if (listKind.value === 'calendar_week') return true
  return (
    listKind.value === 'season' &&
    seasonYear.value === currentYear &&
    seasonKey.value === currentSeason
  )
}

// 今天对应的星期编号（1=周一 … 7=周日），用于高亮本日放送
const todayWeekdayId = (() => {
  const d = new Date().getDay()
  return d === 0 ? 7 : d
})()

// 番剧条目：中文名优先，其次原名
const getBangumiName = (it: API.BangumiCalendarItem) =>
  (it.name_cn && it.name_cn.trim()) || (it.name && it.name.trim()) || ''

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

/** 向远端拉取当前筛选对应的列表数据（不写 UI） */
const loadListFromNetwork = async (): Promise<ListCacheEntry> => {
  const p = page.value
  let nextItems: (API.TMDBMovie | API.TMDBTV)[] = []
  let nextCalendar: API.BangumiCalendarDay[] = []
  let nextTotal = 0

  if (mediaType.value === 'anime') {
    if (listKind.value === 'calendar_week') {
      const res = await getBangumiCalendarApiV1BangumiCalendarGet()
      nextCalendar = res?.data ?? []
    } else if (listKind.value === 'season') {
      const res = await getBangumiSeasonApiV1BangumiSeasonGet({
        year: seasonYear.value,
        season: seasonKey.value,
      })
      nextCalendar = res?.data ?? []
    } else {
      const res = await getTopRatedAnimeApiV1TmdbTopRatedAnimeGet({ page: p })
      nextItems = res?.data?.items ?? []
      nextTotal = res?.data?.total ?? 0
    }
  } else if (mediaType.value === 'movie') {
    if (listKind.value === 'trending_week') {
      const res = await getTrendingMoviesApiV1TmdbTrendingMovieGet({ page: p, window: 'week' })
      nextItems = res?.data?.items ?? []
      nextTotal = res?.data?.total ?? 0
    } else if (listKind.value === 'trending_day') {
      const res = await getTrendingMoviesApiV1TmdbTrendingMovieGet({ page: p, window: 'day' })
      nextItems = res?.data?.items ?? []
      nextTotal = res?.data?.total ?? 0
    } else if (listKind.value === 'popular') {
      const res = await getPopularMoviesApiV1TmdbPopularMovieGet({ page: p })
      nextItems = res?.data?.items ?? []
      nextTotal = res?.data?.total ?? 0
    } else {
      const res = await getTopRatedMoviesApiV1TmdbTopRatedMovieGet({ page: p })
      nextItems = res?.data?.items ?? []
      nextTotal = res?.data?.total ?? 0
    }
  } else if (listKind.value === 'trending_week') {
    const res = await getTrendingTvApiV1TmdbTrendingTvGet({ page: p, window: 'week' })
    nextItems = res?.data?.items ?? []
    nextTotal = res?.data?.total ?? 0
  } else if (listKind.value === 'trending_day') {
    const res = await getTrendingTvApiV1TmdbTrendingTvGet({ page: p, window: 'day' })
    nextItems = res?.data?.items ?? []
    nextTotal = res?.data?.total ?? 0
  } else if (listKind.value === 'popular') {
    const res = await getPopularTvApiV1TmdbPopularTvGet({ page: p })
    nextItems = res?.data?.items ?? []
    nextTotal = res?.data?.total ?? 0
  } else {
    const res = await getTopRatedTvApiV1TmdbTopRatedTvGet({ page: p })
    nextItems = res?.data?.items ?? []
    nextTotal = res?.data?.total ?? 0
  }

  return { items: nextItems, calendar: nextCalendar, total: nextTotal }
}

// 根据当前 mediaType + listKind + page 拉取列表
const fetchList = async () => {
  const key = listCacheKey()
  const live = isLiveAnimeList()

  // 往季等稳定数据：localStorage 命中且未过期则直接用
  if (!live) {
    const cached = getRecommendListCache(key, RECOMMEND_CACHE_TTL_PAST_MS)
    if (cached) {
      applyListCache(cached)
      loading.value = false
      return
    }
  } else {
    // 当前季 / 本周：30 分钟内视为新鲜直接用；更久则秒开旧缓存并后台刷新
    const fresh = getRecommendListCache(key, RECOMMEND_CACHE_TTL_LIVE_MS)
    if (fresh) {
      applyListCache(fresh)
      loading.value = false
      return
    }
    const stale = peekRecommendListCache(key)
    if (stale) {
      applyListCache(stale)
      loading.value = false
      const seq = ++fetchSeq
      try {
        const entry = await loadListFromNetwork()
        commitListCache(key, entry)
        if (seq === fetchSeq && listCacheKey() === key) applyListCache(entry)
      } catch {
        // 后台刷新失败：不写缓存，保留已展示的旧数据
      }
      return
    }
  }

  const seq = ++fetchSeq
  loading.value = true
  items.value = []
  calendar.value = []
  try {
    const entry = await loadListFromNetwork()
    commitListCache(key, entry)
    if (seq !== fetchSeq) return
    applyListCache(entry)
  } catch {
    // 加载失败：不写入缓存，避免把失败结果固化
    if (seq === fetchSeq) {
      items.value = []
      calendar.value = []
      total.value = 0
    }
  } finally {
    if (seq === fetchSeq) loading.value = false
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
    // 剧集与动漫（高分番剧）均按剧集逻辑跳转
    goTvSearch(it as API.TMDBTV)
  }
}

// 点击本周/季度新番条目：按 searchSource 跳转（切到动漫时会默认选中动漫花园）
const goBangumiSearch = (it: API.BangumiCalendarItem) => {
  const name = getBangumiName(it)
  if (!name) return
  const tmdbYear = (it.air_date || '').slice(0, 4)
  if (searchSource.value === 'piratebay') {
    router.push({ path: '/piratebay', query: { q: name, tmdbName: name, tmdbYear } })
  } else if (searchSource.value === 'assrt') {
    router.push({ path: '/subtitle', query: { q: name, tmdbName: name, tmdbYear } })
  } else {
    router.push({ path: '/anime', query: { q: name, tmdbName: name, tmdbYear } })
  }
}

const kindLabel = (k: string) => {
  if (k === 'calendar_week') return '本周新番'
  if (k === 'season') return '季度新番'
  if (k === 'top_rated') return mediaType.value === 'anime' ? '历史高分' : '高分'
  return k === 'trending_week' ? '热播(周)' : k === 'trending_day' ? '热播(日)' : k === 'popular' ? '热门' : k
}

// 切换季度年份 / 季节
const selectSeasonYear = (y: number) => {
  yearMenuOpen.value = false
  if (y > currentYear || seasonYear.value === y) return
  animateOnMount.value = false
  seasonYear.value = y
  clampSeasonToAvailable()
  syncRoute()
  fetchList()
}

const selectSeasonKey = (s: SeasonKey) => {
  if (!isSeasonAvailable(seasonYear.value, s) || seasonKey.value === s) return
  animateOnMount.value = false
  seasonKey.value = s
  syncRoute()
  fetchList()
}

// 切换类型：修正非法列表种类，重置分页并拉取；动漫默认跳转动漫花园
const selectMediaType = (t: 'movie' | 'tv' | 'anime') => {
  if (mediaType.value === t) return
  animateOnMount.value = false
  if (t === 'anime') {
    applyAnimeSearchSource()
  } else if (mediaType.value === 'anime') {
    restoreSearchSourceAfterAnime()
  }
  mediaType.value = t
  if (!listKinds.value.includes(listKind.value)) {
    listKind.value = defaultKindFor(t)
  }
  page.value = 1
  syncRoute()
  fetchList()
}

// 切换列表种类
const selectListKind = (k: string) => {
  if (listKind.value === k) return
  animateOnMount.value = false
  listKind.value = k
  yearMenuOpen.value = false
  page.value = 1
  syncRoute()
  fetchList()
}

watch(() => page.value, () => {
  animateOnMount.value = false
  syncRoute()
  fetchList()
})

onMounted(() => {
  document.addEventListener('click', closeYearMenu)
  const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(DEFAULT_SEARCH_SOURCE_KEY) : null
  if (saved === 'piratebay' || saved === 'anime' || saved === 'assrt') searchSource.value = saved
  loadImageDomain()
  initFromRoute()
  // 直接打开动漫推荐页时，跳转源同步切到动漫花园
  if (mediaType.value === 'anime') applyAnimeSearchSource()
  syncRoute()
  fetchList()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeYearMenu)
})
</script>

<template>
  <div class="px-2 md:px-0">
    <h1 class="text-lg font-semibold mb-4">推荐</h1>

    <!-- 筛选条件 -->
    <div class="mb-5 p-4 rounded-xl border border-border bg-muted/30 space-y-3">
      <!-- 第一行：类型 + 列表 | 跳转 -->
      <div class="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div class="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div class="flex items-center gap-2">
            <span class="text-sm text-muted-foreground shrink-0 w-8">类型</span>
            <div class="flex rounded-lg border border-border p-0.5 bg-background">
              <button
                type="button"
                class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
                :class="mediaType === 'movie' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                @click="selectMediaType('movie')"
              >
                电影
              </button>
              <button
                type="button"
                class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
                :class="mediaType === 'tv' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                @click="selectMediaType('tv')"
              >
                剧集
              </button>
              <button
                type="button"
                class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
                :class="mediaType === 'anime' ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                @click="selectMediaType('anime')"
              >
                动漫
              </button>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-sm text-muted-foreground shrink-0 w-8">列表</span>
            <div class="flex flex-wrap gap-1 rounded-lg border border-border p-0.5 bg-background">
              <button
                v-for="k in listKinds"
                :key="k"
                type="button"
                class="px-3 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer"
                :class="listKind === k ? 'bg-green-500 text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                @click="selectListKind(k)"
              >
                {{ kindLabel(k) }}
              </button>
            </div>
          </div>
        </div>
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

      <!-- 第二行：季度新番的年份 + 季节 -->
      <div
        v-if="mediaType === 'anime' && listKind === 'season'"
        class="flex flex-wrap items-center gap-x-5 gap-y-3 pt-3 border-t border-border"
      >
        <div class="flex items-center gap-2">
          <span class="text-sm text-muted-foreground shrink-0 w-8">年份</span>
          <div class="relative" ref="yearMenuRef">
            <button
              type="button"
              class="inline-flex h-9 min-w-[5.5rem] items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
              @click.stop="yearMenuOpen = !yearMenuOpen"
            >
              {{ seasonYear }}
              <ChevronDown class="size-3.5 opacity-50 shrink-0" :class="yearMenuOpen ? 'rotate-180' : ''" />
            </button>
            <div
              v-if="yearMenuOpen"
              class="absolute left-0 top-full mt-1 w-28 max-h-56 overflow-y-auto rounded-lg border border-border bg-popover text-popover-foreground shadow-md z-50"
            >
              <div class="p-1">
                <button
                  v-for="y in seasonYearOptions"
                  :key="y"
                  type="button"
                  class="flex w-full cursor-pointer select-none items-center rounded-md px-2.5 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground"
                  :class="seasonYear === y ? 'bg-green-500 text-white hover:bg-green-500 hover:text-white' : ''"
                  @click="selectSeasonYear(y)"
                >
                  {{ y }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-sm text-muted-foreground shrink-0 w-8">季节</span>
          <div class="flex flex-wrap gap-1 rounded-lg border border-border p-0.5 bg-background">
            <button
              v-for="s in SEASON_KEYS"
              :key="s"
              type="button"
              class="px-3 py-2 text-sm font-medium rounded-md transition-colors"
              :disabled="!isSeasonAvailable(seasonYear, s)"
              :class="[
                seasonKey === s
                  ? 'bg-green-500 text-white shadow-sm cursor-pointer'
                  : isSeasonAvailable(seasonYear, s)
                    ? 'text-muted-foreground hover:text-foreground cursor-pointer'
                    : 'text-muted-foreground/35 cursor-not-allowed',
              ]"
              :title="isSeasonAvailable(seasonYear, s) ? seasonTitle(s) : `${seasonTitle(s)} · 尚未开始`"
              @click="selectSeasonKey(s)"
            >
              {{ seasonLabel(s) }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载态：骨架屏 -->
    <template v-if="loading">
      <div v-if="isCalendarView" class="space-y-7">
        <AppSkeletonGrid v-for="n in 3" :key="n" :count="10" with-header />
      </div>
      <AppSkeletonGrid v-else :count="itemsPerPage" />
    </template>

    <!-- 番剧周历：本周新番 / 季度新番，按周一到周日分组 -->
    <template v-else-if="isCalendarView">
      <div v-if="calendar.length > 0" class="space-y-7">
        <section v-for="day in calendar" :key="day.weekday.id ?? day.weekday.en ?? ''">
          <div class="flex items-center gap-3 mb-4">
            <div class="flex items-center gap-2.5 shrink-0">
              <span
                class="h-5 w-1.5 rounded-full"
                :class="listKind === 'calendar_week' && day.weekday.id === todayWeekdayId ? 'bg-green-500' : 'bg-border'"
              />
              <h3 class="text-lg font-bold tracking-tight">{{ day.weekday.cn || day.weekday.ja || day.weekday.en }}</h3>
              <span
                v-if="listKind === 'calendar_week' && day.weekday.id === todayWeekdayId"
                class="inline-flex items-center gap-1 rounded-full bg-green-500 px-2 py-0.5 text-xs font-semibold text-white shadow-sm shadow-green-500/30"
              >
                <span class="size-1.5 rounded-full bg-white" />
                今天
              </span>
              <span class="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                {{ day.items.length }} 部
              </span>
            </div>
            <div class="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
          </div>
          <div v-if="day.items.length > 0" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            <div
              v-for="(it, idx) in day.items"
              :key="(it.id ?? 0) + '-' + idx"
              v-reveal="idx"
              class="cv-auto group relative rounded-xl border border-border bg-card shadow-sm overflow-hidden transition-[box-shadow,transform,border-color] duration-300 hover:shadow-md hover:-translate-y-1 hover:border-primary/50 cursor-pointer flex flex-col h-full"
              @click="goBangumiSearch(it)"
            >
              <div class="aspect-[2/3] overflow-hidden bg-muted relative">
                <img
                  v-if="it.image"
                  :src="it.image"
                  alt=""
                  referrerpolicy="no-referrer"
                  class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                  decoding="async"
                />
                <div v-else class="w-full h-full flex items-center justify-center bg-muted text-muted-foreground text-sm">
                  无海报
                </div>
                <div
                  v-if="formatRating(it.score)"
                  class="absolute top-2 left-2 inline-flex items-center gap-1 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-amber-300"
                >
                  <Star class="size-3 fill-amber-400 stroke-amber-400" />
                  {{ formatRating(it.score) }}
                </div>
                <!-- 详情按钮 -->
                <button
                  type="button"
                  class="absolute top-2 right-2 inline-flex items-center justify-center rounded-full bg-black/60 p-1.5 text-white/90 transition-colors hover:bg-black/80 hover:text-white cursor-pointer"
                  title="查看详情"
                  @click.stop="openBangumiDetail(it)"
                >
                  <Info class="size-4" />
                </button>
              </div>
              <div class="p-3 sm:p-4 space-y-1 bg-card flex flex-col flex-1 min-h-0">
                <div class="text-base font-semibold break-words line-clamp-2 leading-snug group-hover:text-primary transition-colors">
                  {{ getBangumiName(it) || '未命名' }}
                </div>
                <div v-if="it.name_cn && it.name && it.name_cn !== it.name" class="text-xs text-muted-foreground line-clamp-1">
                  {{ it.name }}
                </div>
                <div class="text-xs text-muted-foreground font-mono shrink-0">
                  {{ it.air_date || '—' }}
                </div>
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-muted-foreground">{{ listKind === 'season' ? '该日无首播' : '今日无放送' }}</p>
        </section>
      </div>
      <AppEmpty v-else title="暂无数据" description="稍后再试" />
    </template>
    <div
      v-else-if="items.length > 0"
      class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4"
    >
      <div
        v-for="(it, idx) in items"
        :key="(mediaType === 'movie' ? (it as API.TMDBMovie).id : (it as API.TMDBTV).id) + '-' + idx"
        v-reveal="idx"
        class="cv-auto group relative rounded-xl border border-border bg-card shadow-sm overflow-hidden transition-[box-shadow,transform,border-color] duration-300 hover:shadow-md hover:-translate-y-1 hover:border-primary/50 cursor-pointer flex flex-col h-full"
        @click="onCardClick(it)"
      >
        <div class="aspect-[2/3] overflow-hidden bg-muted relative">
          <img
            v-if="it.poster_path"
            :src="imgBase + it.poster_path"
            alt=""
            class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
            decoding="async"
          />
          <div
            v-else
            class="w-full h-full flex items-center justify-center bg-muted text-muted-foreground text-sm"
          >
            无海报
          </div>
          <!-- 评分角标 -->
          <div
            v-if="formatRating(it.vote_average)"
            class="absolute top-2 left-2 inline-flex items-center gap-1 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-semibold text-amber-300"
          >
            <Star class="size-3 fill-amber-400 stroke-amber-400" />
            {{ formatRating(it.vote_average) }}
          </div>
          <!-- 详情按钮 -->
          <button
            type="button"
            class="absolute top-2 right-2 inline-flex items-center justify-center rounded-full bg-black/60 p-1.5 text-white/90 transition-colors hover:bg-black/80 hover:text-white cursor-pointer"
            title="查看详情"
            @click.stop="openDetail(it)"
          >
            <Info class="size-4" />
          </button>
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
    <MediaDetailDialog v-model:open="detailOpen" :media="detailItem" :type="mediaType === 'movie' ? 'movie' : 'tv'" />
    <BangumiDetailDialog v-model:open="bangumiDetailOpen" :subject-id="bangumiDetailId" :fallback="bangumiDetailFallback" />
  </div>
</template>
