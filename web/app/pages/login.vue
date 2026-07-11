<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, Lock, User, KeyRound } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import api from '@/api'
import { getSystemStatusApiV1SystemStatusGet } from '@/api/system'

definePageMeta({
  layout: false,
})

const { setToken } = useAuth()

const username = ref('')
const password = ref('')
const loading = ref(false)
const { showZongzibayChan, init: initChan } = useZongzibayChan()

// 生成粒子随机位置
const particleStyle = (i: number) => ({
  left: `${Math.sin(i * 137.5) * 45 + 50}%`,
  top: `${Math.cos(i * 97.3) * 45 + 50}%`,
  animationDelay: `${(i * 0.7) % 8}s`,
  animationDuration: `${4 + (i % 3) * 2}s`,
  width: `${3 + (i % 4)}px`,
  height: `${3 + (i % 4)}px`,
  opacity: 0.12 + (i % 5) * 0.04,
})

// 提交登录：校验后请求 token，成功则写 token 并跳转首页
const handleLogin = async () => {
  if (!username.value || !password.value) {
    toast.error('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    const res = await api.users.loginForAccessTokenApiV1UsersLoginPost(
      { username: username.value, password: password.value },
      { skipErrorHandler: true },
    )

    if (res.data?.access_token) {
      setToken(res.data.access_token)
      toast.success('登录成功')
      await navigateTo('/')
    }
  } catch (e: any) {
    toast.error(e.message || '登录失败，请检查用户名和密码')
    toast.error(msg)
  } finally {
    loading.value = false
  }
}

// 页面加载时检查系统是否已初始化，未初始化则跳转引导页
onMounted(async () => {
  initChan()
  try {
    const res = await getSystemStatusApiV1SystemStatusGet({ skipErrorHandler: true })
    if (res.data && !res.data.initialized) {
      await navigateTo('/setup')
    }
  } catch {
    // 网络错误等，忽略
  }
})
</script>

<template>
  <div class="login-page">
    <!-- 背景装饰 -->
    <div class="login-bg">
      <div class="grid-overlay" />
      <div class="glow glow-1" />
      <div class="glow glow-2" />
      <div class="glow glow-3" />
      <!-- 浮动粒子 -->
      <div class="particles">
        <span v-for="i in 20" :key="i" class="particle" :style="particleStyle(i)" />
      </div>
    </div>

    <!-- 内容 -->
    <div class="relative z-10 w-full max-w-[420px] mx-auto px-6">
      <!-- Logo 区域 -->
      <div class="text-center mb-8">
        <!-- Logo 图标 -->
        <div class="logo-wrapper">
          <div class="logo-ring logo-ring-outer" />
          <div class="logo-ring logo-ring-inner" />
          <div class="logo-icon">
            <Lock class="w-6 h-6" />
          </div>
        </div>
        <h1 class="text-3xl font-bold tracking-tight text-foreground mt-6">
          欢迎回来
        </h1>
        <p class="text-muted-foreground mt-2.5 text-[15px] leading-relaxed">
          登录 <span class="text-primary font-semibold">粽子湾</span> 以继续使用
        </p>
        <!-- 装饰分割线 -->
        <div class="divider-line" />
      </div>

      <!-- 登录卡片 -->
      <div class="login-card">
        <!-- 卡片顶部光泽 -->
        <div class="card-shine" />
        <div class="space-y-4">
          <div class="space-y-1.5">
            <Label for="username" class="text-sm font-medium text-foreground/75">用户名</Label>
            <div class="input-wrapper">
              <User class="input-icon" />
              <Input
                id="username"
                v-model="username"
                placeholder="请输入用户名"
                autocomplete="username"
                class="input-field"
                @keyup.enter="handleLogin"
              />
            </div>
          </div>
          <div class="space-y-1.5">
            <Label for="password" class="text-sm font-medium text-foreground/75">密码</Label>
            <div class="input-wrapper">
              <KeyRound class="input-icon" />
              <Input
                id="password"
                v-model="password"
                type="password"
                placeholder="请输入密码"
                autocomplete="current-password"
                class="input-field"
                @keyup.enter="handleLogin"
              />
            </div>
          </div>
        </div>

        <Button
          class="login-btn"
          :disabled="loading"
          @click="handleLogin"
        >
          <Loader2 v-if="loading" class="w-4 h-4 mr-2 animate-spin" />
          {{ loading ? '登录中...' : '登录' }}
        </Button>
      </div>

      <!-- 底部 -->
      <p class="text-center text-xs text-muted-foreground/50 mt-6 tracking-widest uppercase">
        &copy; ZongziBay {{ new Date().getFullYear() }}
      </p>
    </div>

    <!-- 右下角角色图片 -->
    <img
      v-if="showZongzibayChan"
      src="~/assets/img/zongzibay-chan-02.png"
      alt="zongzibay-chan"
      class="character-img"
    />
  </div>
</template>

<style scoped>
/* ========================================
   基础布局
   ======================================== */
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: var(--background);
  color: var(--foreground);
}

/* ========================================
   背景层
   ======================================== */
.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-size: 40px 40px;
  background-image:
    linear-gradient(to right, rgba(0, 0, 0, 0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0, 0, 0, 0.04) 1px, transparent 1px);
  mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 100%);
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 50%, black 30%, transparent 100%);
}

/* 光晕装饰 */
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
}

.glow-1 {
  width: min(400px, 90vw);
  height: min(400px, 90vw);
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.15), transparent 70%);
  top: -10%;
  left: 50%;
  transform: translateX(-50%);
  animation: float-1 8s ease-in-out infinite;
}

.glow-2 {
  width: min(300px, 70vw);
  height: min(300px, 70vw);
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.08), transparent 70%);
  bottom: 10%;
  left: -5%;
  animation: float-2 10s ease-in-out infinite;
}

.glow-3 {
  width: min(250px, 60vw);
  height: min(250px, 60vw);
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.06), transparent 70%);
  top: 40%;
  right: -5%;
  animation: float-3 12s ease-in-out infinite;
}

/* 浮动粒子 */
.particles {
  position: absolute;
  inset: 0;
}

.particle {
  position: absolute;
  border-radius: 50%;
  background: var(--primary);
  animation: particle-float linear infinite;
}

@keyframes particle-float {
  0%, 100% {
    transform: translateY(0) translateX(0) scale(1);
  }
  25% {
    transform: translateY(-20px) translateX(8px) scale(1.4);
  }
  50% {
    transform: translateY(-10px) translateX(-5px) scale(0.8);
  }
  75% {
    transform: translateY(-25px) translateX(-12px) scale(1.2);
  }
}

@keyframes float-1 {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(20px); }
}

@keyframes float-2 {
  0%, 100% { transform: translateY(0) translateX(0); }
  50% { transform: translateY(-15px) translateX(10px); }
}

@keyframes float-3 {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(15px); }
}

/* ========================================
   Logo 区域
   ======================================== */
.logo-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
}

.logo-icon {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: oklch(0.79 0.18 145 / 0.12);
  border: 1px solid oklch(0.79 0.18 145 / 0.25);
  color: var(--primary);
  box-shadow:
    0 0 20px oklch(0.79 0.18 145 / 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* 光环动画 */
.logo-ring {
  position: absolute;
  border-radius: 50%;
  border: 1px solid oklch(0.79 0.18 145 / 0.15);
}

.logo-ring-outer {
  width: 72px;
  height: 72px;
  animation: ring-pulse 3s ease-in-out infinite;
}

.logo-ring-inner {
  width: 56px;
  height: 56px;
  animation: ring-pulse 3s ease-in-out infinite 0.5s;
}

@keyframes ring-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.4;
  }
  50% {
    transform: scale(1.08);
    opacity: 0.8;
  }
}

/* 装饰分割线 */
.divider-line {
  width: 48px;
  height: 2px;
  margin: 18px auto 0;
  border-radius: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    oklch(0.79 0.18 145 / 0.3),
    oklch(0.79 0.18 145 / 0.5),
    oklch(0.79 0.18 145 / 0.3),
    transparent
  );
}

/* ========================================
   登录卡片
   ======================================== */
.login-card {
  position: relative;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 28px 24px;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.04),
    0 8px 32px rgba(0, 0, 0, 0.04),
    0 0 0 1px oklch(0.79 0.18 145 / 0.04);
  backdrop-filter: blur(12px);
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.login-card:hover {
  transform: translateY(-1px);
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.05),
    0 12px 40px rgba(0, 0, 0, 0.06),
    0 0 0 1px oklch(0.79 0.18 145 / 0.08);
}

/* 卡片顶部光泽 */
.card-shine {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    oklch(0.79 0.18 145 / 0.3),
    transparent
  );
}

/* ========================================
   输入框
   ======================================== */
.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--muted-foreground);
  z-index: 1;
  pointer-events: none;
  transition: color 0.2s ease;
}

.input-field {
  padding-left: 36px !important;
  height: 44px;
  background: var(--background) !important;
  border-color: var(--border) !important;
  border-radius: 10px;
  font-size: 14px;
  transition: all 0.25s ease;
}

.input-field:focus {
  border-color: oklch(0.79 0.18 145 / 0.5) !important;
  box-shadow:
    0 0 0 3px oklch(0.79 0.18 145 / 0.08),
    0 0 20px oklch(0.79 0.18 145 / 0.04) !important;
  background: var(--background) !important;
}

.input-wrapper:focus-within .input-icon {
  color: var(--primary);
}

/* ========================================
   登录按钮
   ======================================== */
.login-btn {
  width: 100%;
  height: 44px;
  margin-top: 24px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 10px;
  letter-spacing: 0.02em;
  background: var(--primary) !important;
  color: var(--primary-foreground) !important;
  box-shadow:
    0 2px 8px oklch(0.79 0.18 145 / 0.25),
    0 0 0 1px oklch(0.79 0.18 145 / 0.15);
  transition: all 0.3s ease;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow:
    0 4px 16px oklch(0.79 0.18 145 / 0.35),
    0 0 0 2px oklch(0.79 0.18 145 / 0.2);
}

.login-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

/* ========================================
   角色图片
   ======================================== */
.character-img {
  position: absolute;
  bottom: 0;
  right: 0;
  max-height: 35vh;
  max-width: 25vw;
  width: auto;
  height: auto;
  object-fit: contain;
  pointer-events: none;
  z-index: 5;
  opacity: 0.95;
  transition: opacity 0.3s ease, transform 0.3s ease;
  filter: drop-shadow(0 0 20px rgba(0, 0, 0, 0.05));
}

/* ========================================
   响应式
   ======================================== */
@media (max-width: 640px) {
  .character-img {
    max-height: 25vh;
    max-width: 35vw;
    opacity: 0.5;
  }

  .login-card {
    padding: 20px 16px;
    border-radius: 16px;
  }

  .divider-line {
    margin: 14px auto 0;
  }

  .logo-wrapper {
    width: 60px;
    height: 60px;
  }

  .logo-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
  }

  .logo-ring-outer {
    width: 60px;
    height: 60px;
  }

  .logo-ring-inner {
    width: 48px;
    height: 48px;
  }
}

/* ========================================
   Dark mode 适配
   ======================================== */
:global(.dark) .grid-overlay {
  background-image:
    linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
}

:global(.dark) .glow-1 {
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.1), transparent 70%);
}

:global(.dark) .glow-2 {
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.05), transparent 70%);
}

:global(.dark) .glow-3 {
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.04), transparent 70%);
}

:global(.dark) .login-card {
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.2),
    0 8px 32px rgba(0, 0, 0, 0.15),
    0 0 0 1px oklch(0.79 0.18 145 / 0.03);
}

:global(.dark) .login-card:hover {
  box-shadow:
    0 2px 6px rgba(0, 0, 0, 0.25),
    0 12px 40px rgba(0, 0, 0, 0.2),
    0 0 0 1px oklch(0.79 0.18 145 / 0.08);
}

:global(.dark) .logo-icon {
  background: oklch(0.79 0.18 145 / 0.08);
  box-shadow:
    0 0 20px oklch(0.79 0.18 145 / 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

:global(.dark) .input-field {
  background: oklch(0.21 0.01 260 / 0.6) !important;
}

:global(.dark) .input-field:focus {
  box-shadow:
    0 0 0 3px oklch(0.79 0.18 145 / 0.06),
    0 0 20px oklch(0.79 0.18 145 / 0.03) !important;
}

:global(.dark) .card-shine {
  background: linear-gradient(
    90deg,
    transparent,
    oklch(0.79 0.18 145 / 0.2),
    transparent
  );
}
</style>
