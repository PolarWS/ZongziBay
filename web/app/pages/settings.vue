<script setup lang="ts">
import { assrtQuota } from '@/api/assrt'
import { animeGardenTeams } from '@/api/animeGarden'
import { checkConnectionApiV1MagnetCheckGet } from '@/api/magnet'
import { searchTorrentsApiV1PiratebaySearchGet } from '@/api/pirateBay'
import { getConfigApiV1SystemConfigGet, saveConfigApiV1SystemConfigPut, applyDefaultTmdbKeyApiV1SystemConfigApplyDefaultTmdbKeyPost, applyDefaultAssrtKeyApiV1SystemConfigApplyDefaultAssrtKeyPost } from '@/api/system'
import { getTrendingMoviesApiV1TmdbTrendingMovieGet } from '@/api/tmdb'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import Checkbox from '@/components/ui/checkbox/Checkbox.vue'
import { Palette, Info, FileJson, Shield, Clapperboard, DownloadCloud, Server, HardDrive, Wand2, Link2, CheckCircle, XCircle, Loader, RefreshCw, ArrowUpCircle } from 'lucide-vue-next'
import pkg from '../../package.json'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
const testing = reactive({
  tmdb: false,
  piratebay: false,
  animeGarden: false,
  assrt: false,
  qb: false,
  all: false,
})

// 测试结果：null=未测试, true=通过(✓), false=失败(✗)
const testResults = reactive<Record<string, null | boolean>>({
  tmdb: null,
  piratebay: null,
  animeGarden: null,
  assrt: null,
  qb: null,
})

// 默认密钥应用状态
const applyingDefaults = reactive({
  tmdb: false,
  assrt: false,
})
const showDefaultKeyDialog = ref(false)
const defaultKeyTarget = ref<'tmdb' | 'assrt'>('tmdb')
const MASKED = '****'

// --- 版本更新检测 ---
const currentVersion = pkg.version
const checkingUpdate = ref(false)
const latestVersion = ref<string | null>(null)
const updateChecked = ref(false)

const hasUpdate = computed(() => {
  if (!latestVersion.value) return false
  return latestVersion.value !== currentVersion
})

const checkUpdate = async () => {
  checkingUpdate.value = true
  updateChecked.value = false
  try {
    const res = await fetch('https://raw.githubusercontent.com/PolarWS/ZongziBay/main/VERSION', {
      cache: 'no-cache',
    })
    if (!res.ok) throw new Error('获取版本信息失败')
    const text = await res.text()
    latestVersion.value = text.trim()
    updateChecked.value = true
  } catch (e: any) {
    toast.error(e?.message || '检查更新失败')
  } finally {
    checkingUpdate.value = false
  }
}

const confirmApplyDefaultKeys = async () => {
  const target = defaultKeyTarget.value
  if (target === 'tmdb') applyingDefaults.tmdb = true
  else applyingDefaults.assrt = true
  showDefaultKeyDialog.value = false
  try {
    if (target === 'tmdb') {
      await applyDefaultTmdbKeyApiV1SystemConfigApplyDefaultTmdbKeyPost()
      toast.success('TMDB 默认密钥已应用')
    } else {
      await applyDefaultAssrtKeyApiV1SystemConfigApplyDefaultAssrtKeyPost()
      toast.success('ASSRT 默认密钥已应用')
    }
    await loadConfig()
  } catch (e: any) {
    toast.error(e?.message || '应用默认密钥失败')
  } finally {
    if (target === 'tmdb') applyingDefaults.tmdb = false
    else applyingDefaults.assrt = false
  }
}

const applyDefaultTmdbKey = () => {
  defaultKeyTarget.value = 'tmdb'
  showDefaultKeyDialog.value = true
}

const applyDefaultAssrtKey = () => {
  defaultKeyTarget.value = 'assrt'
  showDefaultKeyDialog.value = true
}

const securityUsername = ref('')
const securityPassword = ref('')
const securitySecretKey = ref('')
const securityAlgorithm = ref('')
const securityAccessTokenExpireMinutes = ref<number | null>(null)

function generateSecuritySecretKey() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let key = ''
  for (let i = 0; i < 32; i++) {
    key += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  securitySecretKey.value = key
  toast.success('JWT 密钥已随机生成')
}

const tmdbApiKey = ref('')
const tmdbLanguage = ref('')
const tmdbApiDomain = ref('')
const tmdbImageDomain = ref('')

const qbHost = ref('')
const qbUsername = ref('')
const qbPassword = ref('')
const qbApiKey = ref('')
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
  tmdbApiDomain.value = tmdb.api_domain ?? ''
  tmdbImageDomain.value = tmdb.image_domain ?? ''

  const qb = cfg.qbittorrent || {}
  qbHost.value = qb.host ?? ''
  qbUsername.value = qb.username ?? ''
  qbPassword.value = qb.password ?? ''
  qbApiKey.value = qb.api_key ?? ''
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
  const cfg: Record<string, any> = JSON.parse(JSON.stringify(originalConfig.value || {})) as any

  cfg.security = cfg.security || {}
  cfg.security.username = securityUsername.value
  cfg.security.password = securityPassword.value
  cfg.security.secret_key = securitySecretKey.value
  cfg.security.algorithm = securityAlgorithm.value
  if (securityAccessTokenExpireMinutes.value != null) {
    cfg.security.access_token_expire_minutes = securityAccessTokenExpireMinutes.value
  }

  // JWT 密钥不允许为空或太短
  const finalSecretKey = cfg.security.secret_key !== '****' ? cfg.security.secret_key : (originalConfig.value?.security?.secret_key || '')
  if (!finalSecretKey || finalSecretKey === 'CHANGE_THIS_SECRET_KEY') {
    toast.error('JWT 密钥不能为空或使用默认值，请设置一个安全密钥')
    return
  }
  if (finalSecretKey !== '****' && finalSecretKey.length < 16) {
    toast.error('JWT 密钥长度至少 16 个字符，请重新生成')
    return
  }
  if (cfg.security.secret_key === '****') {
    // 用户未修改，保留原值，不传入空串
    delete cfg.security.secret_key
  }

  cfg.tmdb = cfg.tmdb || {}
  cfg.tmdb.api_key = tmdbApiKey.value
  cfg.tmdb.language = tmdbLanguage.value
  cfg.tmdb.api_domain = tmdbApiDomain.value
  cfg.tmdb.image_domain = tmdbImageDomain.value

  cfg.qbittorrent = cfg.qbittorrent || {}
  cfg.qbittorrent.host = qbHost.value
  cfg.qbittorrent.username = qbUsername.value
  cfg.qbittorrent.password = qbPassword.value
  cfg.qbittorrent.api_key = qbApiKey.value
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

  delete cfg.database

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

const testTmdb = async () => {
  testing.tmdb = true
  testResults.tmdb = null
  try {
    const res = await getTrendingMoviesApiV1TmdbTrendingMovieGet({ page: 1, window: 'week' })
    const data = (res as any)?.data
    const items = data?.results || data?.items || data?.data?.results || []
    toast.success(`TMDB 连接正常${Array.isArray(items) ? `（返回 ${items.length} 条）` : ''}`)
    testResults.tmdb = true
  } catch (e: any) {
    toast.error(e?.message || 'TMDB 连接失败')
    testResults.tmdb = false
  } finally {
    testing.tmdb = false
  }
}

const testPirateBay = async () => {
  testing.piratebay = true
  testResults.piratebay = null
  try {
    const res = await searchTorrentsApiV1PiratebaySearchGet({ q: 'test' })
    const data = (res as any)?.data
    const list = data?.data ?? data ?? []
    toast.success(`海盗湾连接正常${Array.isArray(list) ? `（返回 ${list.length} 条）` : ''}`)
    testResults.piratebay = true
  } catch (e: any) {
    toast.error(e?.message || '海盗湾连接失败')
    testResults.piratebay = false
  } finally {
    testing.piratebay = false
  }
}

const testAnimeGarden = async () => {
  testing.animeGarden = true
  testResults.animeGarden = null
  try {
    const res = await animeGardenTeams()
    const data = (res as any)?.data
    const list = data?.data ?? data ?? []
    toast.success(`动漫花园连接正常${Array.isArray(list) ? `（返回 ${list.length} 条字幕组）` : ''}`)
    testResults.animeGarden = true
  } catch (e: any) {
    toast.error(e?.message || '动漫花园连接失败')
    testResults.animeGarden = false
  } finally {
    testing.animeGarden = false
  }
}

const testAssrt = async () => {
  testing.assrt = true
  testResults.assrt = null
  try {
    const res = await assrtQuota()
    const data = (res as any)?.data
    const quota = data?.data?.quota ?? data?.quota
    toast.success(`ASSRT 连接正常${quota != null ? `（配额 ${quota}）` : ''}`)
    testResults.assrt = true
  } catch (e: any) {
    toast.error(e?.message || 'ASSRT 连接失败')
    testResults.assrt = false
  } finally {
    testing.assrt = false
  }
}

const testQb = async () => {
  testing.qb = true
  testResults.qb = null
  try {
    const res = await checkConnectionApiV1MagnetCheckGet()
    const data = (res as any)?.data
    const ok = data?.data ?? data
    if (ok) {
      toast.success('qBittorrent 连接正常')
      testResults.qb = true
    } else {
      toast.error('qBittorrent 连接失败（请检查 host/账号密码/网络）')
      testResults.qb = false
    }
  } catch (e: any) {
    toast.error(e?.message || 'qBittorrent 连接失败')
    testResults.qb = false
  } finally {
    testing.qb = false
  }
}

const testAllConnections = async () => {
  if (testing.all) return
  testing.all = true
  try {
    await testTmdb()
    await testPirateBay()
    await testAnimeGarden()
    await testAssrt()
    await testQb()
  } finally {
    testing.all = false
  }
}

const onKeydownSaveConfig = (e: KeyboardEvent) => {
  // 尽力拦截 Ctrl+S / Cmd+S 保存配置（部分浏览器/系统可能仍会抢占）
  const key = (e.key || '').toLowerCase()
  if ((e.ctrlKey || e.metaKey) && key === 's') {
    e.preventDefault()
    if (savingConfig.value || loadingConfig.value) return
    saveConfig()
  }
}

// --- 偏好（localStorage）---
const theme = ref<Theme>('system')
const defaultSearchSource = ref<SearchSource>('piratebay')
const defaultType = ref<DefaultType>('tv')
const { showZongzibayChan, init: initChan, setShowChan } = useZongzibayChan()

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


onMounted(async () => {
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

  initChan()
  loadConfig()

  // 快捷键：Ctrl+S / Cmd+S 保存配置
  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', onKeydownSaveConfig, { capture: true })
  }
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
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', onKeydownSaveConfig, { capture: true } as any)
  }
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
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <div>
              <Label class="text-sm">显示粽子娘</Label>
              <p class="text-xs text-muted-foreground mt-0.5">关闭后登录页、引导页及主页面右下角的粽子娘角色图片将被隐藏</p>
            </div>
            <button
              type="button"
              class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200"
              :class="showZongzibayChan ? 'bg-primary' : 'bg-muted-foreground/30'"
              @click="setShowChan(!showZongzibayChan)"
            >
              <span
                class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg transform transition-transform duration-200"
                :class="showZongzibayChan ? 'translate-x-5' : 'translate-x-0'"
              />
            </button>
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
      <div class="space-y-8 pl-8">
        <p class="text-xs text-muted-foreground">
          说明：以上按钮仅用于测试连通性/鉴权是否正常，不会保存配置，也不会创建下载任务或写入数据。
        </p>
        <div class="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            class="min-w-24"
            :disabled="testing.all || loadingConfig"
            @click="testAllConnections"
          >
            <Loader v-if="testing.all" class="mr-1 h-3 w-3 animate-spin" />
            {{ testing.all ? '测试中…' : '测试全部' }}
          </Button>
          <Button size="sm" variant="secondary" :disabled="testing.tmdb" @click="testTmdb">
            <Loader v-if="testing.tmdb" class="mr-1 h-3 w-3 animate-spin" />
            TMDB
            <CheckCircle v-if="testResults.tmdb === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
            <XCircle v-if="testResults.tmdb === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
          </Button>
          <Button size="sm" variant="secondary" :disabled="testing.piratebay" @click="testPirateBay">
            <Loader v-if="testing.piratebay" class="mr-1 h-3 w-3 animate-spin" />
            海盗湾
            <CheckCircle v-if="testResults.piratebay === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
            <XCircle v-if="testResults.piratebay === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
          </Button>
          <Button size="sm" variant="secondary" :disabled="testing.animeGarden" @click="testAnimeGarden">
            <Loader v-if="testing.animeGarden" class="mr-1 h-3 w-3 animate-spin" />
            动漫花园
            <CheckCircle v-if="testResults.animeGarden === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
            <XCircle v-if="testResults.animeGarden === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
          </Button>
          <Button size="sm" variant="secondary" :disabled="testing.assrt" @click="testAssrt">
            <Loader v-if="testing.assrt" class="mr-1 h-3 w-3 animate-spin" />
            ASSRT
            <CheckCircle v-if="testResults.assrt === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
            <XCircle v-if="testResults.assrt === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
          </Button>
          <Button size="sm" variant="secondary" :disabled="testing.qb" @click="testQb">
            <Loader v-if="testing.qb" class="mr-1 h-3 w-3 animate-spin" />
            qBittorrent
            <CheckCircle v-if="testResults.qb === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
            <XCircle v-if="testResults.qb === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
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
              <div class="flex gap-2">
                <input
                  v-model="securitySecretKey"
                  class="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <Button size="sm" variant="outline" class="shrink-0" @click="generateSecuritySecretKey">
                  <RefreshCw class="w-3.5 h-3.5 mr-1" />随机生成
                </Button>
              </div>
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
              <div class="flex gap-2">
                <input
                  v-model="tmdbApiKey"
                  class="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <Button
                  size="sm"
                  variant="outline"
                  class="shrink-0"
                  :disabled="applyingDefaults.tmdb || applyingDefaults.assrt"
                  @click="applyDefaultTmdbKey"
                >
                  {{ applyingDefaults.tmdb ? '应用中…' : '使用项目默认密钥' }}
                </Button>
              </div>
              <p v-if="tmdbApiKey === MASKED" class="text-xs text-emerald-500">
                已使用项目提供的默认密钥，你也可以替换为自己的 API Key
              </p>
            </div>
            <div class="space-y-1">
              <Label>语言</Label>
              <input
                v-model="tmdbLanguage"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>API 域名</Label>
              <input
                v-model="tmdbApiDomain"
                placeholder="api.themoviedb.org"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>图片域名</Label>
              <input
                v-model="tmdbImageDomain"
                placeholder="image.tmdb.org"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p class="text-xs text-muted-foreground">
                若图片加载缓慢可更换为中转代理地址
              </p>
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
              <Label>API Key（5.2.0+ 可选，填写后无需用户名密码）</Label>
              <input
                v-model="qbApiKey"
                type="password"
                placeholder="qbt_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
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
              <div class="flex gap-2">
                <input
                  v-model="assrtToken"
                  class="flex-1 rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <Button
                  size="sm"
                  variant="outline"
                  class="shrink-0"
                  :disabled="applyingDefaults.assrt || applyingDefaults.tmdb"
                  @click="applyDefaultAssrtKey"
                >
                  {{ applyingDefaults.assrt ? '应用中…' : '使用项目默认密钥' }}
                </Button>
              </div>
              <p v-if="assrtToken === MASKED" class="text-xs text-emerald-500">
                已使用项目提供的默认令牌，你也可以替换为自己的 Token
              </p>
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>ASSRT Base URL</Label>
              <input
                v-model="assrtBaseUrl"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p class="text-xs text-muted-foreground">
                若默认地址访问失败可更换为
                <code class="rounded bg-muted px-1 py-0.5 text-[11px]">https://api.makedie.me</code>
              </p>
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
            下载 / 归档根路径及各分类的具体目录，注意与实际挂载路径、NAS 路径保持一致，避免文件找不到。
            根路径是用于qBittorrent挂在目前前面补全，比如你qBittorrent挂载了/video但是本项目挂载了D:/docker/video那么就填D:/docker，如果一致就不用填留空
          </p>
          <p class="text-xs text-muted-foreground">
            数据库固定为当前
            <code class="rounded bg-muted px-1 py-0.5 text-[11px]">config.yml</code>
            同目录下的
            <code class="rounded bg-muted px-1 py-0.5 text-[11px]">ZongziBay.db</code>
            （如 Docker 下
            <code class="rounded bg-muted px-1 py-0.5 text-[11px]">config/ZongziBay.db</code>
            ），不在此配置。
          </p>
          <div class="grid gap-3 sm:grid-cols-2">
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
        <div class="pt-4 flex justify-center gap-2">
          <Button size="sm" variant="outline" class="min-w-24" :disabled="loadingConfig" @click="loadConfig">
            {{ loadingConfig ? '加载中…' : '重新加载' }}
          </Button>
          <Button size="sm" class="min-w-24 border border-transparent" :disabled="savingConfig || loadingConfig" @click="saveConfig">
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
      <div class="pl-8 space-y-3 text-sm text-muted-foreground">
        <p>粽子湾资源助手 — 聚合磁链搜索、qBittorrent 推送与智能重命名。</p>
        <div class="flex items-center gap-3 flex-wrap">
          <span>
            当前版本：
            <code class="rounded bg-muted px-1.5 py-0.5 text-xs">{{ currentVersion }}</code>
          </span>
          <Button size="sm" variant="outline" :disabled="checkingUpdate" @click="checkUpdate">
            <Loader v-if="checkingUpdate" class="mr-1 h-3 w-3 animate-spin" />
            <RefreshCw v-else class="mr-1 h-3 w-3" />
            {{ checkingUpdate ? '检测中…' : '检查更新' }}
          </Button>
        </div>
        <div v-if="updateChecked && latestVersion" class="flex items-center gap-2">
          <template v-if="hasUpdate">
            <ArrowUpCircle class="h-4 w-4 shrink-0 text-orange-500" />
            <span class="text-orange-500">
              发现新版本 <code class="rounded bg-muted px-1 py-0.5 text-xs">{{ latestVersion }}</code>，请前往
              <a href="https://github.com/PolarWS/ZongziBay/releases" target="_blank" class="text-primary underline">GitHub Releases</a>
              下载更新。
            </span>
          </template>
          <template v-else>
            <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
            <span class="text-green-500">已是最新版本</span>
          </template>
        </div>
      </div>
    </section>
  </div>

  <!-- 默认密钥确认对话框 -->
  <Dialog v-model:open="showDefaultKeyDialog">
    <DialogContent class="max-w-md w-[calc(100vw-1rem)] sm:w-full">
      <DialogHeader>
        <DialogTitle>使用项目默认密钥</DialogTitle>
        <DialogDescription class="space-y-3 text-left">
          <p>
            项目提供的
            <strong class="text-foreground">{{ defaultKeyTarget === 'tmdb' ? 'TMDB' : 'ASSRT' }}</strong>
            密钥为公共密钥，<strong class="text-foreground">请求速率有严格限制</strong>，多人共用时可能触发限流导致
            {{ defaultKeyTarget === 'tmdb' ? '元数据获取' : '字幕搜索' }}失败。
          </p>
          <p>
            建议前往对应官网<strong class="text-foreground">免费申请自己的密钥</strong>以获得更稳定的体验：
          </p>
          <ul class="list-disc list-inside space-y-1 text-xs">
            <li>TMDB：<a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noopener noreferrer" class="text-primary underline">themoviedb.org/settings/api</a></li>
            <li>ASSRT：<a href="https://assrt.net/user" target="_blank" rel="noopener noreferrer" class="text-primary underline">assrt.net/user</a>（注册后在用户面板查看 Token）</li>
          </ul>
          <p class="text-xs">
            详细图文教程请参阅：<a href="https://github.com/PolarWS/ZongziBay/blob/main/docs/api_keys_guide.md" target="_blank" rel="noopener noreferrer" class="text-primary underline">API Key 获取指南</a>
          </p>
          <p class="pt-1">是否确认使用项目默认的 <strong class="text-foreground">{{ defaultKeyTarget === 'tmdb' ? 'TMDB' : 'ASSRT' }}</strong> 密钥？你也可以稍后自行填写自己的密钥。</p>
        </DialogDescription>
      </DialogHeader>
      <div class="flex justify-end gap-3 mt-4">
        <Button variant="outline" :disabled="applyingDefaults.tmdb || applyingDefaults.assrt" @click="showDefaultKeyDialog = false">
          我再想想
        </Button>
        <Button :disabled="applyingDefaults.tmdb || applyingDefaults.assrt" @click="confirmApplyDefaultKeys">
          {{ (defaultKeyTarget === 'tmdb' ? applyingDefaults.tmdb : applyingDefaults.assrt) ? '应用中…' : '确认使用' }}
        </Button>
      </div>
    </DialogContent>
  </Dialog>
</template>
