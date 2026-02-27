<script setup lang="ts">
import { getConfigApiV1SystemConfigGet, saveConfigApiV1SystemConfigPut } from '@/api/system'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import Checkbox from '@/components/ui/checkbox/Checkbox.vue'
import { Palette, Info, FileJson, Shield, Clapperboard, DownloadCloud, Server, HardDrive, Wand2, Link2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'

// --- 本地偏好 key ---
const THEME_KEY = 'zongzi_theme'
const DEFAULT_SEARCH_SOURCE_KEY = 'zongzi_default_search_source'
const DEFAULT_TYPE_KEY = 'zongzi_default_type'

type Theme = 'light' | 'dark' | 'system'
type SearchSource = 'piratebay' | 'anime' | 'assrt'
type DefaultType = 'movie' | 'tv'

// --- 系统配置（可编辑并保存到服务端 config 文件，按字段编辑）---
const originalConfig = ref<Record<string, any>>({})
const loadingConfig = ref(false)
const savingConfig = ref(false)

const securityUsername = ref('')
const securityPassword = ref('')
const securitySecretKey = ref('')
const securityAlgorithm = ref('')
const securityAccessTokenExpireMinutes = ref<number | null>(null)

const tmdbApiKey = ref('')
const tmdbLanguage = ref('')

const qbHost = ref('')
const qbUsername = ref('')
const qbPassword = ref('')
const qbUseCopy = ref(false)
const qbCopyDeleteOnComplete = ref(false)
const qbSeedingLimitRatio = ref<number | null>(null)
const qbSeedingDeleteOnRatioReached = ref(false)
const qbSeedingDeleteFiles = ref(false)

const piratebayUrl = ref('')
const piratebayParams = ref('')

const animeGardenUrl = ref('')
const animeGardenPageSize = ref<number | null>(null)

const assrtToken = ref('')
const assrtBaseUrl = ref('')

const dbPath = ref('')

const pathsDownloadRootPath = ref('')
const pathsTargetRootPath = ref('')
const pathsRootPath = ref('')

const pathsDefaultDownloadPath = ref('')
const pathsMovieDownloadPath = ref('')
const pathsTvDownloadPath = ref('')
const pathsAnimeDownloadPath = ref('')
const pathsTempDownloadPath = ref('')

const pathsDefaultTargetPath = ref('')
const pathsMovieTargetPath = ref('')
const pathsTvTargetPath = ref('')
const pathsAnimeTargetPath = ref('')

const smartRenameMovie = ref('')
const smartRenameTv = ref('')
const smartRenameAnime = ref('')

const trackersText = ref('')

const applyConfigToForm = (cfg: Record<string, any>) => {
  const security = cfg.security || {}
  securityUsername.value = security.username ?? ''
  securityPassword.value = security.password ?? ''
  securitySecretKey.value = security.secret_key ?? ''
  securityAlgorithm.value = security.algorithm ?? ''
  securityAccessTokenExpireMinutes.value = security.access_token_expire_minutes ?? null

  const tmdb = cfg.tmdb || {}
  tmdbApiKey.value = tmdb.api_key ?? ''
  tmdbLanguage.value = tmdb.language ?? ''

  const qb = cfg.qbittorrent || {}
  qbHost.value = qb.host ?? ''
  qbUsername.value = qb.username ?? ''
  qbPassword.value = qb.password ?? ''
  const fileHandling = qb.file_handling || {}
  qbUseCopy.value = fileHandling.use_copy ?? false
  qbCopyDeleteOnComplete.value = fileHandling.copy_delete_on_complete ?? false
  const seeding = qb.seeding || {}
  qbSeedingLimitRatio.value = seeding.limit_ratio ?? null
  qbSeedingDeleteOnRatioReached.value = seeding.delete_on_ratio_reached ?? false
  qbSeedingDeleteFiles.value = seeding.delete_files ?? false

  const piratebay = cfg.piratebay || {}
  piratebayUrl.value = piratebay.url ?? ''
  piratebayParams.value = piratebay.params ?? ''

  const animeGarden = cfg.anime_garden || {}
  animeGardenUrl.value = animeGarden.url ?? ''
  animeGardenPageSize.value = animeGarden.page_size ?? null

  const subtitle = cfg.subtitle || {}
  const assrt = subtitle.assrt || {}
  assrtToken.value = assrt.token ?? ''
  assrtBaseUrl.value = assrt.base_url ?? ''

  const database = cfg.database || {}
  dbPath.value = database.path ?? ''

  const pathsCfg = cfg.paths || {}
  pathsDownloadRootPath.value = pathsCfg.download_root_path ?? ''
  pathsTargetRootPath.value = pathsCfg.target_root_path ?? ''
  pathsRootPath.value = pathsCfg.root_path ?? ''
  pathsDefaultDownloadPath.value = pathsCfg.default_download_path ?? ''
  pathsMovieDownloadPath.value = pathsCfg.movie_download_path ?? ''
  pathsTvDownloadPath.value = pathsCfg.tv_download_path ?? ''
  pathsAnimeDownloadPath.value = pathsCfg.anime_download_path ?? ''
  pathsTempDownloadPath.value = pathsCfg.temp_download_path ?? ''
  pathsDefaultTargetPath.value = pathsCfg.default_target_path ?? ''
  pathsMovieTargetPath.value = pathsCfg.movie_target_path ?? ''
  pathsTvTargetPath.value = pathsCfg.tv_target_path ?? ''
  pathsAnimeTargetPath.value = pathsCfg.anime_target_path ?? ''

  const smartRename = cfg.smart_rename || {}
  smartRenameMovie.value = smartRename.movie ?? ''
  smartRenameTv.value = smartRename.tv ?? ''
  smartRenameAnime.value = smartRename.anime ?? ''

  const trackers = cfg.trackers
  trackersText.value = Array.isArray(trackers) ? trackers.join('\n') : ''
}

const loadConfig = async () => {
  loadingConfig.value = true
  try {
    const res = await getConfigApiV1SystemConfigGet()
    const data = (res as any)?.data || {}
    originalConfig.value = data && typeof data === 'object' ? data : {}
    applyConfigToForm(originalConfig.value)
  } catch {
    toast.error('加载配置失败')
    originalConfig.value = {}
  } finally {
    loadingConfig.value = false
  }
}

const saveConfig = async () => {
  const cfg: Record<string, any> = structuredClone(originalConfig.value || {}) as any

  cfg.security = cfg.security || {}
  cfg.security.username = securityUsername.value
  cfg.security.password = securityPassword.value
  cfg.security.secret_key = securitySecretKey.value
  cfg.security.algorithm = securityAlgorithm.value
  if (securityAccessTokenExpireMinutes.value != null) {
    cfg.security.access_token_expire_minutes = securityAccessTokenExpireMinutes.value
  }

  cfg.tmdb = cfg.tmdb || {}
  cfg.tmdb.api_key = tmdbApiKey.value
  cfg.tmdb.language = tmdbLanguage.value

  cfg.qbittorrent = cfg.qbittorrent || {}
  cfg.qbittorrent.host = qbHost.value
  cfg.qbittorrent.username = qbUsername.value
  cfg.qbittorrent.password = qbPassword.value
  cfg.qbittorrent.file_handling = cfg.qbittorrent.file_handling || {}
  cfg.qbittorrent.file_handling.use_copy = qbUseCopy.value
  cfg.qbittorrent.file_handling.copy_delete_on_complete = qbCopyDeleteOnComplete.value
  cfg.qbittorrent.seeding = cfg.qbittorrent.seeding || {}
  if (qbSeedingLimitRatio.value != null) {
    cfg.qbittorrent.seeding.limit_ratio = qbSeedingLimitRatio.value
  }
  cfg.qbittorrent.seeding.delete_on_ratio_reached = qbSeedingDeleteOnRatioReached.value
  cfg.qbittorrent.seeding.delete_files = qbSeedingDeleteFiles.value

  cfg.piratebay = cfg.piratebay || {}
  cfg.piratebay.url = piratebayUrl.value
  cfg.piratebay.params = piratebayParams.value

  cfg.anime_garden = cfg.anime_garden || {}
  cfg.anime_garden.url = animeGardenUrl.value
  if (animeGardenPageSize.value != null) {
    cfg.anime_garden.page_size = animeGardenPageSize.value
  }

  cfg.subtitle = cfg.subtitle || {}
  cfg.subtitle.assrt = cfg.subtitle.assrt || {}
  cfg.subtitle.assrt.token = assrtToken.value
  cfg.subtitle.assrt.base_url = assrtBaseUrl.value

  cfg.database = cfg.database || {}
  cfg.database.path = dbPath.value

  cfg.paths = cfg.paths || {}
  cfg.paths.download_root_path = pathsDownloadRootPath.value
  cfg.paths.target_root_path = pathsTargetRootPath.value
  cfg.paths.root_path = pathsRootPath.value
  cfg.paths.default_download_path = pathsDefaultDownloadPath.value
  cfg.paths.movie_download_path = pathsMovieDownloadPath.value
  cfg.paths.tv_download_path = pathsTvDownloadPath.value
  cfg.paths.anime_download_path = pathsAnimeDownloadPath.value
  cfg.paths.temp_download_path = pathsTempDownloadPath.value
  cfg.paths.default_target_path = pathsDefaultTargetPath.value
  cfg.paths.movie_target_path = pathsMovieTargetPath.value
  cfg.paths.tv_target_path = pathsTvTargetPath.value
  cfg.paths.anime_target_path = pathsAnimeTargetPath.value

  cfg.smart_rename = cfg.smart_rename || {}
  cfg.smart_rename.movie = smartRenameMovie.value
  cfg.smart_rename.tv = smartRenameTv.value
  cfg.smart_rename.anime = smartRenameAnime.value

  const lines = (trackersText.value || '').split('\n').map((t) => t.trim()).filter(Boolean)
  cfg.trackers = lines

  savingConfig.value = true
  try {
    await saveConfigApiV1SystemConfigPut(cfg)
    originalConfig.value = cfg
    toast.success('配置已保存')
  } catch (e: any) {
    toast.error(e?.message || '保存失败')
  } finally {
    savingConfig.value = false
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
  if (s && (s === 'piratebay' || s === 'anime' || s === 'assrt')) defaultSearchSource.value = s
  const d = localStorage.getItem(DEFAULT_TYPE_KEY) as DefaultType | null
  if (d && (d === 'movie' || d === 'tv')) defaultType.value = d

  loadConfig()
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
  <div class="max-w-3xl mx-auto space-y-10 py-6 sm:py-10">
    <h1 class="text-2xl font-semibold tracking-tight">设置</h1>

    <!-- 偏好 -->
    <section class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="flex items-center gap-2 text-muted-foreground">
        <Palette class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">偏好</h2>
      </div>
      <div class="space-y-5 pl-8">
        <div class="space-y-3">
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
        <div class="space-y-3">
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
            <Button
              :variant="defaultSearchSource === 'assrt' ? 'default' : 'outline'"
              size="sm"
              @click="setDefaultSearchSource('assrt')"
            >
              ASSRT字幕站
            </Button>
          </div>
        </div>
        <div class="space-y-3">
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

    <!-- 系统配置（可编辑并保存到服务端 config 文件） -->
    <section class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="flex items-center gap-2 text-muted-foreground">
        <FileJson class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">系统配置</h2>
      </div>
      <p class="text-sm text-muted-foreground pl-8">
        这里按字段编辑服务端 config，修改后点击保存将写回配置文件并立即生效。
      </p>
      <div class="space-y-8 pl-8">
        <div class="flex gap-2">
          <Button size="sm" variant="outline" :disabled="loadingConfig" @click="loadConfig">
            {{ loadingConfig ? '加载中…' : '重新加载' }}
          </Button>
        </div>

        <!-- 登录与安全 -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Shield class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">登录与安全</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            用于系统登录认证和 JWT Token 生成，部署前务必修改默认账号与 JWT 密钥。
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1">
              <Label>用户名</Label>
              <input
                v-model="securityUsername"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>密码</Label>
              <input
                v-model="securityPassword"
                type="password"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>JWT 密钥</Label>
              <input
                v-model="securitySecretKey"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>算法</Label>
              <input
                v-model="securityAlgorithm"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>Token 过期时间（分钟）</Label>
              <input
                v-model.number="securityAccessTokenExpireMinutes"
                type="number"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </div>

        <!-- TMDB -->
        <div class="space-y-3 border-t border-border/60 pt-5">
          <div class="flex items-center gap-2">
            <Clapperboard class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">TMDB</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            用于获取电影 / 电视剧的元数据（海报、简介等），需要先在 TMDB 官网申请 API Key。
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1 sm:col-span-2">
              <Label>API Key</Label>
              <input
                v-model="tmdbApiKey"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>语言</Label>
              <input
                v-model="tmdbLanguage"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </div>

        <!-- qBittorrent -->
        <div class="space-y-3 border-t border-border/60 pt-5">
          <div class="flex items-center gap-2">
            <DownloadCloud class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">qBittorrent</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            用于管理种子下载任务，请确保已开启 qBittorrent WebUI，并与下面的下载 / 归档路径保持一致。
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1 sm:col-span-2">
              <Label>WebUI 地址</Label>
              <input
                v-model="qbHost"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>用户名</Label>
              <input
                v-model="qbUsername"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>密码</Label>
              <input
                v-model="qbPassword"
                type="password"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>单文件使用复制（use_copy）</Label>
              <div class="flex items-center gap-2">
                <Checkbox v-model="qbUseCopy" />
                <span class="text-xs text-muted-foreground">单文件由程序复制到目标路径，多文件仍由 qB 移动整文件夹。</span>
              </div>
            </div>
            <div class="space-y-1">
              <Label>复制完成后删除源任务（copy_delete_on_complete）</Label>
              <div class="flex items-center gap-2">
                <Checkbox v-model="qbCopyDeleteOnComplete" />
                <span class="text-xs text-muted-foreground">仅在使用复制模式时生效，复制成功后自动删除 qB 任务与源文件。</span>
              </div>
            </div>
            <div class="space-y-1">
              <Label>做种分享率限制（limit_ratio）</Label>
              <input
                v-model.number="qbSeedingLimitRatio"
                type="number"
                step="0.1"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>达到分享率后删除任务（delete_on_ratio_reached）</Label>
              <div class="flex items-center gap-2">
                <Checkbox v-model="qbSeedingDeleteOnRatioReached" />
                <span class="text-xs text-muted-foreground">达到上面的分享率阈值后，自动删除对应任务。</span>
              </div>
            </div>
            <div class="space-y-1">
              <Label>删除任务时同时删除文件（delete_files）</Label>
              <div class="flex items-center gap-2">
                <Checkbox v-model="qbSeedingDeleteFiles" />
                <span class="text-xs text-muted-foreground">开启后删除任务会连同本地临时文件一起清理，请谨慎开启。</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 其他服务 -->
        <div class="space-y-3 border-t border-border/60 pt-5">
          <div class="flex items-center gap-2">
            <Server class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">其他服务</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            海盗湾 / 动漫花园 / ASSRT 字幕等外部服务的接口地址与参数设置，通常保持默认即可使用。
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1 sm:col-span-2">
              <Label>PirateBay URL</Label>
              <input
                v-model="piratebayUrl"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>PirateBay 查询参数</Label>
              <input
                v-model="piratebayParams"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>Anime Garden URL</Label>
              <input
                v-model="animeGardenUrl"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>Anime Garden 每页数量</Label>
              <input
                v-model.number="animeGardenPageSize"
                type="number"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>ASSRT Token</Label>
              <input
                v-model="assrtToken"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>ASSRT Base URL</Label>
              <input
                v-model="assrtBaseUrl"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </div>

        <!-- 路径与数据库 -->
        <div class="space-y-3 border-t border-border/60 pt-5">
          <div class="flex items-center gap-2">
            <HardDrive class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">路径与数据库</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            下载 / 归档根路径及各分类的具体目录；注意与实际挂载路径、NAS 路径保持一致，避免文件找不到。
          </p>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1 sm:col-span-2">
              <Label>数据库路径</Label>
              <input
                v-model="dbPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>下载根路径（download_root_path）</Label>
              <input
                v-model="pathsDownloadRootPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>归档根路径（target_root_path）</Label>
              <input
                v-model="pathsTargetRootPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>回退根路径（root_path）</Label>
              <input
                v-model="pathsRootPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>默认下载路径</Label>
              <input
                v-model="pathsDefaultDownloadPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>电影下载路径</Label>
              <input
                v-model="pathsMovieDownloadPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>剧集下载路径</Label>
              <input
                v-model="pathsTvDownloadPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>番剧下载路径</Label>
              <input
                v-model="pathsAnimeDownloadPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>临时下载路径</Label>
              <input
                v-model="pathsTempDownloadPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>默认归档路径</Label>
              <input
                v-model="pathsDefaultTargetPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>电影归档路径</Label>
              <input
                v-model="pathsMovieTargetPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>剧集归档路径</Label>
              <input
                v-model="pathsTvTargetPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>番剧归档路径</Label>
              <input
                v-model="pathsAnimeTargetPath"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </div>

        <!-- 智能重命名模板 -->
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <Wand2 class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">智能重命名模板</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            用于磁力解析页的重命名规则，支持占位符 {name}、{year}、{season}、{ss}、{episode}、{ee}、{extra}、{sub_suffix}、{ext}。
          </p>
          <div class="space-y-4">
            <div class="space-y-1">
              <Label>电影模板</Label>
              <input
                v-model="smartRenameMovie"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>剧集模板</Label>
              <input
                v-model="smartRenameTv"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>番剧模板</Label>
              <input
                v-model="smartRenameAnime"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        </div>

        <!-- BT Trackers -->
        <div class="space-y-3 border-t border-border/60 pt-5">
          <div class="flex items-center gap-2">
            <Link2 class="h-4 w-4 text-muted-foreground" />
            <h3 class="text-sm font-medium text-foreground">BT Trackers</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            一行一个 Tracker URL，保存后将覆盖 config.yml 中的 trackers 列表。添加更多高质量 Tracker 可提升连接速度。
          </p>
          <textarea
            v-model="trackersText"
            class="w-full min-h-[160px] rounded-md border border-input bg-background px-3 py-2 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
            spellcheck="false"
            placeholder="udp://tracker.opentrackr.org:1337/announce"
          />
        </div>

        <!-- 保存按钮（放在最下方） -->
        <div class="pt-4">
          <Button size="sm" :disabled="savingConfig || loadingConfig" @click="saveConfig">
            {{ savingConfig ? '保存中…' : '保存配置' }}
          </Button>
        </div>
      </div>
    </section>

    <!-- 关于 -->
    <section class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="flex items-center gap-2 text-muted-foreground">
        <Info class="h-5 w-5" />
        <h2 class="text-lg font-medium text-foreground">关于</h2>
      </div>
      <div class="pl-8 space-y-2 text-sm text-muted-foreground">
        <p>粽子湾资源助手 — 聚合磁链搜索、qBittorrent 推送与智能重命名。</p>
      </div>
    </section>
  </div>
</template>
