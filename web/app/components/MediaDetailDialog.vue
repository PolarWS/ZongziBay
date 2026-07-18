<script setup lang="ts">
import {
  Star,
  CalendarDays,
  Clock,
  Layers,
  Globe,
  ExternalLink,
  Users,
  Activity,
  MapPin,
  Tv,
  ChevronLeft,
  ChevronRight,
} from 'lucide-vue-next'
import {
  getMovieDetailApiV1TmdbMovieMovieIdGet,
  getTvDetailApiV1TmdbTvTvIdGet,
} from '@/api/tmdb'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'

// 兼容电影与剧集两种数据结构（列表项 + 详情字段）
type MediaItem = Partial<API.TMDBMovieDetail> & Partial<API.TMDBTVDetail>

const props = defineProps<{
  open: boolean
  media: MediaItem | null
  type: 'tv' | 'movie'
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { imgUrl } = useTmdbImage()

// 完整详情（打开时按需拉取），未拉到前回退到列表项数据
const detail = ref<MediaItem | null>(null)
const loading = ref(false)

// 实际用于渲染的数据：优先完整详情，其次列表项
const data = computed<MediaItem | null>(() => detail.value || props.media)

// 打开且有 id 时拉取完整详情
watch(
  () => [props.open, props.media?.id] as const,
  async ([open, id]) => {
    if (!open || !id) return
    detail.value = null
    loading.value = true
    try {
      const res =
        props.type === 'tv'
          ? await getTvDetailApiV1TmdbTvTvIdGet({ tv_id: id })
          : await getMovieDetailApiV1TmdbMovieMovieIdGet({ movie_id: id })
      detail.value = (res?.data as MediaItem) || null
    } catch {
      detail.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)

const title = computed(() =>
  props.type === 'tv'
    ? data.value?.name || data.value?.original_name || '未命名'
    : data.value?.title || data.value?.original_title || '未命名'
)

const originalTitle = computed(() =>
  props.type === 'tv' ? data.value?.original_name || '' : data.value?.original_title || ''
)

const date = computed(() =>
  props.type === 'tv' ? data.value?.first_air_date || '' : data.value?.release_date || ''
)

const rating = computed(() => {
  const v = data.value?.vote_average
  return typeof v === 'number' && v > 0 ? v.toFixed(1) : ''
})

const voteCount = computed(() => data.value?.vote_count || 0)

const overview = computed(() => data.value?.overview || '暂无简介')

const posterUrl = computed(() => imgUrl(data.value?.poster_path, 'w300'))
const backdropUrl = computed(() => imgUrl(data.value?.backdrop_path, 'w780'))

const tagline = computed(() => data.value?.tagline || '')

const genres = computed(() => (data.value?.genres || []).map((g) => g.name).filter(Boolean) as string[])

const status = computed(() => data.value?.status || '')

const homepage = computed(() => data.value?.homepage || '')

// 电影时长（分钟）
const runtime = computed(() => (props.type === 'movie' ? data.value?.runtime || 0 : 0))

// 剧集单集时长（取第一个）
const episodeRuntime = computed(() =>
  props.type === 'tv' ? data.value?.episode_run_time?.[0] || 0 : 0
)

const seasons = computed(() => (props.type === 'tv' ? data.value?.number_of_seasons || 0 : 0))
const episodes = computed(() => (props.type === 'tv' ? data.value?.number_of_episodes || 0 : 0))

const networks = computed(() =>
  props.type === 'tv' ? (data.value?.networks || []).map((n) => n.name).filter(Boolean) as string[] : []
)

const createdBy = computed(() =>
  props.type === 'tv'
    ? (data.value?.created_by || []).map((c) => c.name).filter(Boolean) as string[]
    : []
)

const countries = computed(
  () => (data.value?.production_countries || []).map((c) => c.name).filter(Boolean) as string[]
)

const languages = computed(
  () =>
    (data.value?.spoken_languages || [])
      .map((l) => l.name || l.english_name)
      .filter(Boolean) as string[]
)

// 演员阵容
const cast = computed(() => data.value?.cast || [])

// 演员头像 URL（无则返回空，模板回退到首字母占位）
const castAvatar = (path: string | null | undefined) => imgUrl(path, 'w185')

// 演员阵容横向滚动控制
const castScrollRef = ref<HTMLElement | null>(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)

// 根据滚动位置更新左右按钮/渐变的显隐
const updateCastScroll = () => {
  const el = castScrollRef.value
  if (!el) {
    canScrollLeft.value = false
    canScrollRight.value = false
    return
  }
  canScrollLeft.value = el.scrollLeft > 4
  canScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 4
}

// 点击左右按钮滚动一屏（80%）
const scrollCast = (dir: 'left' | 'right') => {
  const el = castScrollRef.value
  if (!el) return
  const amount = el.clientWidth * 0.8
  el.scrollBy({ left: dir === 'left' ? -amount : amount, behavior: 'smooth' })
}

// 演员数据变化后重新计算滚动状态
watch(cast, async () => {
  await nextTick()
  updateCastScroll()
})

// 打开时锁定页面滚动，避免移动端背景乱滚（滚动穿透）
watch(
  () => props.open,
  (open) => {
    if (typeof document === 'undefined') return
    document.body.style.overflow = open ? 'hidden' : ''
  }
)

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})

// 把分钟格式化为 "x 小时 y 分钟"
const formatRuntime = (min: number) => {
  if (!min) return ''
  const h = Math.floor(min / 60)
  const m = min % 60
  return h > 0 ? `${h} 小时 ${m} 分钟` : `${m} 分钟`
}

// 状态英文 -> 中文
const statusText = computed(() => {
  const map: Record<string, string> = {
    Released: '已上映',
    'Post Production': '后期制作',
    'In Production': '制作中',
    Planned: '筹备中',
    Rumored: '传闻中',
    Canceled: '已取消',
    'Returning Series': '连载中',
    Ended: '已完结',
    Pilot: '试播',
  }
  return map[status.value] || status.value
})
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-3xl max-h-[88vh] overflow-y-auto overflow-x-hidden overscroll-contain w-[92vw] rounded-xl p-0">
      <!-- 背景图 -->
      <div
        v-if="backdropUrl"
        class="relative h-40 sm:h-52 w-full overflow-hidden rounded-t-xl bg-muted"
      >
        <img :src="backdropUrl" alt="" class="w-full h-full object-cover" />
        <div class="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent" />
      </div>

      <div class="px-6 pb-6 min-w-0" :class="backdropUrl ? '-mt-16 relative' : 'pt-6'">
        <div class="flex gap-4">
          <div class="shrink-0 w-24 sm:w-28 rounded-lg overflow-hidden border border-border/50 shadow-lg bg-muted">
            <img
              v-if="posterUrl"
              :src="posterUrl"
              alt=""
              class="w-full aspect-[2/3] object-cover"
            />
            <div v-else class="w-full aspect-[2/3] flex items-center justify-center text-xs text-muted-foreground">
              无海报
            </div>
          </div>

          <div class="flex flex-col min-w-0 flex-1 pt-2 sm:pt-4">
            <DialogHeader class="space-y-1 text-left">
              <DialogTitle class="text-lg font-semibold tracking-tight leading-snug break-words">
                {{ title }}
              </DialogTitle>
              <DialogDescription v-if="originalTitle && originalTitle !== title" class="text-sm break-words">
                {{ originalTitle }}
              </DialogDescription>
            </DialogHeader>

            <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2 text-sm text-muted-foreground">
              <span v-if="rating" class="inline-flex items-center gap-1 font-medium text-amber-500">
                <Star class="size-4 fill-amber-400 stroke-amber-500" />
                {{ rating }}
                <span v-if="voteCount" class="text-xs text-muted-foreground/70">({{ voteCount }})</span>
              </span>
              <span v-if="date" class="inline-flex items-center gap-1">
                <CalendarDays class="size-4" />
                {{ date }}
              </span>
              <span v-if="type === 'movie' && runtime" class="inline-flex items-center gap-1">
                <Clock class="size-4" />
                {{ formatRuntime(runtime) }}
              </span>
              <span v-if="type === 'tv' && (seasons || episodes)" class="inline-flex items-center gap-1">
                <Layers class="size-4" />
                <template v-if="seasons">{{ seasons }} 季</template>
                <template v-if="episodes"> · {{ episodes }} 集</template>
              </span>
              <span v-if="type === 'tv' && episodeRuntime" class="inline-flex items-center gap-1">
                <Clock class="size-4" />
                单集 {{ episodeRuntime }} 分钟
              </span>
            </div>

            <!-- 类型标签 -->
            <div v-if="genres.length" class="flex flex-wrap gap-1.5 mt-2.5">
              <span
                v-for="g in genres"
                :key="g"
                class="inline-flex items-center rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium"
              >
                {{ g }}
              </span>
            </div>
          </div>
        </div>

        <!-- 标语 -->
        <p v-if="tagline" class="mt-4 text-sm italic text-muted-foreground/90">“{{ tagline }}”</p>

        <!-- 简介 -->
        <div class="mt-4">
          <h3 class="text-sm font-semibold mb-1.5">剧情简介</h3>
          <p class="text-sm text-muted-foreground leading-relaxed whitespace-pre-line break-words">
            {{ overview }}
          </p>
        </div>

        <!-- 附加信息 -->
        <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div v-if="status" class="flex items-start gap-2 min-w-0">
            <span class="text-muted-foreground shrink-0 inline-flex items-center gap-1"><Activity class="size-3.5" />状态</span>
            <span class="font-medium break-words min-w-0">{{ statusText }}</span>
          </div>
          <div v-if="createdBy.length" class="flex items-start gap-2 min-w-0">
            <span class="text-muted-foreground shrink-0 inline-flex items-center gap-1"><Users class="size-3.5" />主创</span>
            <span class="font-medium break-words min-w-0">{{ createdBy.join('、') }}</span>
          </div>
          <div v-if="networks.length" class="flex items-start gap-2 min-w-0">
            <span class="text-muted-foreground shrink-0 inline-flex items-center gap-1"><Tv class="size-3.5" />播出平台</span>
            <span class="font-medium break-words min-w-0">{{ networks.join('、') }}</span>
          </div>
          <div v-if="countries.length" class="flex items-start gap-2 min-w-0">
            <span class="text-muted-foreground shrink-0 inline-flex items-center gap-1"><MapPin class="size-3.5" />制片地区</span>
            <span class="font-medium break-words min-w-0">{{ countries.join('、') }}</span>
          </div>
          <div v-if="languages.length" class="flex items-start gap-2 min-w-0">
            <span class="text-muted-foreground shrink-0 inline-flex items-center gap-1"><Globe class="size-3.5" />语言</span>
            <span class="font-medium break-words min-w-0">{{ languages.join('、') }}</span>
          </div>
        </div>

        <!-- 演员阵容 -->
        <div v-if="cast.length" class="mt-6">
          <h3 class="text-sm font-semibold mb-3">演员阵容</h3>
          <div class="relative">
            <!-- 左侧渐变遮罩 + 按钮 -->
            <div
              v-show="canScrollLeft"
              class="pointer-events-none absolute left-0 top-0 bottom-0 w-14 bg-gradient-to-r from-background to-transparent z-10"
            />
            <button
              v-show="canScrollLeft"
              type="button"
              aria-label="向左滚动"
              class="group/btn absolute left-1.5 top-[34%] -translate-y-1/2 z-20 inline-flex items-center justify-center size-9 rounded-full bg-background/70 backdrop-blur-md border border-border/60 shadow-lg ring-1 ring-black/5 text-foreground/70 hover:text-foreground hover:bg-background hover:scale-110 active:scale-95 transition-all duration-200 cursor-pointer"
              @click="scrollCast('left')"
            >
              <ChevronLeft class="size-4 transition-transform duration-200 group-hover/btn:-translate-x-0.5" />
            </button>

            <div
              ref="castScrollRef"
              class="flex gap-3 overflow-x-auto pb-1 cast-scroll"
              @scroll="updateCastScroll"
            >
              <div
                v-for="(c, idx) in cast"
                :key="(c.id ?? idx) + '-' + idx"
                class="shrink-0 w-[92px] rounded-xl border border-border/60 bg-muted/30 overflow-hidden transition-colors hover:bg-muted/60"
              >
                <div class="w-full aspect-[2/3] bg-muted overflow-hidden">
                  <img
                    v-if="c.profile_path"
                    :src="castAvatar(c.profile_path)"
                    :alt="c.name || ''"
                    class="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div
                    v-else
                    class="w-full h-full flex items-center justify-center text-2xl font-semibold text-muted-foreground/60 bg-gradient-to-br from-muted to-muted/50"
                  >
                    {{ (c.name || '?').slice(0, 1) }}
                  </div>
                </div>
                <div class="px-2 py-2">
                  <div class="text-xs font-semibold leading-tight line-clamp-2 break-words">{{ c.name }}</div>
                  <div v-if="c.character" class="mt-0.5 text-[11px] text-muted-foreground leading-tight line-clamp-2 break-words">
                    {{ c.character }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 右侧渐变遮罩 + 按钮 -->
            <div
              v-show="canScrollRight"
              class="pointer-events-none absolute right-0 top-0 bottom-0 w-14 bg-gradient-to-l from-background to-transparent z-10"
            />
            <button
              v-show="canScrollRight"
              type="button"
              aria-label="向右滚动"
              class="group/btn absolute right-1.5 top-[34%] -translate-y-1/2 z-20 inline-flex items-center justify-center size-9 rounded-full bg-background/70 backdrop-blur-md border border-border/60 shadow-lg ring-1 ring-black/5 text-foreground/70 hover:text-foreground hover:bg-background hover:scale-110 active:scale-95 transition-all duration-200 cursor-pointer"
              @click="scrollCast('right')"
            >
              <ChevronRight class="size-4 transition-transform duration-200 group-hover/btn:translate-x-0.5" />
            </button>
          </div>
        </div>

        <!-- 官网链接 -->
        <a
          v-if="homepage"
          :href="homepage"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-4 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
        >
          <ExternalLink class="size-4" />
          访问官方网站
        </a>

        <div v-if="loading" class="mt-3 text-xs text-muted-foreground/70">正在加载更多信息…</div>
      </div>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.cast-scroll {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.cast-scroll::-webkit-scrollbar {
  display: none;
}
</style>
