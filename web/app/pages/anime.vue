<script setup lang="ts">
import { animeGardenSearch } from '@/api/animeGarden'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import AppPagination from '@/components/AppPagination.vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, Magnet, X } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

// 响应式状态与配置
const loading = ref(false)
const items = ref<API.AnimeGardenResource[]>([])
const open = ref(false)
const selected = ref<API.AnimeGardenResource | null>(null)
const errMsg = ref<string | null>(null)
const FANSUB_TAGS_KEY = 'anime_fansub_tags'
const customFansubTags = ref<string[]>([])
const customFansubInput = ref('')
const selectedFansub = ref('')
const page = ref(1)
const pageSize = 20
const apiComplete = ref(true)
const inputKeyword = ref('')

// 从路由与列表派生的计算属性
const q = computed(() => (route.query.q as string) || '')
// 字幕组列表：从当前搜索结果中探测（按数量排序），点击后通过 API fansub 参数筛选
const fansubList = computed(() => {
  const map = new Map<string, number>()
  items.value.forEach(it => {
    const name = it.fansub?.name
    if (name) map.set(name, (map.get(name) || 0) + 1)
  })
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
})
// 列表直接使用接口返回的 items（字幕组筛选通过 API 的 fansub 参数完成）
const filteredItems = computed(() => items.value)
// 总数：API 仅在 complete 时可知；用于文案展示
const totalCount = computed(() => {
  const base = (page.value - 1) * pageSize + items.value.length
  if (apiComplete.value) return base
  return Math.max(base, page.value * pageSize)
})
// 分页组件用 total：必须 total > pageSize 才会显示分页。未 complete 时至少设为 (page+1)*pageSize，保证“下一页”可点
const totalForPagination = computed(() => {
  if (apiComplete.value) {
    const total = (page.value - 1) * pageSize + items.value.length
    return Math.max(total, 1)
  }
  return (page.value + 1) * pageSize
})
const tmdbName = computed(() => (route.query.tmdbName as string) || '')
const tmdbYear = computed(() => (route.query.tmdbYear as string) || '')

// 地址栏关键词变化时同步输入框并拉取数据
watch(() => q.value, (v) => {
  inputKeyword.value = v
  page.value = 1
  selectedFansub.value = ''
  fetchData()
}, { immediate: false })

watch(() => page.value, () => {
  fetchData()
})

// 挂载时从本地恢复自定义标签并拉取搜索数据
onMounted(() => {
  inputKeyword.value = q.value
  try {
    const raw = localStorage.getItem(FANSUB_TAGS_KEY)
    if (raw) {
      const arr = JSON.parse(raw)
      if (Array.isArray(arr)) customFansubTags.value = arr.filter((t): t is string => typeof t === 'string')
    }
  } catch (_) {}
  fetchData()
})

// 切换选中字幕组并重新请求
function toggleFansub(name: string) {
  const next = selectedFansub.value === name ? '' : name
  selectedFansub.value = next
  page.value = 1
  fetchData()
}

// 添加自定义字幕组标签并持久化
function addCustomTag() {
  const v = customFansubInput.value.trim()
  if (!v) return
  if (customFansubTags.value.includes(v)) {
    customFansubInput.value = ''
    return
  }
  customFansubTags.value = [...customFansubTags.value, v]
  try {
    localStorage.setItem(FANSUB_TAGS_KEY, JSON.stringify(customFansubTags.value))
  } catch (_) {}
  customFansubInput.value = ''
}

// 移除自定义标签，若当前选中则清空筛选并刷新
function removeCustomTag(tag: string) {
  customFansubTags.value = customFansubTags.value.filter(t => t !== tag)
  try {
    localStorage.setItem(FANSUB_TAGS_KEY, JSON.stringify(customFansubTags.value))
  } catch (_) {}
  if (selectedFansub.value === tag) {
    selectedFansub.value = ''
    page.value = 1
    fetchData()
  }
}

// 清空字幕组筛选并刷新
function clearFansub() {
  selectedFansub.value = ''
  page.value = 1
  fetchData()
}

// 提交搜索：写入路由并触发 watch 拉数
function onSearch() {
  const v = inputKeyword.value.trim()
  if (!v) return
  page.value = 1
  selectedFansub.value = ''
  router.replace({ path: '/anime', query: { q: v } })
}

// 请求动漫花园搜索接口
async function fetchData() {
  const query = q.value.trim()
  if (!query) {
    items.value = []
    return
  }
  loading.value = true
  errMsg.value = null
  try {
    const res = await animeGardenSearch({
      q: query,
      page: page.value,
      page_size: pageSize,
      fansub: selectedFansub.value || undefined,
    })
    const data = (res as any)?.data
    if (!data || !Array.isArray(data.resources)) {
      items.value = []
      return
    }
    items.value = data.resources
    apiComplete.value = data.pagination?.complete ?? (data.resources.length < pageSize)
  } catch (e: any) {
    errMsg.value = e?.message || '搜索失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

// 打开详情弹窗
function onOpenDetails(it: API.AnimeGardenResource) {
  selected.value = it
  open.value = true
}

// 新窗口打开原页
function openLink(href: string) {
  if (href) window.open(href, '_blank')
}

// 跳转磁链任务页并携带 TMDB 信息
function openMagnetPage(it: API.AnimeGardenResource) {
  if (!it.magnet) return
  router.push({
    path: '/magnet',
    query: {
      magnet: it.magnet,
      name: it.title,
      size: String(it.size),
      tmdbName: tmdbName.value,
      tmdbYear: tmdbYear.value,
      source: 'anime',
    },
  })
}

// 格式化体积显示（KB → MB/GB）
function formatSize(kb: number) {
  if (!kb || !Number.isFinite(kb)) return '—'
  const n = kb / 1024
  if (n >= 1024) return `${(n / 1024).toFixed(2)} GB`
  return `${n.toFixed(2)} MB`
}

// 格式化 ISO 日期为本地短格式
function formatDate(iso: string) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}
</script>

<template>
  <div class="px-2 md:px-0">
    <div class="flex flex-col gap-4 mb-4">
      <h1 class="text-lg font-semibold truncate min-w-0">动漫花园</h1>
      <form class="flex gap-2" @submit.prevent="onSearch">
        <Input
          v-model="inputKeyword"
          class="flex-1 max-w-md h-9"
          placeholder="输入关键词搜索（支持中文/繁体）"
          type="search"
        />
        <Button type="submit" class="h-9">搜索</Button>
      </form>
      <div v-if="q" class="flex flex-col gap-2">
        <p class="text-sm text-muted-foreground">当前搜索：{{ q }}</p>
        <div class="flex flex-wrap gap-2 items-center">
          <Badge
            v-for="fs in fansubList"
            :key="fs.name"
            :variant="selectedFansub === fs.name ? 'default' : 'outline'"
            class="cursor-pointer hover:opacity-80 select-none h-7 px-2.5 text-xs leading-none flex items-center"
            @click="toggleFansub(fs.name)"
          >
            {{ fs.name }}
            <span class="ml-1 text-[10px] opacity-70">{{ fs.count }}</span>
          </Badge>
          <template v-if="customFansubTags.length > 0">
            <div v-if="fansubList.length > 0" class="w-px h-4 bg-border shrink-0 self-center" />
            <Badge
              v-for="tag in customFansubTags"
              :key="tag"
              :variant="selectedFansub === tag ? 'default' : 'secondary'"
              class="cursor-pointer hover:opacity-80 select-none h-7 px-2.5 text-xs leading-none flex items-center gap-0.5 pr-1"
              @click="toggleFansub(tag)"
            >
              {{ tag }}
              <span
                class="ml-1 opacity-50 hover:opacity-100 hover:bg-destructive/10 rounded-full w-4 h-4 inline-flex items-center justify-center text-xs leading-none cursor-pointer"
                aria-label="移除标签"
                @click.stop="removeCustomTag(tag)"
              >
                <X class="w-3 h-3" />
              </span>
            </Badge>
          </template>
          <div class="flex items-center gap-1 ml-1 shrink-0">
            <Input
              v-model="customFansubInput"
              type="text"
              class="h-7 w-20 sm:w-24 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="自定义标签"
              @keydown.enter="addCustomTag"
            />
            <Button
              size="sm"
              variant="ghost"
              class="h-7 w-7 p-0 shrink-0"
              :disabled="!customFansubInput.trim()"
              @click="addCustomTag"
            >
              <span class="text-lg leading-none mb-0.5">+</span>
            </Button>
          </div>
          <Button
            v-if="selectedFansub"
            type="button"
            size="sm"
            variant="ghost"
            class="h-7 text-muted-foreground text-xs shrink-0 px-2"
            @click="clearFansub"
          >
            取消筛选
          </Button>
        </div>
      </div>
    </div>
    <AppLoadingOverlay v-if="loading" />
    <div v-else-if="filteredItems.length > 0" class="rounded-md border border-border bg-card shadow-sm">
      <ul class="divide-y divide-border">
        <li
          v-for="it in filteredItems"
          :key="it.id"
          class="p-4 md:p-5 hover:bg-muted/50 cursor-pointer"
          @click="onOpenDetails(it)"
        >
          <div class="text-sm font-medium break-words">
            {{ it.title }}
          </div>
          <div class="mt-2 text-xs text-muted-foreground grid grid-cols-[1fr_auto] items-center gap-y-2 gap-x-6">
            <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
              <span>类型 {{ it.type }}</span>
              <span>大小 {{ formatSize(it.size) }}</span>
              <span v-if="it.fansub?.name">字幕 {{ it.fansub.name }}</span>
              <span v-if="it.publisher?.name">发布 {{ it.publisher.name }}</span>
              <span>时间 {{ formatDate(it.createdAt) }}</span>
            </div>
            <div class="justify-self-end flex gap-2">
              <Button
                v-if="it.href"
                size="sm"
                variant="ghost"
                class="h-7"
                @click.stop="openLink(it.href)"
              >
                原页
              </Button>
              <Button
                v-if="it.magnet"
                size="sm"
                variant="outline"
                class="h-7"
                @click.stop="openMagnetPage(it)"
              >
                磁力
              </Button>
            </div>
          </div>
        </li>
      </ul>
    </div>
    <AppEmpty v-else :title="errMsg ? '搜索失败' : '暂无结果'">
      <Button v-if="errMsg" size="sm" class="h-8" @click="fetchData">刷新</Button>
    </AppEmpty>
    <div v-if="filteredItems.length > 0" class="flex flex-col items-center gap-2 mt-4 mb-4">
      <p class="text-sm text-muted-foreground">
        <template v-if="apiComplete">共 {{ totalCount }} 条</template>
        <template v-else>第 {{ page }} 页，已加载 {{ (page - 1) * pageSize + filteredItems.length }} 条</template>
      </p>
      <AppPagination
        v-model:page="page"
        :items-per-page="pageSize"
        :total="totalForPagination"
      />
    </div>
    <Dialog v-model:open="open">
      <DialogContent class="max-w-2xl max-h-[85vh] overflow-y-auto w-[90vw] sm:w-full rounded-xl">
        <DialogHeader>
          <DialogTitle class="text-lg font-semibold tracking-tight leading-normal line-clamp-2">{{ selected?.title || '详情' }}</DialogTitle>
          <DialogDescription>
            动漫花园资源详情
          </DialogDescription>
        </DialogHeader>
        <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-6 p-4 rounded-lg bg-muted/30 border border-border/50">
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs">类型</span>
            <span class="font-mono text-sm">{{ selected?.type || '—' }}</span>
          </div>
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs">大小</span>
            <span class="font-mono text-sm">{{ selected ? formatSize(selected.size) : '—' }}</span>
          </div>
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs">字幕组</span>
            <span class="font-mono text-sm">{{ selected?.fansub?.name || '—' }}</span>
          </div>
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs">发布者</span>
            <span class="font-mono text-sm">{{ selected?.publisher?.name || '—' }}</span>
          </div>
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs">时间</span>
            <span class="font-mono text-sm">{{ selected ? formatDate(selected.createdAt) : '—' }}</span>
          </div>
        </div>
        <div class="mt-2 flex flex-wrap gap-2 justify-center items-center">
          <Button
            v-if="selected?.href"
            size="sm"
            variant="outline"
            class="!h-8 gap-2"
            @click="selected && openLink(selected.href)"
          >
            <ExternalLink class="w-4 h-4" />
            打开原页
          </Button>
          <Button
            v-if="selected?.magnet"
            size="sm"
            class="!h-[31px] gap-2"
            @click="selected && openMagnetPage(selected)"
          >
            <Magnet class="w-4 h-4" />
            磁力链接
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
