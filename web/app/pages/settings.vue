<script setup lang="ts">
import {
  getPathConfigApiV1SystemPathsGet,
  getRenameTemplatesApiV1SystemRenameTemplatesGet,
  getTrackersApiV1SystemTrackersGet,
} from '@/api/system'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { FolderOpen, List, Palette, Info } from 'lucide-vue-next'

// --- 本地偏好 key ---
const THEME_KEY = 'zongzi_theme'
const DEFAULT_SEARCH_SOURCE_KEY = 'zongzi_default_search_source'
const DEFAULT_TYPE_KEY = 'zongzi_default_type'

type Theme = 'light' | 'dark' | 'system'
type SearchSource = 'piratebay' | 'anime'
type DefaultType = 'movie' | 'tv'

// --- 只读数据：路径、模板、Tracker ---
const paths = ref<Record<string, string>>({})
const renameTemplates = ref<Record<string, string>>({})
const trackers = ref<string[]>([])
const loadingPaths = ref(false)
const loadingTemplates = ref(false)
const loadingTrackers = ref(false)

const loadPaths = async () => {
  loadingPaths.value = true
  try {
    const res = await getPathConfigApiV1SystemPathsGet()
    const data = (res as any)?.data
    paths.value = data && typeof data === 'object' ? data : {}
  } finally {
    loadingPaths.value = false
  }
}

const loadTemplates = async () => {
  loadingTemplates.value = true
  try {
    const res = await getRenameTemplatesApiV1SystemRenameTemplatesGet()
    const data = (res as any)?.data
    renameTemplates.value = data && typeof data === 'object' ? data : {}
  } finally {
    loadingTemplates.value = false
  }
}

const loadTrackers = async () => {
  loadingTrackers.value = true
  try {
    const res = await getTrackersApiV1SystemTrackersGet()
    const data = (res as any)?.data
    trackers.value = Array.isArray(data) ? data : []
  } finally {
    loadingTrackers.value = false
  }
}

// --- 偏好（localStorage）---
const theme = ref<Theme>('system')
const defaultSearchSource = ref<SearchSource>('piratebay')
const defaultType = ref<DefaultType>('tv')

const applyTheme = (v: Theme) => {
  const root = document.documentElement
  if (v === 'dark') {
    root.classList.add('dark')
  } else if (v === 'light') {
    root.classList.remove('dark')
  } else {
    const prefersDark = typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
    if (prefersDark) root.classList.add('dark')
    else root.classList.remove('dark')
  }
}

const setTheme = (v: Theme) => {
  theme.value = v
  if (typeof localStorage !== 'undefined') localStorage.setItem(THEME_KEY, v)
  applyTheme(v)
}

const setDefaultSearchSource = (v: SearchSource) => {
  defaultSearchSource.value = v
  if (typeof localStorage !== 'undefined') localStorage.setItem(DEFAULT_SEARCH_SOURCE_KEY, v)
}

const setDefaultType = (v: DefaultType) => {
  defaultType.value = v
  if (typeof localStorage !== 'undefined') localStorage.setItem(DEFAULT_TYPE_KEY, v)
}

onMounted(() => {
  if (typeof localStorage === 'undefined') return
  const t = localStorage.getItem(THEME_KEY) as Theme | null
  if (t && ['light', 'dark', 'system'].includes(t)) {
    theme.value = t
    applyTheme(t)
  } else {
    applyTheme('system')
  }
  const s = localStorage.getItem(DEFAULT_SEARCH_SOURCE_KEY) as SearchSource | null
  if (s && (s === 'piratebay' || s === 'anime')) defaultSearchSource.value = s
  const d = localStorage.getItem(DEFAULT_TYPE_KEY) as DefaultType | null
  if (d && (d === 'movie' || d === 'tv')) defaultType.value = d

  loadPaths()
  loadTemplates()
  loadTrackers()
})

let systemThemeMedia: MediaQueryList | null = null
const systemThemeHandler = () => {
  if (theme.value === 'system') applyTheme('system')
}
onMounted(() => {
  if (typeof window === 'undefined') return
  systemThemeMedia = window.matchMedia('(prefers-color-scheme: dark)')
  systemThemeMedia.addEventListener('change', systemThemeHandler)
})
onUnmounted(() => {
  if (systemThemeMedia) systemThemeMedia.removeEventListener('change', systemThemeHandler)
})
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-8">
    <h1 class="text-2xl font-semibold tracking-tight">设置</h1>

    <!-- 偏好 -->
    <section class="rounded-xl border border-border bg-card p-4 sm:p-6 space-y-4">
      <div class="flex items-center gap-2 text-muted-foreground">
        <Palette class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">偏好</h2>
      </div>
      <div class="space-y-4 pl-7">
        <div class="space-y-2">
          <Label>主题</Label>
          <div class="flex flex-wrap gap-2">
            <Button
              :variant="theme === 'light' ? 'default' : 'outline'"
              size="sm"
              @click="setTheme('light')"
            >
              浅色
            </Button>
            <Button
              :variant="theme === 'dark' ? 'default' : 'outline'"
              size="sm"
              @click="setTheme('dark')"
            >
              深色
            </Button>
            <Button
              :variant="theme === 'system' ? 'default' : 'outline'"
              size="sm"
              @click="setTheme('system')"
            >
              跟随系统
            </Button>
          </div>
        </div>
        <div class="space-y-2">
          <Label>推荐页 / 搜索跳转默认来源</Label>
          <div class="flex flex-wrap gap-2">
            <Button
              :variant="defaultSearchSource === 'piratebay' ? 'default' : 'outline'"
              size="sm"
              @click="setDefaultSearchSource('piratebay')"
            >
              海盗湾
            </Button>
            <Button
              :variant="defaultSearchSource === 'anime' ? 'default' : 'outline'"
              size="sm"
              @click="setDefaultSearchSource('anime')"
            >
              动漫花园
            </Button>
          </div>
        </div>
        <div class="space-y-2">
          <Label>首页默认类型</Label>
          <div class="flex flex-wrap gap-2">
            <Button
              :variant="defaultType === 'movie' ? 'default' : 'outline'"
              size="sm"
              @click="setDefaultType('movie')"
            >
              电影
            </Button>
            <Button
              :variant="defaultType === 'tv' ? 'default' : 'outline'"
              size="sm"
              @click="setDefaultType('tv')"
            >
              剧集
            </Button>
          </div>
        </div>
      </div>
    </section>

    <!-- 路径与模板（只读） -->
    <section class="rounded-xl border border-border bg-card p-4 sm:p-6 space-y-4">
      <div class="flex items-center gap-2 text-muted-foreground">
        <FolderOpen class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">路径与重命名</h2>
      </div>
      <p class="text-sm text-muted-foreground pl-7">以下为只读展示，修改请编辑服务端 config 后重启。</p>
      <div class="space-y-4 pl-7">
        <div class="space-y-2">
          <Label>路径配置</Label>
          <div v-if="loadingPaths" class="text-sm text-muted-foreground">加载中…</div>
          <pre v-else-if="Object.keys(paths).length" class="text-xs text-foreground rounded-lg bg-muted p-3 overflow-x-auto">{{ paths }}</pre>
          <div v-else class="text-sm text-muted-foreground">暂无</div>
        </div>
        <div class="space-y-2">
          <Label>重命名模板</Label>
          <div v-if="loadingTemplates" class="text-sm text-muted-foreground">加载中…</div>
          <pre v-else-if="Object.keys(renameTemplates).length" class="text-xs text-foreground rounded-lg bg-muted p-3 overflow-x-auto">{{ renameTemplates }}</pre>
          <div v-else class="text-sm text-muted-foreground">暂无</div>
        </div>
      </div>
    </section>

    <!-- Tracker -->
    <section class="rounded-xl border border-border bg-card p-4 sm:p-6 space-y-4">
      <div class="flex items-center gap-2 text-muted-foreground">
        <List class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">BT Tracker</h2>
      </div>
      <div class="pl-7">
        <div v-if="loadingTrackers" class="text-sm text-muted-foreground">加载中…</div>
        <ul v-else-if="trackers.length" class="text-sm text-muted-foreground list-disc list-inside space-y-1">
          <li v-for="(t, i) in trackers" :key="i" class="break-all">{{ t }}</li>
        </ul>
        <div v-else class="text-sm text-muted-foreground">暂无</div>
      </div>
    </section>

    <!-- 关于 -->
    <section class="rounded-xl border border-border bg-card p-4 sm:p-6 space-y-4">
      <div class="flex items-center gap-2 text-muted-foreground">
        <Info class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">关于</h2>
      </div>
      <div class="pl-7 space-y-1 text-sm text-muted-foreground">
        <p>粽子湾资源助手 — 聚合磁链搜索、qBittorrent 推送与智能重命名。</p>
      </div>
    </section>
  </div>
</template>
