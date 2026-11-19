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
import { Palette, Info, Shield, Clapperboard, DownloadCloud, Server, HardDrive, Wand2, Link2, CheckCircle, XCircle, Loader, RefreshCw, ArrowUpCircle, Key, Copy, Eye, EyeOff, ChevronDown, Ban, Play, Trash2 } from 'lucide-vue-next'
import { getApiTokens, createApiToken, toggleApiToken, deleteApiToken } from '@/api/apiTokens'
import { onClickOutside } from '@vueuse/core'
import pkg from '../../package.json'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'vue-sonner'
import { sha256 } from '@/utils/crypto'
import { applyTemplate, DEFAULT_RENAME_TEMPLATES } from '@/utils/renamer'

// --- 本地偏好 key ---
const THEME_KEY = 'zongzi_theme'
const DEFAULT_SEARCH_SOURCE_KEY = 'zongzi_default_search_source'
const DEFAULT_TYPE_KEY = 'zongzi_default_type'

type Theme = 'light' | 'dark' | 'system'
type SearchSource = 'piratebay' | 'anime' | 'assrt'
type DefaultType = 'movie' | 'tv'
type SettingsTab =
  | 'prefs'
  | 'security'
  | 'tmdb'
  | 'qb'
  | 'services'
  | 'paths'
  | 'rename'
  | 'trackers'
  | 'apitokens'
  | 'about'

const SETTINGS_TABS: { id: SettingsTab; label: string; icon: typeof Palette }[] = [
  { id: 'prefs', label: '偏好', icon: Palette },
  { id: 'security', label: '安全', icon: Shield },
  { id: 'tmdb', label: 'TMDB', icon: Clapperboard },
  { id: 'qb', label: '下载器', icon: DownloadCloud },
  { id: 'services', label: '服务', icon: Server },
  { id: 'paths', label: '路径', icon: HardDrive },
  { id: 'rename', label: '重命名', icon: Wand2 },
  { id: 'trackers', label: 'Tracker', icon: Link2 },
  { id: 'apitokens', label: 'MCP', icon: Key },
  { id: 'about', label: '关于', icon: Info },
]

const CONFIG_TABS = new Set<SettingsTab>([
  'security',
  'tmdb',
  'qb',
  'services',
  'paths',
  'rename',
  'trackers',
])

const activeTab = ref<SettingsTab>('prefs')
const isConfigTab = computed(() => CONFIG_TABS.has(activeTab.value))

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
const PLACEHOLDER_CONFIGURED = '已配置，留空则保持不变'

/** 脱敏字段展示：**** 显示为空，方便直接输入新值 */
function displaySecret(val: unknown): string {
  const s = typeof val === 'string' ? val : ''
  return !s || s === MASKED ? '' : s
}

/** 保存时：输入为空且原先已配置 → 回传 **** 让后端保留原值 */
function saveSecret(val: string, wasConfigured: boolean): string {
  const trimmed = (val || '').trim()
  if (!trimmed && wasConfigured) return MASKED
  return trimmed
}

const securityPasswordConfigured = ref(false)
const tmdbApiKeyConfigured = ref(false)
const qbPasswordConfigured = ref(false)
const qbApiKeyConfigured = ref(false)
const assrtTokenConfigured = ref(false)

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

// 下载器后端选择：qbittorrent / transmission / aria2
type DownloaderType = 'qbittorrent' | 'transmission' | 'aria2'
const downloaderType = ref<DownloaderType>('qbittorrent')
const tmHost = ref('')
const tmUsername = ref('')
const tmPassword = ref('')
const tmPasswordConfigured = ref(false)
const aria2Host = ref('')
const aria2Secret = ref('')
const aria2SecretConfigured = ref(false)

const piratebayUrl = ref('')
const piratebayParams = ref('')

const animeGardenUrl = ref('')
const animeGardenPageSize = ref<number | null>(null)

const bangumiApiUrl = ref('')

const assrtToken = ref('')
const assrtBaseUrl = ref('')
const isDefaultTmdbKey = ref(false)
const isDefaultAssrtToken = ref(false)

// 当用户手动修改密钥时，自动清除"默认密钥"标记
watch(tmdbApiKey, (val) => {
  if (val.trim()) isDefaultTmdbKey.value = false
})
watch(assrtToken, (val) => {
  if (val.trim()) isDefaultAssrtToken.value = false
})

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

/** 设置页重命名预览用的示例变量（可改，方便试模板效果） */
const renamePreviewName = ref('末日三问')
const renamePreviewYear = ref('2026')
const renamePreviewSeason = ref('1')
const renamePreviewEpisode = ref('1')
const renamePreviewExtra = ref(' - PV')
const renamePreviewSubSuffix = ref(' - CHT')
const renamePreviewExt = ref('.mkv')

const renamePreviewVars = computed(() => {
  const season = renamePreviewSeason.value.trim() || '1'
  const episode = renamePreviewEpisode.value.trim() || '1'
  const ss = season.padStart(2, '0')
  const ee = episode.padStart(2, '0')
  return {
    name: renamePreviewName.value.trim() || '示例名称',
    year: renamePreviewYear.value.trim() || '2024',
    season,
    ss,
    episode,
    ee,
    extra: renamePreviewExtra.value,
    sub_suffix: renamePreviewSubSuffix.value,
    ext: renamePreviewExt.value || '.mkv',
  }
})

const renamePreviewMovie = computed(() =>
  applyTemplate(smartRenameMovie.value.trim() || DEFAULT_RENAME_TEMPLATES.movie, renamePreviewVars.value),
)
const renamePreviewTv = computed(() =>
  applyTemplate(smartRenameTv.value.trim() || DEFAULT_RENAME_TEMPLATES.tv, renamePreviewVars.value),
)
const renamePreviewAnime = computed(() =>
  applyTemplate(smartRenameAnime.value.trim() || DEFAULT_RENAME_TEMPLATES.anime, renamePreviewVars.value),
)

const trackersText = ref('')

const applyConfigToForm = (cfg: Record<string, any>) => {
  const security = cfg.security || {}
  securityUsername.value = security.username ?? ''
  securityPasswordConfigured.value = !!(security.password && security.password !== '')
  securityPassword.value = displaySecret(security.password)
  // secret_key 后端不脱敏，直接展示；若碰巧为 **** 则留空
  securitySecretKey.value = displaySecret(security.secret_key)
  securityAlgorithm.value = security.algorithm ?? ''
  securityAccessTokenExpireMinutes.value = security.access_token_expire_minutes ?? null

  const tmdb = cfg.tmdb || {}
  tmdbApiKeyConfigured.value = !!(tmdb.api_key && tmdb.api_key !== '')
  tmdbApiKey.value = displaySecret(tmdb.api_key)
  tmdbLanguage.value = tmdb.language ?? ''
  tmdbApiDomain.value = tmdb.api_domain ?? ''
  tmdbImageDomain.value = tmdb.image_domain ?? ''
  isDefaultTmdbKey.value = !!tmdb._is_default_key

  // downloader 节：后端类型 + Transmission/Aria2 连接信息
  const dl = cfg.downloader || {}
  const dlActive = dl.active || 'qbittorrent'
  if (dlActive === 'transmission' || dlActive === 'aria2') downloaderType.value = dlActive
  else downloaderType.value = 'qbittorrent'
  const tmDl = dl.transmission || {}
  tmHost.value = tmDl.host ?? ''
  tmUsername.value = tmDl.username ?? ''
  tmPasswordConfigured.value = !!(tmDl.password && tmDl.password !== '')
  tmPassword.value = displaySecret(tmDl.password)
  const ariaDl = dl.aria2 || {}
  aria2Host.value = ariaDl.host ?? ''
  aria2SecretConfigured.value = !!(ariaDl.secret && ariaDl.secret !== '')
  aria2Secret.value = displaySecret(ariaDl.secret)

  const qb = cfg.qbittorrent || {}
  qbHost.value = qb.host ?? ''
  qbUsername.value = qb.username ?? ''
  qbPasswordConfigured.value = !!(qb.password && qb.password !== '')
  qbPassword.value = displaySecret(qb.password)
  qbApiKeyConfigured.value = !!(qb.api_key && qb.api_key !== '')
  qbApiKey.value = displaySecret(qb.api_key)
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

  const bangumi = cfg.bangumi || {}
  bangumiApiUrl.value = bangumi.api_url ?? ''

  const subtitle = cfg.subtitle || {}
  const assrt = subtitle.assrt || {}
  assrtTokenConfigured.value = !!(assrt.token && assrt.token !== '')
  assrtToken.value = displaySecret(assrt.token)
  assrtBaseUrl.value = assrt.base_url ?? ''
  isDefaultAssrtToken.value = !!assrt._is_default_token

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
  smartRenameMovie.value = smartRename.movie || DEFAULT_RENAME_TEMPLATES.movie
  smartRenameTv.value = smartRename.tv || DEFAULT_RENAME_TEMPLATES.tv
  smartRenameAnime.value = smartRename.anime || DEFAULT_RENAME_TEMPLATES.anime

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
  const passwordToSave = saveSecret(securityPassword.value, securityPasswordConfigured.value)
  cfg.security.password = passwordToSave !== MASKED ? await sha256(passwordToSave) : passwordToSave
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
  cfg.tmdb.api_key = saveSecret(tmdbApiKey.value, tmdbApiKeyConfigured.value)
  cfg.tmdb.language = tmdbLanguage.value
  cfg.tmdb.api_domain = tmdbApiDomain.value
  cfg.tmdb.image_domain = tmdbImageDomain.value

  // downloader 节：后端类型 + Transmission/Aria2 连接信息
  cfg.downloader = cfg.downloader || {}
  cfg.downloader.active = downloaderType.value
  cfg.downloader.transmission = cfg.downloader.transmission || {}
  cfg.downloader.transmission.host = tmHost.value
  cfg.downloader.transmission.username = tmUsername.value
  cfg.downloader.transmission.password = saveSecret(tmPassword.value, tmPasswordConfigured.value)
  cfg.downloader.aria2 = cfg.downloader.aria2 || {}
  cfg.downloader.aria2.host = aria2Host.value
  cfg.downloader.aria2.secret = saveSecret(aria2Secret.value, aria2SecretConfigured.value)

  cfg.qbittorrent = cfg.qbittorrent || {}
  cfg.qbittorrent.host = qbHost.value
  cfg.qbittorrent.username = qbUsername.value
  cfg.qbittorrent.password = saveSecret(qbPassword.value, qbPasswordConfigured.value)
  cfg.qbittorrent.api_key = saveSecret(qbApiKey.value, qbApiKeyConfigured.value)
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

  cfg.bangumi = cfg.bangumi || {}
  cfg.bangumi.api_url = bangumiApiUrl.value

  cfg.subtitle = cfg.subtitle || {}
  cfg.subtitle.assrt = cfg.subtitle.assrt || {}
  cfg.subtitle.assrt.token = saveSecret(assrtToken.value, assrtTokenConfigured.value)
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

const DOWNLOADER_LABEL: Record<string, string> = {
  qbittorrent: 'qBittorrent',
  transmission: 'Transmission',
  aria2: 'Aria2',
}

const testQb = async () => {
  testing.qb = true
  testResults.qb = null
  const label = DOWNLOADER_LABEL[downloaderType.value] || '下载器'
  try {
    const res = await checkConnectionApiV1MagnetCheckGet()
    const data = (res as any)?.data
    const ok = data?.data ?? data
    if (ok) {
      toast.success(`${label} 连接正常`)
      testResults.qb = true
    } else {
      toast.error(`${label} 连接失败（请检查 host/账号密码/网络）`)
      testResults.qb = false
    }
  } catch (e: any) {
    toast.error(e?.message || `${label} 连接失败`)
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


// --- API Token 管理 ---
interface ApiTokenItem {
  id: number
  name: string
  scopes: string
  is_active: boolean
  last_used_at: string | null
  created_at: string
  expires_at: string | null
}

const apiTokens = ref<ApiTokenItem[]>([])
const apiTokensTotal = ref(0)
const apiTokensLoading = ref(false)

const newTokenName = ref('')
const newTokenScopes = ref('read')
const newTokenExpiryDays = ref<number | null>(null)
const creating = ref(false)

const isScopeMenuOpen = ref(false)
const scopeMenuRef = ref<HTMLElement | null>(null)
onClickOutside(scopeMenuRef, () => {
  isScopeMenuOpen.value = false
})

const scopeOptions = [
  { value: 'read', label: '只读', desc: '只读 — 查看下载列表、搜索媒体信息' },
  { value: 'search', label: '搜索', desc: '搜索 — 只读 + 搜索种子和字幕' },
  { value: 'download', label: '完整', desc: '完整 — 搜索 + 添加/取消下载任务' },
] as const

const scopeLabels: Record<string, string> = Object.fromEntries(
  scopeOptions.map((o) => [o.value, o.desc]),
)

const selectedScopeLabel = computed(
  () => scopeOptions.find((o) => o.value === newTokenScopes.value)?.label ?? newTokenScopes.value,
)

function selectScope(value: string) {
  newTokenScopes.value = value
  isScopeMenuOpen.value = false
}

// 新创建的 token（完整 token 仅展示一次）
const createdToken = ref<{ id: number; name: string; token: string; scopes: string; expires_at: string | null; masked: string } | null>(null)
const showFullToken = ref(false)
const createdTokenDialogOpen = ref(false)

function closeCreatedTokenDialog() {
  createdTokenDialogOpen.value = false
  createdToken.value = null
  showFullToken.value = false
}

function onCreatedTokenDialogOpenChange(open: boolean) {
  if (!open) closeCreatedTokenDialog()
  else createdTokenDialogOpen.value = true
}

const deleteTokenDialogOpen = ref(false)
const tokenToDelete = ref<{ id: number; name: string } | null>(null)
const deletingToken = ref(false)

async function loadApiTokens() {
  apiTokensLoading.value = true
  try {
    const res = await getApiTokens({ page: 1, page_size: 100 })
    const data = (res as any)?.data
    apiTokens.value = data?.items ?? []
    apiTokensTotal.value = data?.total ?? 0
  } catch {
    // 静默失败
  } finally {
    apiTokensLoading.value = false
  }
}

async function handleCreateToken() {
  if (!newTokenName.value.trim()) return
  creating.value = true
  try {
    const res = await createApiToken({
      name: newTokenName.value.trim(),
      scopes: newTokenScopes.value,
      expires_in_days: newTokenExpiryDays.value ?? null,
    })
    const data = (res as any)?.data
    if (data) {
      createdToken.value = data
      showFullToken.value = true
      createdTokenDialogOpen.value = true
    }
    newTokenName.value = ''
    newTokenScopes.value = 'read'
    newTokenExpiryDays.value = null
    await loadApiTokens()
  } catch (e: any) {
    toast.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleToggleToken(tokenId: number, isActive: boolean) {
  try {
    await toggleApiToken(tokenId, isActive)
    await loadApiTokens()
    toast.success(isActive ? '已启用' : '已禁用')
  } catch (e: any) {
    toast.error(e?.message || '操作失败')
  }
}

function openDeleteTokenDialog(tokenId: number, name: string) {
  tokenToDelete.value = { id: tokenId, name }
  deleteTokenDialogOpen.value = true
}

async function confirmDeleteToken() {
  if (!tokenToDelete.value) return
  deletingToken.value = true
  try {
    await deleteApiToken(tokenToDelete.value.id)
    await loadApiTokens()
    toast.success('令牌已删除')
    deleteTokenDialogOpen.value = false
    tokenToDelete.value = null
  } catch (e: any) {
    toast.error(e?.message || '删除失败')
  } finally {
    deletingToken.value = false
  }
}

function copyTokenToClipboard(token: string) {
  navigator.clipboard.writeText(token).then(() => {
    toast.success('令牌已复制到剪贴板')
  }).catch(() => {
    toast.error('复制失败，请手动复制')
  })
}

function copyMcpConfig(token: string) {
  const host = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000'
  const config = JSON.stringify({
    mcpServers: {
      zongzibay: {
        url: `${host}/mcp/sse`,
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    },
  }, null, 2)
  navigator.clipboard.writeText(config).then(() => {
    toast.success('MCP 配置已复制到剪贴板')
  }).catch(() => {
    toast.error('复制失败')
  })
}

const mcpSseUrl = computed(() => {
  const host = typeof window !== 'undefined' ? window.location.origin : ''
  return `${host}/mcp/sse`
})

const isApiTokenTab = computed(() => activeTab.value === 'apitokens')

watch(activeTab, (tab) => {
  if (tab === 'apitokens') loadApiTokens()
})

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
  <div class="space-y-6">
    <h1 class="text-2xl font-semibold tracking-tight">设置</h1>

    <div class="flex flex-col gap-6 lg:flex-row lg:items-start">
      <!-- 分类导航：宽屏为左侧竖向侧栏，窄屏为顶部换行药丸 -->
      <nav class="lg:sticky lg:top-20 lg:w-52 lg:shrink-0">
        <div class="flex flex-wrap gap-1.5 rounded-xl border border-border bg-card p-1.5 shadow-sm lg:flex-col">
          <button
            v-for="tab in SETTINGS_TABS"
            :key="tab.id"
            type="button"
            class="flex flex-1 min-w-[calc(33.333%-0.5rem)] cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-2 text-sm font-medium transition-colors sm:min-w-0 lg:w-full lg:flex-none lg:justify-start"
            :class="activeTab === tab.id
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'"
            @click="activeTab = tab.id"
          >
            <component :is="tab.icon" class="h-4 w-4 shrink-0" />
            {{ tab.label }}
          </button>
        </div>
      </nav>

      <!-- 内容区 -->
      <div class="min-w-0 flex-1 space-y-6">

    <!-- 偏好 -->
    <section v-show="activeTab === 'prefs'" class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="space-y-5">
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
    <!-- 用 div 而非 form：多组密码/密钥字段放进同一 form 会触发 Chrome 密码表单启发式警告 -->
    <div v-if="isConfigTab">
    <section class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="space-y-6">
        <div v-show="activeTab === 'tmdb' || activeTab === 'qb' || activeTab === 'services'" class="space-y-3">
          <p class="text-xs text-muted-foreground">
            说明：以下按钮仅用于测试连通性/鉴权是否正常，不会保存配置，也不会创建下载任务或写入数据。
          </p>
          <div class="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              class="min-w-24"
              type="button"
              :disabled="testing.all || loadingConfig"
              @click="testAllConnections"
            >
              <Loader v-if="testing.all" class="mr-1 h-3 w-3 animate-spin" />
              {{ testing.all ? '测试中…' : '测试全部' }}
            </Button>
            <Button size="sm" variant="secondary" type="button" :disabled="testing.tmdb" @click="testTmdb">
              <Loader v-if="testing.tmdb" class="mr-1 h-3 w-3 animate-spin" />
              TMDB
              <CheckCircle v-if="testResults.tmdb === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
              <XCircle v-if="testResults.tmdb === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
            </Button>
            <Button size="sm" variant="secondary" type="button" :disabled="testing.piratebay" @click="testPirateBay">
              <Loader v-if="testing.piratebay" class="mr-1 h-3 w-3 animate-spin" />
              海盗湾
              <CheckCircle v-if="testResults.piratebay === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
              <XCircle v-if="testResults.piratebay === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
            </Button>
            <Button size="sm" variant="secondary" type="button" :disabled="testing.animeGarden" @click="testAnimeGarden">
              <Loader v-if="testing.animeGarden" class="mr-1 h-3 w-3 animate-spin" />
              动漫花园
              <CheckCircle v-if="testResults.animeGarden === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
              <XCircle v-if="testResults.animeGarden === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
            </Button>
            <Button size="sm" variant="secondary" type="button" :disabled="testing.assrt" @click="testAssrt">
              <Loader v-if="testing.assrt" class="mr-1 h-3 w-3 animate-spin" />
              ASSRT
              <CheckCircle v-if="testResults.assrt === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
              <XCircle v-if="testResults.assrt === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
            </Button>
            <Button size="sm" variant="secondary" type="button" :disabled="testing.qb" @click="testQb">
              <Loader v-if="testing.qb" class="mr-1 h-3 w-3 animate-spin" />
              qBittorrent
              <CheckCircle v-if="testResults.qb === true" class="ml-1 h-3.5 w-3.5 text-green-500" />
              <XCircle v-if="testResults.qb === false" class="ml-1 h-3.5 w-3.5 text-red-500" />
            </Button>
          </div>
        </div>

        <!-- 登录与安全 -->
        <div v-show="activeTab === 'security'" class="space-y-3">
          <p class="text-xs text-muted-foreground">
            用于系统登录认证和 JWT Token 生成，部署前务必修改默认账号与 JWT 密钥。
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1">
              <Label>用户名</Label>
              <input
                v-model="securityUsername"
                autocomplete="username"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>密码</Label>
              <input
                v-model="securityPassword"
                type="password"
                autocomplete="new-password"
                :placeholder="securityPasswordConfigured ? PLACEHOLDER_CONFIGURED : '请输入登录密码'"
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
        <div v-show="activeTab === 'tmdb'" class="space-y-3">
          <p class="text-xs text-muted-foreground">
            用于获取电影 / 电视剧的元数据（海报、简介等），需要先在 TMDB 官网申请 API Key。
          </p>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="space-y-1 sm:col-span-2">
              <Label>API Key</Label>
              <div class="flex gap-2">
                <input
                  v-model="tmdbApiKey"
                  :placeholder="tmdbApiKeyConfigured ? PLACEHOLDER_CONFIGURED : '请输入 TMDB API Key'"
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
              <p v-if="isDefaultTmdbKey" class="text-xs text-emerald-500">
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

        <!-- 下载器后端 -->
        <div v-show="activeTab === 'qb'" class="space-y-3">
          <div class="space-y-3">
            <div>
              <Label>下载器类型</Label>
              <div class="flex flex-wrap gap-2 mt-2">
                <Button
                  :variant="downloaderType === 'qbittorrent' ? 'default' : 'outline'"
                  size="sm"
                  @click="downloaderType = 'qbittorrent'"
                >
                  qBittorrent
                </Button>
                <Button
                  :variant="downloaderType === 'transmission' ? 'default' : 'outline'"
                  size="sm"
                  @click="downloaderType = 'transmission'"
                >
                  Transmission
                </Button>
                <Button
                  :variant="downloaderType === 'aria2' ? 'default' : 'outline'"
                  size="sm"
                  @click="downloaderType = 'aria2'"
                >
                  Aria2
                </Button>
              </div>
              <p class="text-xs text-muted-foreground mt-2">
                选择后保存配置即可切换后端。切换后请确保下方连接信息与实际的下载器保持一致。
              </p>
            </div>
          </div>

          <!-- qBittorrent -->
          <div v-if="downloaderType === 'qbittorrent'" class="space-y-3">
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
                autocomplete="off"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>密码</Label>
              <input
                v-model="qbPassword"
                type="password"
                autocomplete="off"
                :placeholder="qbPasswordConfigured ? PLACEHOLDER_CONFIGURED : '请输入 WebUI 密码'"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label>API Key（5.2.0+ 可选，填写后无需用户名密码）</Label>
              <input
                v-model="qbApiKey"
                type="password"
                autocomplete="off"
                :placeholder="qbApiKeyConfigured ? PLACEHOLDER_CONFIGURED : 'qbt_xxxxxxxxxxxxxxxxxxxxxxxxxxxx'"
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

          <!-- Transmission -->
          <div v-else-if="downloaderType === 'transmission'" class="space-y-3">
            <p class="text-xs text-muted-foreground">
              Transmission 通过 RPC 接口管理下载任务，请确保已开启 Transmission Web（默认 9091 端口）并配置 RPC 认证。
            </p>
            <div class="grid gap-4 sm:grid-cols-2">
              <div class="space-y-1 sm:col-span-2">
                <Label>RPC 地址</Label>
                <input
                  v-model="tmHost"
                  placeholder="http://localhost:9091"
                  class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1">
                <Label>用户名</Label>
                <input
                  v-model="tmUsername"
                  autocomplete="off"
                  class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1">
                <Label>密码</Label>
                <input
                  v-model="tmPassword"
                  type="password"
                  autocomplete="off"
                  :placeholder="tmPasswordConfigured ? PLACEHOLDER_CONFIGURED : '请输入 RPC 密码'"
                  class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
          </div>

          <!-- Aria2 -->
          <div v-else-if="downloaderType === 'aria2'" class="space-y-3">
            <p class="text-xs text-muted-foreground">
              Aria2 通过 JSON-RPC 接口管理下载任务。注意：Aria2 不支持种子内重命名与移动归档，将降级为复制模式。
            </p>
            <div class="grid gap-4 sm:grid-cols-2">
              <div class="space-y-1 sm:col-span-2">
                <Label>RPC 地址</Label>
                <input
                  v-model="aria2Host"
                  placeholder="http://localhost:6800"
                  class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1 sm:col-span-2">
                <Label>RPC Secret</Label>
                <input
                  v-model="aria2Secret"
                  type="password"
                  autocomplete="off"
                  :placeholder="aria2SecretConfigured ? PLACEHOLDER_CONFIGURED : 'rpc-secret'"
                  class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 其他服务 -->
        <div v-show="activeTab === 'services'" class="space-y-3">
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
              <Label>Bangumi API URL</Label>
              <input
                v-model="bangumiApiUrl"
                placeholder="https://api.bgm.tv"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <p class="text-xs text-muted-foreground">
                番剧「本周新番」周历数据来源（bgm.tv），公开接口无需 Token，通常保持默认即可。
              </p>
            </div>
            <div class="space-y-1 sm:col-span-2">
              <Label>ASSRT Token</Label>
              <div class="flex gap-2">
                <input
                  v-model="assrtToken"
                  :placeholder="assrtTokenConfigured ? PLACEHOLDER_CONFIGURED : '请输入 ASSRT Token'"
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
              <p v-if="isDefaultAssrtToken" class="text-xs text-emerald-500">
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
        <div v-show="activeTab === 'paths'" class="space-y-3">
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
        <div v-show="activeTab === 'rename'" class="space-y-4">
          <p class="text-xs text-muted-foreground">
            用于磁力解析页的重命名规则。修改模板后可在下方用示例数据实时预览结果，确认无误再保存。
          </p>
          <div class="rounded-md bg-muted/60 p-3 text-xs text-muted-foreground">
            <div class="font-medium text-foreground mb-1.5">占位符说明</div>
            <ul class="space-y-1 list-none">
              <li><code class="bg-muted px-1 rounded">{name}</code> 资源名（TMDB / 自定义标题，如：末日三问）</li>
              <li><code class="bg-muted px-1 rounded">{year}</code> 年份（电影常用，如：2026）</li>
              <li><code class="bg-muted px-1 rounded">{season}</code> 季数（如：1）</li>
              <li><code class="bg-muted px-1 rounded">{ss}</code> 季数补零两位（如：01）</li>
              <li><code class="bg-muted px-1 rounded">{episode}</code> 集数（如：3）</li>
              <li><code class="bg-muted px-1 rounded">{ee}</code> 集数补零两位（如：03）</li>
              <li><code class="bg-muted px-1 rounded">{extra}</code> 额外标记，从原文件名识别 PV/Menu 等；没有则为空</li>
              <li><code class="bg-muted px-1 rounded">{sub_suffix}</code> 字幕语言后缀（如： - CHT）；非字幕文件为空</li>
              <li><code class="bg-muted px-1 rounded">{ext}</code> 扩展名（含点号，如：.mkv、.srt）</li>
            </ul>
          </div>
          <div class="space-y-4">
            <div class="space-y-1">
              <Label>电影模板</Label>
              <input
                v-model="smartRenameMovie"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                :placeholder="DEFAULT_RENAME_TEMPLATES.movie"
              />
              <p class="text-[11px] font-mono text-muted-foreground break-all">预览：{{ renamePreviewMovie }}</p>
            </div>
            <div class="space-y-1">
              <Label>剧集模板</Label>
              <input
                v-model="smartRenameTv"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                :placeholder="DEFAULT_RENAME_TEMPLATES.tv"
              />
              <p class="text-[11px] font-mono text-muted-foreground break-all">预览：{{ renamePreviewTv }}</p>
            </div>
            <div class="space-y-1">
              <Label>番剧模板</Label>
              <input
                v-model="smartRenameAnime"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                :placeholder="DEFAULT_RENAME_TEMPLATES.anime"
              />
              <p class="text-[11px] font-mono text-muted-foreground break-all">预览：{{ renamePreviewAnime }}</p>
            </div>
          </div>
          <div class="border-t border-border pt-4 space-y-3">
            <div>
              <div class="font-medium text-sm text-foreground">测试数据</div>
              <p class="text-xs text-muted-foreground mt-0.5">
                改这里不会写入配置，只用来模拟重命名结果，方便调模板。
              </p>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div class="space-y-1">
                <Label class="text-xs">{name} 资源名</Label>
                <input
                  v-model="renamePreviewName"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">{year} 年份</Label>
                <input
                  v-model="renamePreviewYear"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">{season} 季数 → {ss}</Label>
                <input
                  v-model="renamePreviewSeason"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">{episode} 集数 → {ee}</Label>
                <input
                  v-model="renamePreviewEpisode"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">{extra} 额外标记</Label>
                <input
                  v-model="renamePreviewExtra"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder=" - PV"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">{sub_suffix} 字幕后缀</Label>
                <input
                  v-model="renamePreviewSubSuffix"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder=" - CHT"
                />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">{ext} 扩展名</Label>
                <input
                  v-model="renamePreviewExt"
                  class="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-xs font-mono text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder=".mkv"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- BT Trackers -->
        <div v-show="activeTab === 'trackers'" class="space-y-3">
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
    </div>

    <!-- MCP 令牌管理 -->
    <section v-show="activeTab === 'apitokens'" class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="space-y-5">
        <div>
          <p class="text-xs text-muted-foreground">
            MCP 令牌用于外部 AI 服务（如 Claude、Cursor 等）通过 MCP 协议访问 ZongziBay。
            令牌仅在创建时展示一次，请妥善保管。连接地址：<code class="rounded bg-muted px-1 py-0.5 text-[11px]">{{ mcpSseUrl }}</code>
          </p>
        </div>

        <!-- 创建令牌表单 -->
        <div class="rounded-md border border-border p-4 space-y-3">
          <div class="font-medium text-sm">创建新 MCP 令牌</div>
          <div class="grid gap-3 sm:grid-cols-3">
            <div class="space-y-1">
              <Label class="text-xs">名称</Label>
              <input
                v-model="newTokenName"
                placeholder="例如：MCP"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div class="space-y-1">
              <Label class="text-xs">权限</Label>
              <div class="relative" ref="scopeMenuRef">
                <button
                  type="button"
                  class="flex h-[34px] w-full items-center justify-between rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  @click="isScopeMenuOpen = !isScopeMenuOpen"
                >
                  <span>{{ selectedScopeLabel }}</span>
                  <ChevronDown class="h-3.5 w-3.5 opacity-50" />
                </button>
                <div
                  v-if="isScopeMenuOpen"
                  class="absolute left-0 top-full mt-1 z-50 w-full min-w-[14rem] rounded-md border border-border bg-popover text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95"
                >
                  <div class="p-1">
                    <button
                      v-for="opt in scopeOptions"
                      :key="opt.value"
                      type="button"
                      class="relative flex w-full cursor-pointer select-none flex-col items-start rounded-sm px-2 py-1.5 text-left outline-none hover:bg-accent hover:text-accent-foreground"
                      :class="{ 'bg-accent text-accent-foreground': newTokenScopes === opt.value }"
                      @click="selectScope(opt.value)"
                    >
                      <span class="text-sm font-medium">{{ opt.label }}</span>
                      <span class="text-[11px] text-muted-foreground">{{ opt.desc }}</span>
                    </button>
                  </div>
                </div>
              </div>
              <p class="text-[11px] text-muted-foreground">{{ scopeLabels[newTokenScopes] }}</p>
            </div>
            <div class="space-y-1">
              <Label class="text-xs">过期天数（可选）</Label>
              <input
                v-model.number="newTokenExpiryDays"
                type="number"
                min="1"
                max="3650"
                placeholder="留空则永不过期"
                class="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          <Button size="sm" :disabled="creating || !newTokenName.trim()" @click="handleCreateToken">
            <Key v-if="!creating" class="mr-1 h-3.5 w-3.5" />
            <Loader v-if="creating" class="mr-1 h-3.5 w-3.5 animate-spin" />
            {{ creating ? '创建中…' : '创建 MCP 令牌' }}
          </Button>
        </div>

        <!-- 令牌列表 -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <div class="font-medium text-sm">MCP 令牌列表（{{ apiTokensTotal }}）</div>
            <Button size="sm" variant="ghost" class="h-7 text-xs" :disabled="apiTokensLoading" @click="loadApiTokens">
              <RefreshCw :class="['mr-1 h-3 w-3', apiTokensLoading ? 'animate-spin' : '']" />
              刷新
            </Button>
          </div>
          <div v-if="apiTokensLoading && !apiTokens.length" class="text-center py-8 text-sm text-muted-foreground">
            <Loader class="mx-auto h-5 w-5 animate-spin mb-2" />加载中…
          </div>
          <div v-else-if="!apiTokens.length" class="text-center py-8 text-sm text-muted-foreground">
            暂无令牌，请在上方创建第一个 MCP 令牌
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-border text-left text-xs text-muted-foreground">
                  <th class="py-2 pr-3 font-medium">名称</th>
                  <th class="py-2 pr-3 font-medium">权限</th>
                  <th class="py-2 pr-3 font-medium">状态</th>
                  <th class="py-2 pr-3 font-medium hidden sm:table-cell">创建时间</th>
                  <th class="py-2 pr-3 font-medium hidden sm:table-cell">最后使用</th>
                  <th class="py-2 pr-3 font-medium">过期</th>
                  <th class="py-2 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in apiTokens" :key="t.id" class="border-b border-border/50" :class="{ 'opacity-50': !t.is_active }">
                  <td class="py-2.5 pr-3 font-medium">{{ t.name }}</td>
                  <td class="py-2.5 pr-3">
                    <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                      :class="{
                        'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400': t.scopes === 'read',
                        'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400': t.scopes === 'search',
                        'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400': t.scopes === 'download',
                      }"
                    >{{ { read: '只读', search: '搜索', download: '完整' }[t.scopes] || t.scopes }}</span>
                  </td>
                  <td class="py-2.5 pr-3">
                    <span class="inline-flex items-center gap-1">
                      <span class="h-2 w-2 rounded-full" :class="t.is_active ? 'bg-green-500' : 'bg-gray-400'" />
                      {{ t.is_active ? '启用' : '禁用' }}
                    </span>
                  </td>
                  <td class="py-2.5 pr-3 text-xs text-muted-foreground hidden sm:table-cell">{{ t.created_at }}</td>
                  <td class="py-2.5 pr-3 text-xs text-muted-foreground hidden sm:table-cell">{{ t.last_used_at || '从未使用' }}</td>
                  <td class="py-2.5 pr-3 text-xs">
                    <span v-if="t.expires_at" :class="new Date(t.expires_at) < new Date() ? 'text-red-500' : 'text-muted-foreground'">
                      {{ t.expires_at }}
                    </span>
                    <span v-else class="text-muted-foreground">永不过期</span>
                  </td>
                  <td class="py-2.5 text-right">
                    <div class="flex items-center justify-end gap-0.5">
                      <Button
                        size="sm"
                        variant="ghost"
                        class="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-muted"
                        :title="t.is_active ? '禁用' : '启用'"
                        @click="handleToggleToken(t.id, !t.is_active)"
                      >
                        <Ban v-if="t.is_active" class="h-3.5 w-3.5" />
                        <Play v-else class="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        class="h-8 w-8 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        title="删除"
                        @click="openDeleteTokenDialog(t.id, t.name)"
                      >
                        <Trash2 class="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- 关于 -->
    <section v-show="activeTab === 'about'" class="rounded-xl border border-border bg-card p-5 sm:p-7 space-y-5">
      <div class="space-y-3 text-sm text-muted-foreground">
        <p class="flex items-center gap-2.5 text-foreground">
          <img
            src="~/assets/img/zongzibay_logo.svg"
            alt="ZongziBay"
            class="h-7 w-7 shrink-0 object-contain"
          />
          <span>
            <span class="font-medium">粽子湾资源助手</span>
            <span class="text-muted-foreground"> — 聚合磁链搜索、qBittorrent 推送与智能重命名。</span>
          </span>
        </p>
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
    </div>
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

  <!-- 删除 MCP 令牌确认 -->
  <Dialog v-model:open="deleteTokenDialogOpen">
    <DialogContent class="max-w-sm overflow-x-hidden w-[calc(100vw-1rem)] sm:w-full">
      <DialogHeader>
        <DialogTitle>删除 MCP 令牌</DialogTitle>
        <DialogDescription>
          确定要删除令牌「{{ tokenToDelete?.name }}」吗？使用该令牌的服务将立即失效，此操作无法撤销。
        </DialogDescription>
      </DialogHeader>
      <div class="flex justify-end gap-3 mt-4">
        <Button variant="outline" :disabled="deletingToken" @click="deleteTokenDialogOpen = false">取消</Button>
        <Button variant="destructive" :disabled="deletingToken" @click="confirmDeleteToken">
          <Loader v-if="deletingToken" class="mr-1 h-3.5 w-3.5 animate-spin" />
          {{ deletingToken ? '删除中…' : '确认删除' }}
        </Button>
      </div>
    </DialogContent>
  </Dialog>

  <!-- MCP 令牌创建成功（仅展示一次） -->
  <Dialog
    :open="createdTokenDialogOpen"
    @update:open="onCreatedTokenDialogOpenChange"
  >
    <DialogContent class="max-w-md w-[calc(100vw-1rem)] sm:w-full gap-5">
      <DialogHeader class="space-y-3 text-left sm:text-left">
        <div class="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-500/10">
          <CheckCircle class="h-5 w-5 text-emerald-500" />
        </div>
        <div class="space-y-1.5">
          <DialogTitle>MCP 令牌已创建</DialogTitle>
          <DialogDescription>
            此令牌只会显示一次，关闭后无法再次查看，请先复制保存。
          </DialogDescription>
        </div>
      </DialogHeader>

      <div v-if="createdToken" class="space-y-4">
        <div class="flex flex-wrap gap-2 text-xs">
          <span class="rounded-md border border-border bg-muted/50 px-2.5 py-1 text-foreground">
            {{ createdToken.name }}
          </span>
          <span class="rounded-md border border-border bg-muted/50 px-2.5 py-1 text-muted-foreground">
            {{ { read: '只读', search: '搜索', download: '完整' }[createdToken.scopes] || createdToken.scopes }}
          </span>
          <span class="rounded-md border border-border bg-muted/50 px-2.5 py-1 text-muted-foreground">
            {{ createdToken.expires_at ? `过期 ${createdToken.expires_at}` : '永不过期' }}
          </span>
        </div>

        <div class="space-y-2">
          <div class="text-xs font-medium text-muted-foreground">令牌</div>
          <div class="rounded-lg border border-border bg-muted/40 p-3">
            <code class="block break-all font-mono text-xs leading-relaxed select-all text-foreground">
              {{ showFullToken ? createdToken.token : createdToken.masked }}
            </code>
          </div>
          <div class="flex gap-2">
            <Button size="sm" variant="outline" class="flex-1" @click="showFullToken = !showFullToken">
              <Eye v-if="!showFullToken" class="h-3.5 w-3.5" />
              <EyeOff v-else class="h-3.5 w-3.5" />
              {{ showFullToken ? '隐藏' : '显示' }}
            </Button>
            <Button size="sm" class="flex-1" @click="copyTokenToClipboard(createdToken.token)">
              <Copy class="h-3.5 w-3.5" />
              复制令牌
            </Button>
          </div>
        </div>

        <div class="rounded-lg border border-dashed border-border bg-muted/20 px-3 py-2.5">
          <p class="text-[11px] leading-relaxed text-muted-foreground mb-2">
            也可一键复制 Cursor / Claude 可用的 MCP 配置。
          </p>
          <Button size="sm" variant="secondary" class="w-full" @click="copyMcpConfig(createdToken.token)">
            <Copy class="h-3.5 w-3.5" />
            复制 MCP 配置
          </Button>
        </div>
      </div>

      <div class="flex justify-end border-t border-border pt-4">
        <Button class="min-w-24" @click="closeCreatedTokenDialog">我已保存</Button>
      </div>
    </DialogContent>
  </Dialog>
</template>
