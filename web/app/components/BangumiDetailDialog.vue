<script setup lang="ts">
import { getBangumiSubjectApiV1BangumiSubjectGet } from '@/api/bangumi'
import { Star, Calendar, Clapperboard, Hash, ExternalLink } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'

const props = defineProps<{
  open: boolean
  subjectId: number | null
  fallback?: API.BangumiCalendarItem | null
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const detail = ref<API.BangumiSubjectDetail | null>(null)
const loading = ref(false)

const displayName = computed(() => {
  const d = detail.value
  const f = props.fallback
  return (d?.name_cn || d?.name || f?.name_cn || f?.name || '').trim() || '未命名'
})

const originalName = computed(() => {
  const d = detail.value
  const name = d?.name || props.fallback?.name || ''
  return name && name !== displayName.value ? name : ''
})

const displayImage = computed(() => (detail.value?.image || props.fallback?.image || '').trim())

const airDate = computed(() => detail.value?.date || props.fallback?.air_date || '')

const episodes = computed(() => {
  const d = detail.value
  return d?.total_episodes || d?.eps || null
})

const scoreText = computed(() => {
  const v = detail.value?.score ?? props.fallback?.score
  return typeof v === 'number' && v > 0 ? v.toFixed(1) : ''
})

const rankText = computed(() => {
  const r = detail.value?.rank ?? props.fallback?.rank
  return typeof r === 'number' && r > 0 ? r : null
})

// Bangumi 简介常在中文后附「[简介原文]」日文原文，展示时截掉
const summary = computed(() => {
  const raw = (detail.value?.summary || props.fallback?.summary || '').trim()
  if (!raw) return '暂无简介'
  const cut = raw.search(/\[简介原文\]/u)
  const text = (cut >= 0 ? raw.slice(0, cut) : raw).trim()
  return text || '暂无简介'
})

const tags = computed(() => (detail.value?.tags || []).filter((t) => t.name))

const detailUrl = computed(() => detail.value?.url || props.fallback?.url || '')

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen && props.subjectId != null) {
      loading.value = true
      detail.value = null
      try {
        const res = await getBangumiSubjectApiV1BangumiSubjectGet({ subject_id: props.subjectId })
        detail.value = (res?.data as API.BangumiSubjectDetail) || null
      } finally {
        loading.value = false
      }
    }
  }
)

// 打开时锁定页面滚动，避免移动端背景乱滚
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
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-3xl max-h-[88vh] overflow-y-auto overflow-x-hidden overscroll-contain w-[92vw] rounded-xl p-0">
      <!-- 顶部封面：清晰展示 + 底部渐变，与电影模态框一致 -->
      <div
        v-if="displayImage"
        class="relative h-40 sm:h-52 w-full overflow-hidden rounded-t-xl bg-muted"
      >
        <img
          :src="displayImage"
          alt=""
          referrerpolicy="no-referrer"
          class="w-full h-full object-cover"
        />
        <div class="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent" />
      </div>

      <div class="px-6 pb-6 min-w-0" :class="displayImage ? '-mt-16 relative' : 'pt-6'">
        <div class="flex gap-4">
          <div class="shrink-0 w-24 sm:w-28 rounded-lg overflow-hidden border border-border/50 shadow-lg bg-muted">
            <img
              v-if="displayImage"
              :src="displayImage"
              alt=""
              referrerpolicy="no-referrer"
              class="w-full aspect-[2/3] object-cover"
            />
            <div v-else class="w-full aspect-[2/3] flex items-center justify-center text-xs text-muted-foreground">
              无海报
            </div>
          </div>

          <div class="flex flex-col min-w-0 flex-1 pt-2 sm:pt-4">
            <DialogHeader class="space-y-1 text-left">
              <DialogTitle class="text-lg font-semibold tracking-tight leading-snug break-words">
                {{ displayName }}
              </DialogTitle>
              <DialogDescription v-if="originalName" class="text-sm break-words">
                {{ originalName }}
              </DialogDescription>
            </DialogHeader>

            <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2 text-sm text-muted-foreground">
              <span v-if="scoreText" class="inline-flex items-center gap-1 font-medium text-amber-500">
                <Star class="size-4 fill-amber-400 stroke-amber-500" />
                {{ scoreText }}
              </span>
              <span v-if="rankText" class="inline-flex items-center gap-1">
                <Hash class="size-4" /> No.{{ rankText }}
              </span>
              <span v-if="airDate" class="inline-flex items-center gap-1">
                <Calendar class="size-4" /> {{ airDate }}
              </span>
              <span v-if="episodes" class="inline-flex items-center gap-1">
                <Clapperboard class="size-4" /> {{ episodes }} 话
              </span>
            </div>

            <div v-if="tags.length" class="flex flex-wrap gap-1.5 mt-2.5">
              <span
                v-for="t in tags"
                :key="t.name ?? ''"
                class="inline-flex items-center rounded-full bg-primary/10 text-primary px-2 py-0.5 text-xs font-medium"
              >
                {{ t.name }}
              </span>
            </div>
          </div>
        </div>

        <div class="mt-4">
          <h3 class="text-sm font-semibold mb-1.5">简介</h3>
          <p class="text-sm text-muted-foreground leading-relaxed whitespace-pre-line break-words">
            {{ summary }}
          </p>
        </div>

        <a
          v-if="detailUrl"
          :href="detailUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-4 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
        >
          <ExternalLink class="size-4" /> 在 Bangumi 查看
        </a>

        <div v-if="loading" class="mt-3 text-xs text-muted-foreground/70">正在加载更多信息…</div>
      </div>
    </DialogContent>
  </Dialog>
</template>
