<script setup lang="ts">
import { searchTorrentsApiV1PiratebaySearchGet } from '@/api/pirateBay'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  ArrowUpCircle,
  ArrowDownCircle,
  HardDrive,
  Files,
  User,
  Clock,
  Tag,
  Film,
  Magnet
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

// 响应式状态：加载、列表、详情弹窗与季/集筛选
const loading = ref(false)
const items = ref<API.PirateBayTorrent[]>([])
const open = ref(false)
const selected = ref<API.PirateBayTorrent | null>(null)
const errMsg = ref<string | null>(null)
const season = ref('')
const episode = ref('')

// 从路由派生的计算属性
const q = computed(() => (route.query.q as string) || '')
const tmdbName = computed(() => (route.query.tmdbName as string) || '')
const tmdbYear = computed(() => (route.query.tmdbYear as string) || '')

// 年份筛选（可选），同步到 URL；优先从 tmdbYear 回填
const year = ref('')
watch([() => route.query.year, tmdbYear], ([urlYear, tmdb]) => {
  const fromUrl = String(urlYear ?? '')
  const fromTmdb = String(tmdb ?? '')
  if (fromUrl) year.value = fromUrl
  else if (fromTmdb) year.value = fromTmdb
  else if (!year.value) year.value = ''
}, { immediate: true })

// 从关键词中解析 SxxExx / Sxx / Exx 并回填到季/集输入框
const initFromQ = () => {
  const currentQ = q.value
  let match = currentQ.match(/(.+?)\s+S(\d+)E(\d+)/i)
  if (match) {
    season.value = match[2] ?? ''
    episode.value = match[3] ?? ''
    return
  }
  match = currentQ.match(/(.+?)\s+S(\d+)/i)
  if (match) {
    season.value = match[2] ?? ''
    episode.value = ''
    return
  }
  match = currentQ.match(/(.+?)\s+E(\d+)/i)
  if (match) {
    season.value = ''
    episode.value = match[2] ?? ''
    return
  }
  season.value = ''
  episode.value = ''
}

// 关键词变化时先解析季/集，再拉取列表
watch(() => q.value, initFromQ, { immediate: true })

watch(() => q.value, () => {
  fetchData()
})

// 挂载时拉取海盗湾搜索结果
onMounted(() => {
  fetchData()
})

// 格式化文件大小显示
const formatSize = (s: string) => {
  const n = Number(s)
  if (!isFinite(n) || n <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = n
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(2)} ${units[i]}`
}

// 格式化时间戳为本地日期时间
const formatAdded = (s: string) => {
  const n = Number(s)
  if (!isFinite(n) || n <= 0) return '—'
  const ms = n > 1e12 ? n : n * 1000
  const d = new Date(ms)
  const pad = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 应用季/集与年份筛选：拼成新关键词并写回路由，再请求
const onApplyFilter = () => {
  let base = q.value
  base = base.replace(/\s+S\d+E\d+/i, '')
             .replace(/\s+S\d+/i, '')
             .replace(/\s+E\d+/i, '')
             .trim()
  let suffix = ''
  if (season.value) {
    const s = season.value.toString().padStart(2, '0')
    suffix += ` S${s}`
    if (episode.value) {
      const e = episode.value.toString().padStart(2, '0')
      suffix += `E${e}`
    }
  }
  const newQ = suffix ? `${base}${suffix}` : base
  const newYear = (year.value && String(year.value).trim()) || undefined
  const query = { ...route.query, q: newQ } as Record<string, string>
  if (newYear) query.year = newYear
  else delete query.year
  router.replace({ query }).then(() => {
    fetchData()
  })
}

// 清除季/集和年份后重新应用筛选
const onClearFilter = () => {
  season.value = ''
  episode.value = ''
  year.value = ''
  onApplyFilter()
}

// 请求海盗湾搜索接口（关键词 + 可选年份）
const fetchData = async () => {
  const baseQ = q.value.trim()
  // 仅当用户点击「筛选」写入的 year 才参与搜索，不用 tmdbYear 默认带出
const yearPart = (route.query.year as string)?.trim() || ''
  const query = [baseQ, yearPart].filter(Boolean).join(' ')
  if (!query) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const res = await searchTorrentsApiV1PiratebaySearchGet({ q: query })
    const code = (res as any)?.code ?? 0
    const msg = (res as any)?.message ?? ''
    const data = (res as any)?.data ?? []
    const ok = code === 0 || code === 200
    if (!ok) {
      errMsg.value = msg || '搜索失败'
      items.value = []
    } else {
      errMsg.value = null
      items.value = Array.isArray(data) ? data : []
    }
  } finally {
    loading.value = false
  }
}

// 打开详情弹窗
const onOpenDetails = (it: API.PirateBayTorrent) => {
  selected.value = it
  open.value = true
}

// 跳转磁链任务创建页并携带 TMDB 信息
const openMagnetPage = (it: API.PirateBayTorrent) => {
  if (!it.magnet) return
  router.push({
    path: '/magnet',
    query: {
      magnet: it.magnet,
      name: it.name,
      size: it.size,
      seeders: it.seeders,
      leechers: it.leechers,
      num_files: it.num_files,
      username: it.username,
      added: it.added,
      category: it.category,
      imdb: it.imdb || '',
      tmdbName: tmdbName.value,
      tmdbYear: tmdbYear.value,
    },
  })
}
</script>

<template>
  <div class="px-2 md:px-0">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-2 sm:gap-4">
      <h1 class="text-lg font-semibold truncate min-w-0">海盗湾搜索：{{ q || '—' }}</h1>
      
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <div class="flex items-center gap-1">
          <span class="text-sm font-medium">年份</span>
          <Input
            v-model="year"
            class="w-14 h-8 px-2 text-center"
            placeholder="可选"
            maxlength="4"
            @keyup.enter="onApplyFilter"
          />
        </div>
        <div class="flex items-center gap-1">
            <span class="text-sm font-medium">S</span>
            <Input v-model="season" class="w-12 h-8 px-1 text-center" placeholder="01" @keyup.enter="onApplyFilter" />
        </div>
        <div class="flex items-center gap-1">
            <span class="text-sm font-medium">E</span>
            <Input 
                v-model="episode" 
                class="w-12 h-8 px-1 text-center" 
                placeholder="01" 
                :disabled="!season"
                @keyup.enter="onApplyFilter" 
            />
        </div>
        <Button size="sm" @click="onApplyFilter">筛选</Button>
        <Button size="sm" variant="outline" @click="onClearFilter">清除</Button>
      </div>
    </div>
    <AppLoadingOverlay v-if="loading" />
    <div v-else-if="items.length > 0" class="rounded-md border border-border bg-card shadow-sm">
      <ul class="divide-y divide-border">
        <li
          v-for="it in items"
          :key="it.id"
          class="p-4 md:p-5 hover:bg-muted/50 cursor-pointer"
          @click="onOpenDetails(it)"
        >
          <div class="text-sm font-medium break-words">
            {{ it.name }}
          </div>
          <div class="mt-2 text-xs text-muted-foreground grid grid-cols-[1fr_auto] items-center gap-y-2 gap-x-6">
            <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
              <span v-if="it.added">时间 {{ formatAdded(it.added) }}</span>
              <span>大小 {{ formatSize(it.size) }}</span>
              <span v-if="it.username">用户 {{ it.username }}</span>
              <span>做种 {{ it.seeders }}</span>
              <span>下载 {{ it.leechers }}</span>
              <span v-if="it.num_files">文件数 {{ it.num_files }}</span>
            </div>
            <div class="justify-self-end">
              <Button
                v-if="it.magnet"
                size="sm"
                variant="outline"
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
      <Button v-if="errMsg" size="sm" @click="fetchData">刷新</Button>
    </AppEmpty>
    <Dialog v-model:open="open">
      <DialogContent class="max-w-2xl max-h-[85vh] overflow-y-auto w-[90vw] sm:w-full rounded-xl">
        <DialogHeader>
          <DialogTitle class="text-lg font-semibold tracking-tight leading-normal">{{ selected?.name || '详情' }}</DialogTitle>
          <DialogDescription>
            海盗湾资源详情
          </DialogDescription>
        </DialogHeader>
        
        <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-6 p-4 rounded-lg bg-muted/30 border border-border/50">
          <!-- Seeders -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <ArrowUpCircle class="w-3.5 h-3.5" /> 做种 (Seeders)
            </span>
            <span class="font-mono text-sm pl-6 font-medium">{{ selected?.seeders || '—' }}</span>
          </div>

          <!-- Leechers -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <ArrowDownCircle class="w-3.5 h-3.5" /> 下载 (Leechers)
            </span>
            <span class="font-mono text-sm pl-6">{{ selected?.leechers || '—' }}</span>
          </div>

          <!-- Size -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <HardDrive class="w-3.5 h-3.5" /> 大小
            </span>
            <span class="font-mono text-sm pl-6">{{ formatSize(selected?.size || '') }}</span>
          </div>

          <!-- Files -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Files class="w-3.5 h-3.5" /> 文件数
            </span>
            <span class="font-mono text-sm pl-6">{{ selected?.num_files || '—' }}</span>
          </div>

          <!-- User -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <User class="w-3.5 h-3.5" /> 发布用户
            </span>
            <span class="font-mono text-sm pl-6 truncate" :title="selected?.username">{{ selected?.username || '—' }}</span>
          </div>

          <!-- Date -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Clock class="w-3.5 h-3.5" /> 发布时间
            </span>
            <span class="font-mono text-sm pl-6">{{ formatAdded(selected?.added || '') }}</span>
          </div>

          <!-- Category -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Tag class="w-3.5 h-3.5" /> 分类
            </span>
            <span class="font-mono text-sm pl-6">{{ selected?.category || '—' }}</span>
          </div>

          <!-- IMDb -->
          <div class="flex flex-col gap-1.5">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Film class="w-3.5 h-3.5" /> IMDb
            </span>
            <span class="font-mono text-sm pl-6 truncate">{{ selected?.imdb || '—' }}</span>
          </div>
        </div>

        <div class="mt-2 flex justify-end">
            <Button
            v-if="selected?.magnet"
            class="w-full sm:w-auto gap-2"
            @click="selected && openMagnetPage(selected)"
            >
            <Magnet class="w-4 h-4" />
            打开磁力链接
            </Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
