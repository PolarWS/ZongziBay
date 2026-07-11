<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Loader2,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  User,
  KeyRound,
  Download,
  Server,
  Globe,
  Film,
  Tv,
  Subtitles,
  PlayCircle,
  ArrowRight,
  RefreshCw,
  Eye,
  EyeOff,
  FolderOpen,
  HardDrive,
  ExternalLink,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { sha256 } from '@/utils/crypto'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  getSystemStatusApiV1SystemStatusGet,
  getEnvConfigApiV1SystemEnvConfigGet,
  getExistingConfigApiV1SystemExistingConfigGet,
  testConnectionApiV1SystemTestConnectionPost,
  setupSystemApiV1SystemSetupPost,
  applyDefaultTmdbKeyApiV1SystemConfigApplyDefaultTmdbKeyPost,
  applyDefaultAssrtKeyApiV1SystemConfigApplyDefaultAssrtKeyPost,
} from '@/api/system'

definePageMeta({ layout: false })

const STEPS = [
  { id: 'welcome', label: '欢迎', icon: PlayCircle },
  { id: 'account', label: '账户', icon: User },
  { id: 'qb', label: '下载器', icon: Download },
  { id: 'api', label: 'API密钥', icon: KeyRound },
  { id: 'paths', label: '目录', icon: FolderOpen },
  { id: 'test', label: '连通性', icon: Globe },
  { id: 'finish', label: '完成', icon: Check },
]

const currentStep = ref(0)
const loading = ref(false)
const checkingStatus = ref(true)
const systemInitialized = ref(false)

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const secretKey = ref('')
const showSecretKey = ref(false)
const qbHost = ref('')
const qbUsername = ref('')
const qbPassword = ref('')
const qbApiKey = ref('')
const showQbPassword = ref(false)
const showQbApiKey = ref(false)
const tmdbApiKey = ref('')
const tmdbApiDomain = ref('https://api.themoviedb.org')
const assrtToken = ref('')
const assrtBaseUrl = ref('https://api.assrt.net')
const piratebayUrl = ref('https://apibay.org/q.php')
const animeGardenUrl = ref('https://animes.garden/api/resources')
const showTmdbKey = ref(false)
const showAssrtToken = ref(false)

// 路径配置
const downloadRootPath = ref('')
const targetRootPath = ref('')
const rootPath = ref('')
const defaultDownloadPath = ref('/temp')
const movieDownloadPath = ref('/temp')
const tvDownloadPath = ref('/temp')
const animeDownloadPath = ref('/temp')
const tempDownloadPath = ref('/temp')
const defaultTargetPath = ref('/nas/movies')
const movieTargetPath = ref('/nas/movies')
const tvTargetPath = ref('/nas/tv')
const animeTargetPath = ref('/nas/anime')

const testResults = ref<Record<string, { success: boolean; message: string }>>({})
const testing = ref(false)
const allTestsPassed = ref(false)
const { showZongzibayChan, init: initChan, setShowChan } = useZongzibayChan()

// qBittorrent 独立连通性测试
const testingQb = ref(false)
const qbTestPassed = ref(false)
const qbTestMessage = ref('')

// 标记已有配置的敏感字段（用于显示提示，不预填明文）
const existingFields = reactive({
  password: false,
  qbHost: false,
  qbPassword: false,
  qbApiKey: false,
  tmdbApiKey: false,
  assrtToken: false,
})

// 默认密钥应用状态
const applyingDefaults = reactive({
  tmdb: false,
  assrt: false,
})
const showDefaultKeyDialog = ref(false)
const defaultKeyTarget = ref<'tmdb' | 'assrt'>('tmdb')

const confirmApplyDefaultKeys = async () => {
  const target = defaultKeyTarget.value
  if (target === 'tmdb') applyingDefaults.tmdb = true
  else applyingDefaults.assrt = true
  showDefaultKeyDialog.value = false
  try {
    if (target === 'tmdb') {
      await applyDefaultTmdbKeyApiV1SystemConfigApplyDefaultTmdbKeyPost()
      existingFields.tmdbApiKey = true
      toast.success('TMDB 默认密钥已应用')
    } else {
      await applyDefaultAssrtKeyApiV1SystemConfigApplyDefaultAssrtKeyPost()
      existingFields.assrtToken = true
      toast.success('ASSRT 默认令牌已应用')
    }
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

function resetApiDefaults() {
  tmdbApiDomain.value = 'https://api.themoviedb.org'
  assrtBaseUrl.value = 'https://api.assrt.net'
  piratebayUrl.value = 'https://apibay.org/q.php'
  animeGardenUrl.value = 'https://animes.garden/api/resources'
  toast.success('已恢复为默认值')
}

function generateSecretKey() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let key = ''
  for (let i = 0; i < 32; i++) {
    key += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  secretKey.value = key
  toast.success('JWT 密钥已随机生成')
}

const particleStyle = (i: number) => ({
  left: `${Math.sin(i * 137.5) * 45 + 50}%`,
  top: `${Math.cos(i * 97.3) * 45 + 50}%`,
  animationDelay: `${(i * 0.7) % 8}s`,
  animationDuration: `${4 + (i % 3) * 2}s`,
  width: `${3 + (i % 4)}px`,
  height: `${3 + (i % 4)}px`,
  opacity: 0.12 + (i % 5) * 0.04,
})

async function checkStatus() {
  checkingStatus.value = true
  try {
    const res = await getSystemStatusApiV1SystemStatusGet({ skipErrorHandler: true })
    if (res.data?.initialized) {
      systemInitialized.value = true
      toast.error('系统已完成初始化，即将跳转登录页...')
      setTimeout(() => navigateTo('/login'), 2000)
    }
  } catch {
    // 未初始化，继续
  } finally {
    checkingStatus.value = false
  }
}

async function loadEnvConfig() {
  try {
    const res = await getEnvConfigApiV1SystemEnvConfigGet({ skipErrorHandler: true })
    if (res.data?.parsed) {
      const p = res.data.parsed
      if (p.username && !username.value) username.value = p.username
      if (p.password && !password.value) password.value = p.password
      if (p.tmdb_api_key && !tmdbApiKey.value) tmdbApiKey.value = p.tmdb_api_key
      if (p.assrt_token && !assrtToken.value) assrtToken.value = p.assrt_token
      if (p.qb_host && !qbHost.value) qbHost.value = p.qb_host
      if (p.qb_username && !qbUsername.value) qbUsername.value = p.qb_username
      if (p.qb_password && !qbPassword.value) qbPassword.value = p.qb_password
      if (p.qb_api_key && !qbApiKey.value) qbApiKey.value = p.qb_api_key
    }
  } catch {
    // nothing
  }
}

async function loadExistingConfig() {
  try {
    const res = await getExistingConfigApiV1SystemExistingConfigGet({ skipErrorHandler: true })
    if (!res.data) return
    const d = res.data

    // 安全：只预填用户名，密码标记已配置
    if (d.security?.username && !username.value) username.value = d.security.username
    if (d.security?.password) existingFields.password = true

    // TMDB：API Key 标记已配置，api_domain 预填
    if (d.tmdb?.api_key) existingFields.tmdbApiKey = true
    if (d.tmdb?.api_domain && !tmdbApiDomain.value) tmdbApiDomain.value = d.tmdb.api_domain

    // qBittorrent：host 和 username 非敏感可预填，密码/API Key 标记已配置
    if (d.qbittorrent?.host) existingFields.qbHost = true
    if (d.qbittorrent?.host && !qbHost.value) qbHost.value = d.qbittorrent.host
    if (d.qbittorrent?.username && !qbUsername.value) qbUsername.value = d.qbittorrent.username
    if (d.qbittorrent?.password) existingFields.qbPassword = true
    if (d.qbittorrent?.api_key) existingFields.qbApiKey = true

    // ASSRT：Token 标记已配置，base_url 预填
    if (d.subtitle?.assrt?.token) existingFields.assrtToken = true
    if (d.subtitle?.assrt?.base_url && !assrtBaseUrl.value) assrtBaseUrl.value = d.subtitle.assrt.base_url

    // PirateBay / Anime Garden 预填
    if (d.piratebay?.url && !piratebayUrl.value) piratebayUrl.value = d.piratebay.url
    if (d.anime_garden?.url && !animeGardenUrl.value) animeGardenUrl.value = d.anime_garden.url

    // 路径：全部预填
    const p = d.paths || {}
    if (p.download_root_path && !downloadRootPath.value) downloadRootPath.value = p.download_root_path
    if (p.target_root_path && !targetRootPath.value) targetRootPath.value = p.target_root_path
    if (p.root_path && !rootPath.value) rootPath.value = p.root_path
    if (p.default_download_path && !defaultDownloadPath.value) defaultDownloadPath.value = p.default_download_path
    if (p.movie_download_path && !movieDownloadPath.value) movieDownloadPath.value = p.movie_download_path
    if (p.tv_download_path && !tvDownloadPath.value) tvDownloadPath.value = p.tv_download_path
    if (p.anime_download_path && !animeDownloadPath.value) animeDownloadPath.value = p.anime_download_path
    if (p.temp_download_path && !tempDownloadPath.value) tempDownloadPath.value = p.temp_download_path
    if (p.default_target_path && !defaultTargetPath.value) defaultTargetPath.value = p.default_target_path
    if (p.movie_target_path && !movieTargetPath.value) movieTargetPath.value = p.movie_target_path
    if (p.tv_target_path && !tvTargetPath.value) tvTargetPath.value = p.tv_target_path
    if (p.anime_target_path && !animeTargetPath.value) animeTargetPath.value = p.anime_target_path
  } catch {
    // nothing
  }
}

function nextStep() {
  // 步骤 1：账号验证
  if (currentStep.value === 1) {
    if (!username.value.trim()) {
      toast.error('请输入用户名')
      return
    }
    if (!password.value.trim() && !existingFields.password) {
      toast.error('请输入登录密码')
      return
    }
    if (!secretKey.value.trim()) {
      toast.error('请设置 JWT 密钥（可点击"随机生成"）')
      return
    }
    if (secretKey.value.trim() === 'CHANGE_THIS_SECRET_KEY') {
      toast.error('请修改 JWT 密钥，不要使用默认值')
      return
    }
    if (secretKey.value.trim().length < 16) {
      toast.error('JWT 密钥长度至少 16 个字符，请重新生成')
      return
    }
  }
  // 步骤 2：qBittorrent 连通性验证
  if (currentStep.value === 2) {
    if (!qbTestPassed.value) {
      toast.error('请先测试 qBittorrent 连通性，通过后再继续')
      return
    }
  }
  // 步骤 5：连通性测试验证
  if (currentStep.value === 5) {
    if (!allTestsPassed.value) {
      toast.error('请先完成连通性测试，全部通过后再继续')
      return
    }
  }
  if (currentStep.value < STEPS.length - 1) currentStep.value++
}

function prevStep() {
  if (currentStep.value > 0) currentStep.value--
}

function goToStep(index: number) {
  // 只允许回到已经走过的步骤或当前步骤，禁止跳过未完成的步骤
  if (index > currentStep.value) {
    // 检查是否已经通过了该步骤前的所有必要验证
    for (let i = currentStep.value + 1; i <= index; i++) {
      if (i === 1) {
        if (!username.value.trim()) {
          toast.error('请先完成账户设置')
          return
        }
        if (!password.value.trim() && !existingFields.password) {
          toast.error('请先完成账户设置')
          return
        }
      }
      if (i === 2) {
        if (!qbTestPassed.value) {
          toast.error('请先通过 qBittorrent 连通性测试')
          return
        }
      }
    }
  }
  // 进入下载器步骤时重置连通性测试结果（用户可能修改了配置）
  if (index === 2) {
    qbTestPassed.value = false
    qbTestMessage.value = ''
  }
  currentStep.value = index
}

async function testQbConnection() {
  if (!qbHost.value.trim() && !existingFields.qbHost) {
    toast.error('请先填写 qBittorrent WebUI 地址')
    return
  }
  testingQb.value = true
  qbTestPassed.value = false
  qbTestMessage.value = ''
  try {
    const res = await testConnectionApiV1SystemTestConnectionPost(
      {
        qb_host: qbHost.value,
        qb_username: qbUsername.value,
        qb_password: qbPassword.value,
        qb_api_key: qbApiKey.value,
      },
      { skipErrorHandler: true },
    )
    const result = res.data?.results?.qbittorrent
    if (result?.success) {
      qbTestPassed.value = true
      qbTestMessage.value = result.message
      toast.success('qBittorrent 连接成功')
    } else {
      qbTestPassed.value = false
      qbTestMessage.value = result?.message || '连接失败'
      toast.error(result?.message || 'qBittorrent 连接失败')
    }
  } catch (e: any) {
    qbTestPassed.value = false
    qbTestMessage.value = e.message || '测试失败'
    toast.error(e.message || 'qBittorrent 连接测试失败')
  } finally {
    testingQb.value = false
  }
}

async function runTests() {
  testing.value = true
  testResults.value = {}
  allTestsPassed.value = false
  try {
    const res = await testConnectionApiV1SystemTestConnectionPost(
      {
        tmdb_api_key: tmdbApiKey.value,
        qb_host: qbHost.value,
        qb_username: qbUsername.value,
        qb_password: qbPassword.value,
        qb_api_key: qbApiKey.value,
        assrt_token: assrtToken.value,
        assrt_base_url: assrtBaseUrl.value,
      },
      { skipErrorHandler: true },
    )
    if (res.data?.results) {
      testResults.value = res.data.results
      allTestsPassed.value = res.data.all_success || false
    }
  } catch (e: any) {
    toast.error(e.message || '连通性测试失败')
  } finally {
    testing.value = false
  }
}

async function submitSetup() {
  if (!username.value) {
    toast.error('请输入用户名')
    return
  }
  if (!password.value && !existingFields.password) {
    toast.error('请输入登录密码')
    return
  }
  if (!secretKey.value.trim()) {
    toast.error('请设置 JWT 密钥（返回步骤1点击"随机生成"）')
    return
  }
  if (secretKey.value.trim() === 'CHANGE_THIS_SECRET_KEY') {
    toast.error('请修改 JWT 密钥，不要使用默认值')
    return
  }
  if (secretKey.value.trim().length < 16) {
    toast.error('JWT 密钥长度至少 16 个字符，请返回步骤1重新生成')
    return
  }
  loading.value = true
  try {
    await setupSystemApiV1SystemSetupPost(
      {
        username: username.value,
        password: password.value ? await sha256(password.value) : '',
        secret_key: secretKey.value,
        qb_host: qbHost.value,
        qb_username: qbUsername.value,
        qb_password: qbPassword.value,
        qb_api_key: qbApiKey.value,
        tmdb_api_key: tmdbApiKey.value,
        tmdb_api_domain: tmdbApiDomain.value,
        assrt_token: assrtToken.value,
        assrt_base_url: assrtBaseUrl.value,
        piratebay_url: piratebayUrl.value,
        anime_garden_url: animeGardenUrl.value,
        download_root_path: downloadRootPath.value,
        target_root_path: targetRootPath.value,
        root_path: rootPath.value,
        default_download_path: defaultDownloadPath.value,
        movie_download_path: movieDownloadPath.value,
        tv_download_path: tvDownloadPath.value,
        anime_download_path: animeDownloadPath.value,
        temp_download_path: tempDownloadPath.value,
        default_target_path: defaultTargetPath.value,
        movie_target_path: movieTargetPath.value,
        tv_target_path: tvTargetPath.value,
        anime_target_path: animeTargetPath.value,
      },
      { skipErrorHandler: true },
    )
    toast.success('初始化完成！')
    goToStep(6)
  } catch (e: any) {
    toast.error(e.message || '初始化失败')
  } finally {
    loading.value = false
  }
}

const testServices = [
  { key: 'tmdb', label: 'TMDB', icon: Film },
  { key: 'piratebay', label: '海盗湾 (PirateBay)', icon: Globe },
  { key: 'anime_garden', label: '动漫花园 (Anime Garden)', icon: Tv },
  { key: 'assrt', label: 'ASSRT 字幕', icon: Subtitles },
  { key: 'qbittorrent', label: 'qBittorrent', icon: Download },
]

onMounted(async () => {
  initChan()
  await checkStatus()
  if (!systemInitialized.value) {
    await loadExistingConfig()  // 从已有 YAML 配置文件预填
    await loadEnvConfig()       // 从 Docker 环境变量补充覆盖
  }
})
</script>

<template>
  <div class="setup-page">
    <div class="setup-bg">
      <div class="grid-overlay" />
      <div class="glow glow-1" />
      <div class="glow glow-2" />
      <div class="glow glow-3" />
      <div class="particles">
        <span v-for="i in 20" :key="i" class="particle" :style="particleStyle(i)" />
      </div>
    </div>

    <div v-if="checkingStatus" class="relative z-10 flex flex-col items-center gap-4">
      <Loader2 class="w-8 h-8 animate-spin text-primary" />
      <p class="text-muted-foreground">正在检查系统状态...</p>
    </div>

    <div v-else-if="systemInitialized" class="relative z-10 flex flex-col items-center gap-4 text-center px-6">
      <div class="logo-icon status-ok">
        <Check class="w-6 h-6" />
      </div>
      <h1 class="text-2xl font-bold">系统已完成初始化</h1>
      <p class="text-muted-foreground">即将跳转到登录页面...</p>
    </div>

    <div v-else class="relative z-10 w-full max-w-[640px] mx-auto px-4 sm:px-6">
      <div class="text-center mb-6">
        <div class="logo-wrapper">
          <div class="logo-ring logo-ring-outer" />
          <div class="logo-ring logo-ring-inner" />
          <div class="logo-icon">
            <ShieldCheck class="w-6 h-6" />
          </div>
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-foreground mt-5">ZongziBay 初始化</h1>
        <p class="text-muted-foreground mt-2 text-sm leading-relaxed">
          {{ currentStep === 0 ? '欢迎使用粽子湾！让我们完成几步初始配置' : STEPS[currentStep].label }}
        </p>
        <div class="divider-line" />
      </div>

      <div class="steps-indicator">
        <button
          v-for="(step, idx) in STEPS.slice(0, -1)"
          :key="step.id"
          class="step-dot"
          :class="{ active: idx <= currentStep, current: idx === currentStep }"
          @click="goToStep(idx)"
        >
          <span class="step-num">{{ idx + 1 }}</span>
          <span class="step-label">{{ step.label }}</span>
        </button>
      </div>

      <div class="setup-card">
        <div class="card-shine" />

        <!-- 欢迎 -->
        <div v-if="currentStep === 0" class="space-y-5">
          <div class="text-center py-2">
            <div class="welcome-icon-wrapper">
              <PlayCircle class="w-10 h-10 text-primary" />
            </div>
            <h2 class="text-lg font-semibold mt-3">欢迎使用粽子湾</h2>
            <p class="text-sm text-muted-foreground mt-2 leading-relaxed">
              粽子湾是一款集搜索、下载、整理于一体的媒体管理工具。<br />
              在开始之前，需要完成以下几项基本配置。
            </p>
            <div class="mt-5 space-y-2 text-left text-sm text-muted-foreground">
              <div class="flex items-start gap-2.5">
                <span class="text-primary font-bold mt-0.5 shrink-0">1.</span>
                <span>设置管理员账户和密码</span>
              </div>
              <div class="flex items-start gap-2.5">
                <span class="text-primary font-bold mt-0.5 shrink-0">2.</span>
                <span>配置 qBittorrent 下载器连接</span>
              </div>
              <div class="flex items-start gap-2.5">
                <span class="text-primary font-bold mt-0.5 shrink-0">3.</span>
                <span>填写 TMDB 和 ASSRT API 密钥</span>
              </div>
              <div class="flex items-start gap-2.5">
                <span class="text-primary font-bold mt-0.5 shrink-0">4.</span>
                <span>设置下载与归档目录</span>
              </div>
              <div class="flex items-start gap-2.5">
                <span class="text-primary font-bold mt-0.5 shrink-0">5.</span>
                <span>测试各项服务连通性</span>
              </div>
            </div>
          </div>
          <Button class="setup-btn" @click="nextStep">
            开始配置 <ArrowRight class="w-4 h-4 ml-1.5" />
          </Button>
        </div>

        <!-- 账户 -->
        <div v-if="currentStep === 1" class="space-y-4">
          <p class="text-xs text-red-500/80">* 账号为必填项，请设置管理员账户和密码</p>
          <div class="space-y-1.5">
            <Label for="su" class="text-sm font-medium text-foreground/75">用户名 <span class="text-red-500">*</span></Label>
            <div class="input-wrapper">
              <User class="input-icon" />
              <Input id="su" v-model="username" placeholder="设置管理员用户名" autocomplete="off" class="input-field" />
            </div>
          </div>
          <div class="space-y-1.5">
            <Label for="sp" class="text-sm font-medium text-foreground/75">登录密码 <span class="text-red-500">*</span></Label>
            <div class="input-wrapper">
              <KeyRound class="input-icon" />
              <Input id="sp" v-model="password" :type="showPassword ? 'text' : 'password'" :placeholder="existingFields.password ? '已配置，留空则保持不变' : '设置管理员密码'" autocomplete="new-password" class="input-field" />
              <button type="button" class="password-toggle" @click="showPassword = !showPassword">
                <Eye v-if="!showPassword" class="w-4 h-4" />
                <EyeOff v-else class="w-4 h-4" />
              </button>
            </div>
            <p class="text-xs text-muted-foreground/60 mt-1.5">如通过 Docker 环境变量注入，字段会自动填充</p>
          </div>
          <div class="space-y-1.5">
            <Label for="sk" class="text-sm font-medium text-foreground/75">JWT 密钥 <span class="text-red-500">*</span></Label>
            <div class="flex gap-2">
              <div class="input-wrapper flex-1">
                <ShieldCheck class="input-icon" />
                <Input id="sk" v-model="secretKey" :type="showSecretKey ? 'text' : 'password'" placeholder="点击右侧随机生成" autocomplete="off" class="input-field" />
                <button type="button" class="password-toggle" @click="showSecretKey = !showSecretKey">
                  <Eye v-if="!showSecretKey" class="w-4 h-4" />
                  <EyeOff v-else class="w-4 h-4" />
                </button>
              </div>
              <Button
                size="default"
                variant="outline"
                class="shrink-0 h-[44px]"
                @click="generateSecretKey"
              >
                <RefreshCw class="w-4 h-4 mr-1" />
                随机生成
              </Button>
            </div>
            <p class="text-xs text-muted-foreground/60 mt-1.5">用于 JWT Token 签名，部署前务必修改此密钥，确保系统安全</p>
          </div>
          <div class="flex items-center justify-between pt-3 border-t border-border/50">
            <div>
              <span class="text-sm font-medium text-foreground/75">显示粽子娘</span>
              <p class="text-xs text-muted-foreground/60 mt-0.5">关闭后右下角粽子娘图片将隐藏</p>
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

        <!-- qBittorrent -->
        <div v-if="currentStep === 2" class="space-y-4">
          <p class="text-xs text-red-500/80">* 下载器为必填项，请配置 qBittorrent 连接并通过连通性测试</p>
          <div class="space-y-1.5">
            <Label for="qb-host" class="text-sm font-medium text-foreground/75">WebUI 地址 <span class="text-red-500">*</span></Label>
            <div class="input-wrapper">
              <Server class="input-icon" />
              <Input id="qb-host" v-model="qbHost" placeholder="http://localhost:8080" class="input-field" />
            </div>
          </div>
          <p class="text-xs text-muted-foreground/60 -mt-3 mb-1">以下两种认证方式任选其一即可</p>
          <div class="space-y-1.5">
            <Label class="text-sm font-medium text-foreground/75">用户名密码认证</Label>
            <div class="grid grid-cols-2 gap-2">
              <Input v-model="qbUsername" placeholder="用户名" class="input-field !pl-3" />
              <div class="input-wrapper">
                <Input v-model="qbPassword" :type="showQbPassword ? 'text' : 'password'" :placeholder="existingFields.qbPassword ? '已配置，留空则保持不变' : '密码'" class="input-field !pl-3 !pr-8" />
                <button type="button" class="password-toggle" @click="showQbPassword = !showQbPassword">
                  <Eye v-if="!showQbPassword" class="w-4 h-4" />
                  <EyeOff v-else class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="flex-1 h-px bg-border" />
            <span class="text-xs text-muted-foreground shrink-0">或者</span>
            <div class="flex-1 h-px bg-border" />
          </div>
          <div class="space-y-1.5">
            <Label for="qb-api" class="text-sm font-medium text-foreground/75">API Key <span class="text-xs text-muted-foreground/60">(qB 5.2.0+)</span></Label>
            <div class="input-wrapper">
              <KeyRound class="input-icon" />
              <Input id="qb-api" v-model="qbApiKey" :type="showQbApiKey ? 'text' : 'password'" :placeholder="existingFields.qbApiKey ? '已配置，留空则保持不变' : 'qBittorrent API Key'" class="input-field" />
              <button type="button" class="password-toggle" @click="showQbApiKey = !showQbApiKey">
                <Eye v-if="!showQbApiKey" class="w-4 h-4" />
                <EyeOff v-else class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- qB 连通性测试 -->
          <div class="pt-2 border-t border-border/50">
            <div class="flex items-center gap-2">
              <Button size="sm" variant="outline" :disabled="testingQb" :class="{ '!bg-red-600 !text-white !border-red-600 hover:!bg-red-700': !qbTestPassed && !testingQb }" @click="testQbConnection">
                <Loader2 v-if="testingQb" class="w-4 h-4 mr-1.5 animate-spin" />
                <RefreshCw v-else class="w-4 h-4 mr-1.5" />
                {{ testingQb ? '测试中…' : '测试连接' }}
              </Button>
              <div v-if="qbTestPassed" class="flex items-center gap-1.5 text-green-600 text-sm">
                <Check class="w-4 h-4" />
                <span>连接成功</span>
              </div>
              <div v-else-if="qbTestMessage && !testingQb" class="flex items-center gap-1.5 text-red-500 text-sm">
                <X class="w-4 h-4" />
                <span class="truncate max-w-[200px]">{{ qbTestMessage }}</span>
              </div>
            </div>
            <p v-if="qbTestPassed" class="text-xs text-muted-foreground/60 mt-1">连通性测试通过，可以继续下一步</p>
          </div>
        </div>

        <!-- API Keys -->
        <div v-if="currentStep === 3" class="space-y-4">
          <div class="flex items-center justify-between">
            <p class="text-xs text-muted-foreground">配置各服务的 API 密钥和连接地址，通常保持默认即可</p>
            <Button size="xs" variant="ghost" class="text-xs h-7 px-2 text-muted-foreground hover:text-foreground" @click="resetApiDefaults">
              <RefreshCw class="w-3 h-3 mr-1" />恢复默认
            </Button>
          </div>

          <!-- TMDB -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <Film class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-medium text-foreground/75">TMDB</span>
              </div>
              <a href="https://github.com/PolarWS/ZongziBay/blob/main/docs/api_keys_guide.md" target="_blank" class="flex items-center gap-1 text-xs text-primary hover:underline shrink-0">
                获取教程 <ExternalLink class="w-3 h-3" />
              </a>
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs">API Key</Label>
              <div class="flex gap-2">
                <div class="input-wrapper flex-1">
                  <Input v-model="tmdbApiKey" :type="showTmdbKey ? 'text' : 'password'" :placeholder="existingFields.tmdbApiKey ? '已配置，留空则保持不变' : '从 tmdb.org 获取'" class="input-field !pl-3 !text-xs" />
                  <button type="button" class="password-toggle" @click="showTmdbKey = !showTmdbKey">
                    <Eye v-if="!showTmdbKey" class="w-3.5 h-3.5" />
                    <EyeOff v-else class="w-3.5 h-3.5" />
                  </button>
                </div>
                <Button size="sm" variant="outline" class="shrink-0 h-[44px]" :disabled="applyingDefaults.tmdb || applyingDefaults.assrt" @click="applyDefaultTmdbKey">
                  {{ applyingDefaults.tmdb ? '应用中…' : '使用默认' }}
                </Button>
              </div>
            </div>
            <div class="space-y-1">
              <Label class="text-xs">API 域名</Label>
              <Input v-model="tmdbApiDomain" placeholder="https://api.themoviedb.org" class="input-field !pl-3 !text-xs" />
            </div>
          </div>

          <!-- ASSRT -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <Subtitles class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-medium text-foreground/75">ASSRT 字幕</span>
              </div>
              <a href="https://github.com/PolarWS/ZongziBay/blob/main/docs/api_keys_guide.md" target="_blank" class="flex items-center gap-1 text-xs text-primary hover:underline shrink-0">
                获取教程 <ExternalLink class="w-3 h-3" />
              </a>
            </div>
            <div class="space-y-1.5">
              <Label class="text-xs">Token</Label>
              <div class="flex gap-2">
                <div class="input-wrapper flex-1">
                  <Input v-model="assrtToken" :type="showAssrtToken ? 'text' : 'password'" :placeholder="existingFields.assrtToken ? '已配置，留空则保持不变' : '从 assrt.net 获取'" class="input-field !pl-3 !text-xs" />
                  <button type="button" class="password-toggle" @click="showAssrtToken = !showAssrtToken">
                    <Eye v-if="!showAssrtToken" class="w-3.5 h-3.5" />
                    <EyeOff v-else class="w-3.5 h-3.5" />
                  </button>
                </div>
                <Button size="sm" variant="outline" class="shrink-0 h-[44px]" :disabled="applyingDefaults.assrt || applyingDefaults.tmdb" @click="applyDefaultAssrtKey">
                  {{ applyingDefaults.assrt ? '应用中…' : '使用默认' }}
                </Button>
              </div>
            </div>
            <div class="space-y-1">
              <Label class="text-xs">API 地址</Label>
              <Input v-model="assrtBaseUrl" class="input-field !pl-3 !text-xs" />
            </div>
          </div>

          <!-- PirateBay -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center gap-2">
              <Globe class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm font-medium text-foreground/75">海盗湾 (PirateBay)</span>
            </div>
            <p class="text-xs text-muted-foreground/60">公开 API，无需额外申请密钥，保持默认即可</p>
            <div class="space-y-1">
              <Label class="text-xs">API 地址</Label>
              <Input v-model="piratebayUrl" class="input-field !pl-3 !text-xs" />
            </div>
          </div>

          <!-- Anime Garden -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center gap-2">
              <Tv class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm font-medium text-foreground/75">动漫花园 (Anime Garden)</span>
            </div>
            <p class="text-xs text-muted-foreground/60">公开 API，无需额外申请密钥，保持默认即可</p>
            <div class="space-y-1">
              <Label class="text-xs">API 地址</Label>
              <Input v-model="animeGardenUrl" class="input-field !pl-3 !text-xs" />
            </div>
          </div>
        </div>

        <!-- 项目目录 -->
        <div v-if="currentStep === 4" class="space-y-5">
          <p class="text-xs text-muted-foreground">配置文件的下载保存路径与刮削归档路径，通常保持默认即可使用</p>

          <!-- 根路径 -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center gap-2">
              <HardDrive class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm font-medium text-foreground/75">根路径</span>
            </div>
            <p class="text-xs text-muted-foreground/60">
              用于补全路径前缀，如 qBittorrent 挂载 /video 但本项目挂载 D:/docker/video，则填 D:/docker；一致则留空
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1 sm:col-span-2">
                <Label class="text-xs">下载根路径</Label>
                <Input v-model="downloadRootPath" placeholder="留空即不补全前缀" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1 sm:col-span-2">
                <Label class="text-xs">归档根路径</Label>
                <Input v-model="targetRootPath" placeholder="留空即不补全前缀" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1 sm:col-span-2">
                <Label class="text-xs">回退根路径</Label>
                <Input v-model="rootPath" placeholder="未配上面两个时回退用" class="input-field !pl-3 !text-xs" />
              </div>
            </div>
          </div>

          <!-- 下载路径 -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center gap-2">
              <Download class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm font-medium text-foreground/75">下载路径</span>
            </div>
            <p class="text-xs text-muted-foreground/60">qBittorrent 下载时的保存位置，各分类可独立配置</p>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1">
                <Label class="text-xs">默认</Label>
                <Input v-model="defaultDownloadPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">电影</Label>
                <Input v-model="movieDownloadPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">剧集</Label>
                <Input v-model="tvDownloadPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">番剧</Label>
                <Input v-model="animeDownloadPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1 sm:col-span-2">
                <Label class="text-xs">临时</Label>
                <Input v-model="tempDownloadPath" class="input-field !pl-3 !text-xs" />
              </div>
            </div>
          </div>

          <!-- 归档路径 -->
          <div class="space-y-3 border border-border/60 rounded-lg p-4">
            <div class="flex items-center gap-2">
              <FolderOpen class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm font-medium text-foreground/75">归档路径</span>
            </div>
            <p class="text-xs text-muted-foreground/60">整理刮削后的最终存储位置，各分类可独立配置</p>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1">
                <Label class="text-xs">默认</Label>
                <Input v-model="defaultTargetPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">电影</Label>
                <Input v-model="movieTargetPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">剧集</Label>
                <Input v-model="tvTargetPath" class="input-field !pl-3 !text-xs" />
              </div>
              <div class="space-y-1">
                <Label class="text-xs">番剧</Label>
                <Input v-model="animeTargetPath" class="input-field !pl-3 !text-xs" />
              </div>
            </div>
          </div>
        </div>

        <!-- 连通性测试 -->
        <div v-if="currentStep === 5" class="space-y-4">
          <p class="text-sm text-muted-foreground">测试各项服务的连接状态，建议全部通过后再完成初始化</p>
          <div class="space-y-2">
            <div
              v-for="svc in testServices"
              :key="svc.key"
              class="test-item"
              :class="{ success: testResults[svc.key]?.success, fail: testResults[svc.key] && !testResults[svc.key].success }"
            >
              <div class="flex items-center gap-3">
                <component :is="svc.icon" class="w-4 h-4 shrink-0" />
                <span class="text-sm font-medium">{{ svc.label }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span v-if="!testResults[svc.key] && !testing" class="text-xs text-muted-foreground/50">等待测试</span>
                <span v-else-if="!testResults[svc.key] && testing" class="text-xs text-muted-foreground">测试中...</span>
                <template v-else>
                  <Check v-if="testResults[svc.key]?.success" class="w-4 h-4 text-green-500" />
                  <X v-else class="w-4 h-4 text-red-500" />
                  <span class="text-xs" :class="testResults[svc.key]?.success ? 'text-green-600' : 'text-red-600'">
                    {{ testResults[svc.key]?.message }}
                  </span>
                </template>
              </div>
            </div>
          </div>
          <Button class="setup-btn" :disabled="testing" @click="runTests">
            <Loader2 v-if="testing" class="w-4 h-4 mr-2 animate-spin" />
            <RefreshCw v-else class="w-4 h-4 mr-2" />
            {{ testing ? '测试中...' : '开始测试' }}
          </Button>
          <p v-if="allTestsPassed" class="text-center text-sm text-green-600 font-medium">全部服务连通性正常，可以继续完成初始化</p>
        </div>

        <!-- 完成 -->
        <div v-if="currentStep === 6" class="space-y-5 text-center">
          <div class="finish-icon-wrapper">
            <Check class="w-10 h-10 text-green-500" />
          </div>
          <div>
            <h2 class="text-lg font-semibold">初始化完成</h2>
            <p class="text-sm text-muted-foreground mt-2 leading-relaxed">系统已配置完毕，请使用设置的用户名和密码登录</p>
          </div>
          <Button class="setup-btn" @click="navigateTo('/login')">
            前往登录 <ArrowRight class="w-4 h-4 ml-1.5" />
          </Button>
        </div>
      </div>

      <div v-if="currentStep > 0 && currentStep < 6" class="flex items-center justify-between mt-5">
        <Button variant="outline" size="sm" @click="prevStep"><ChevronLeft class="w-4 h-4 mr-1" />上一步</Button>
        <Button v-if="currentStep === 5" size="sm" :disabled="loading" @click="submitSetup">
          <Loader2 v-if="loading" class="w-4 h-4 mr-1.5 animate-spin" />
          {{ loading ? '初始化中...' : '完成初始化' }}
        </Button>
        <Button v-else-if="currentStep < 5" size="sm" @click="nextStep">下一步 <ChevronRight class="w-4 h-4 ml-1" /></Button>
      </div>

      <p class="text-center text-xs text-muted-foreground/40 mt-6 tracking-wider">&copy; ZongziBay {{ new Date().getFullYear() }}</p>
    </div>

    <img v-if="showZongzibayChan" src="~/assets/img/zongzibay-chan-03.png" alt="zongzibay-chan" class="character-img" />

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
  </div>
</template>

<style scoped>
.setup-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden; background: var(--background); color: var(--foreground); }
.setup-bg { position: absolute; inset: 0; pointer-events: none; }
.grid-overlay { position: absolute; inset: 0; background-size: 40px 40px; background-image: linear-gradient(to right, rgba(0, 0, 0, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(0, 0, 0, 0.04) 1px, transparent 1px); mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 100%); -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 100%); }
.glow { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.5; }
.glow-1 { width: min(400px, 90vw); height: min(400px, 90vw); background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.15), transparent 70%); top: -10%; left: 50%; transform: translateX(-50%); animation: float-1 8s ease-in-out infinite; }
.glow-2 { width: min(300px, 70vw); height: min(300px, 70vw); background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.08), transparent 70%); bottom: 10%; left: -5%; animation: float-2 10s ease-in-out infinite; }
.glow-3 { width: min(250px, 60vw); height: min(250px, 60vw); background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.06), transparent 70%); top: 40%; right: -5%; animation: float-3 12s ease-in-out infinite; }
.particles { position: absolute; inset: 0; }
.particle { position: absolute; border-radius: 50%; background: var(--primary); animation: particle-float linear infinite; }
@keyframes particle-float { 0%, 100% { transform: translateY(0) translateX(0) scale(1); } 25% { transform: translateY(-20px) translateX(8px) scale(1.4); } 50% { transform: translateY(-10px) translateX(-5px) scale(0.8); } 75% { transform: translateY(-25px) translateX(-12px) scale(1.2); } }
@keyframes float-1 { 0%, 100% { transform: translateX(-50%) translateY(0); } 50% { transform: translateX(-50%) translateY(20px); } }
@keyframes float-2 { 0%, 100% { transform: translateY(0) translateX(0); } 50% { transform: translateY(-15px) translateX(10px); } }
@keyframes float-3 { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(15px); } }
.logo-wrapper { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 72px; height: 72px; }
.logo-icon { position: relative; z-index: 2; display: flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 14px; background: oklch(0.79 0.18 145 / 0.12); border: 1px solid oklch(0.79 0.18 145 / 0.25); color: var(--primary); box-shadow: 0 0 20px oklch(0.79 0.18 145 / 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.logo-icon.status-ok { color: oklch(0.6 0.2 145); background: oklch(0.6 0.2 145 / 0.12); border-color: oklch(0.6 0.2 145 / 0.25); box-shadow: 0 0 20px oklch(0.6 0.2 145 / 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.logo-ring { position: absolute; border-radius: 50%; border: 1px solid oklch(0.79 0.18 145 / 0.15); }
.logo-ring-outer { width: 72px; height: 72px; animation: ring-pulse 3s ease-in-out infinite; }
.logo-ring-inner { width: 56px; height: 56px; animation: ring-pulse 3s ease-in-out infinite 0.5s; }
@keyframes ring-pulse { 0%, 100% { transform: scale(1); opacity: 0.4; } 50% { transform: scale(1.08); opacity: 0.8; } }
.divider-line { width: 48px; height: 2px; margin: 14px auto 0; border-radius: 1px; background: linear-gradient(90deg, transparent, oklch(0.79 0.18 145 / 0.3), oklch(0.79 0.18 145 / 0.5), oklch(0.79 0.18 145 / 0.3), transparent); }
.steps-indicator { display: flex; justify-content: center; gap: 10px; margin-bottom: 20px; flex-wrap: nowrap; }
.step-dot { display: flex; align-items: center; gap: 4px; padding: 5px 10px; border-radius: 20px; background: var(--muted); border: 1px solid var(--border); font-size: 11px; color: var(--muted-foreground); cursor: pointer; transition: all 0.25s ease; white-space: nowrap; }
.step-dot:hover { border-color: oklch(0.79 0.18 145 / 0.3); }
.step-dot.active { background: oklch(0.79 0.18 145 / 0.1); border-color: oklch(0.79 0.18 145 / 0.3); color: var(--primary); }
.step-dot.current { background: oklch(0.79 0.18 145 / 0.15); border-color: var(--primary); color: var(--primary); font-weight: 600; }
.step-num { display: flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 50%; background: var(--muted-foreground); color: var(--muted); font-size: 9px; font-weight: 700; }
.step-dot.active .step-num { background: var(--primary); color: var(--primary-foreground); }
.setup-card { position: relative; background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 28px 24px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 8px 32px rgba(0, 0, 0, 0.04), 0 0 0 1px oklch(0.79 0.18 145 / 0.04); backdrop-filter: blur(12px); overflow: hidden; }
.card-shine { position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, oklch(0.79 0.18 145 / 0.3), transparent); }
.input-wrapper { position: relative; }
.input-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); width: 16px; height: 16px; color: var(--muted-foreground); z-index: 1; pointer-events: none; transition: color 0.2s ease; }
.input-field { padding-left: 36px !important; height: 44px; background: var(--background) !important; border-color: var(--border) !important; border-radius: 10px; font-size: 14px; transition: all 0.25s ease; }
.input-field:focus { border-color: oklch(0.79 0.18 145 / 0.5) !important; box-shadow: 0 0 0 3px oklch(0.79 0.18 145 / 0.08), 0 0 20px oklch(0.79 0.18 145 / 0.04) !important; }
.input-wrapper:focus-within .input-icon { color: var(--primary); }
.password-toggle { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: var(--muted-foreground); background: none; border: none; cursor: pointer; padding: 2px; z-index: 1; transition: color 0.2s; }
.password-toggle:hover { color: var(--foreground); }
.setup-btn { width: 100%; height: 44px; font-size: 15px; font-weight: 600; border-radius: 10px; letter-spacing: 0.02em; background: var(--primary) !important; color: var(--primary-foreground) !important; box-shadow: 0 2px 8px oklch(0.79 0.18 145 / 0.25), 0 0 0 1px oklch(0.79 0.18 145 / 0.15); transition: all 0.3s ease; }
.setup-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 16px oklch(0.79 0.18 145 / 0.35), 0 0 0 2px oklch(0.79 0.18 145 / 0.2); }
.setup-btn:active:not(:disabled) { transform: translateY(0) scale(0.98); }
.setup-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.welcome-icon-wrapper { display: inline-flex; align-items: center; justify-content: center; width: 64px; height: 64px; border-radius: 16px; background: oklch(0.79 0.18 145 / 0.08); border: 1px solid oklch(0.79 0.18 145 / 0.15); }
.test-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-radius: 10px; background: var(--muted); border: 1px solid var(--border); transition: all 0.25s ease; }
.test-item.success { border-color: oklch(0.6 0.2 145 / 0.3); background: oklch(0.6 0.2 145 / 0.04); }
.test-item.fail { border-color: oklch(0.6 0.25 25 / 0.3); background: oklch(0.6 0.25 25 / 0.04); }
.finish-icon-wrapper { display: inline-flex; align-items: center; justify-content: center; width: 72px; height: 72px; border-radius: 50%; background: oklch(0.6 0.2 145 / 0.1); border: 2px solid oklch(0.6 0.2 145 / 0.3); box-shadow: 0 0 30px oklch(0.6 0.2 145 / 0.12); animation: finish-pulse 2s ease-in-out infinite; }
@keyframes finish-pulse { 0%, 100% { transform: scale(1); box-shadow: 0 0 20px oklch(0.6 0.2 145 / 0.12); } 50% { transform: scale(1.05); box-shadow: 0 0 40px oklch(0.6 0.2 145 / 0.2); } }
.character-img { position: absolute; bottom: 0; right: 0; max-height: 30vh; max-width: 20vw; width: auto; height: auto; object-fit: contain; pointer-events: none; z-index: 5; opacity: 0.85; filter: drop-shadow(0 0 20px rgba(0, 0, 0, 0.05)); }
@media (max-width: 640px) { .character-img { max-height: 20vh; max-width: 30vw; opacity: 0.4; } .setup-card { padding: 20px 16px; border-radius: 16px; } .step-label { font-size: 10px; } }
:global(.dark) .grid-overlay { background-image: linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px); }
:global(.dark) .glow-1 { background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.1), transparent 70%); }
:global(.dark) .glow-2 { background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.05), transparent 70%); }
:global(.dark) .glow-3 { background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.04), transparent 70%); }
:global(.dark) .setup-card { box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2), 0 8px 32px rgba(0, 0, 0, 0.15), 0 0 0 1px oklch(0.79 0.18 145 / 0.03); }
:global(.dark) .logo-icon { background: oklch(0.79 0.18 145 / 0.08); box-shadow: 0 0 20px oklch(0.79 0.18 145 / 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05); }
:global(.dark) .input-field { background: oklch(0.21 0.01 260 / 0.6) !important; }
:global(.dark) .input-field:focus { box-shadow: 0 0 0 3px oklch(0.79 0.18 145 / 0.06), 0 0 20px oklch(0.79 0.18 145 / 0.03) !important; }
:global(.dark) .card-shine { background: linear-gradient(90deg, transparent, oklch(0.79 0.18 145 / 0.2), transparent); }
</style>
