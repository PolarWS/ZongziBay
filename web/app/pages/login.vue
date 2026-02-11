<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, Lock } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import api from '@/api'

definePageMeta({
  layout: false,
})

const { setToken } = useAuth()

const username = ref('')
const password = ref('')
const loading = ref(false)

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
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- 背景装饰 -->
    <div class="login-bg">
      <div class="grid-overlay" />
      <div class="glow glow-1" />
      <div class="glow glow-2" />
      <div class="glow glow-3" />
    </div>

    <!-- 内容 -->
    <div class="relative z-10 w-full max-w-[400px] mx-auto px-6">
      <!-- Logo 区域 -->
      <div class="text-center mb-10">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 mb-5 shadow-[0_0_30px_rgba(0,220,130,0.15)]">
          <Lock class="w-7 h-7 text-primary" />
        </div>
        <h1 class="text-3xl font-bold tracking-tight text-foreground">
          欢迎回来
        </h1>
        <p class="text-muted-foreground mt-2 text-[15px]">
          登录 <span class="text-primary font-semibold">粽子湾</span> 以继续使用
        </p>
      </div>

      <!-- 登录卡片 -->
      <div class="login-card">
        <div class="space-y-5">
          <div class="space-y-2">
            <Label for="username" class="text-sm font-medium text-foreground/80">用户名</Label>
            <Input
              id="username"
              v-model="username"
              placeholder="请输入用户名"
              autocomplete="username"
              class="h-11 bg-background/50 border-border/60 focus-visible:border-primary/50 focus-visible:ring-primary/20 transition-all duration-200"
              @keyup.enter="handleLogin"
            />
          </div>
          <div class="space-y-2">
            <Label for="password" class="text-sm font-medium text-foreground/80">密码</Label>
            <Input
              id="password"
              v-model="password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              class="h-11 bg-background/50 border-border/60 focus-visible:border-primary/50 focus-visible:ring-primary/20 transition-all duration-200"
              @keyup.enter="handleLogin"
            />
          </div>
        </div>

        <Button
          class="w-full h-11 mt-6 text-[15px] font-medium rounded-lg shadow-[0_2px_10px_rgba(0,220,130,0.25)] hover:shadow-[0_4px_20px_rgba(0,220,130,0.35)] transition-all duration-300"
          :disabled="loading"
          @click="handleLogin"
        >
          <Loader2 v-if="loading" class="w-4 h-4 mr-2 animate-spin" />
          {{ loading ? '登录中...' : '登录' }}
        </Button>
      </div>

      <!-- 底部 -->
      <p class="text-center text-xs text-muted-foreground/60 mt-8 tracking-wide">
        ZongziBay {{ new Date().getFullYear() }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: var(--background);
}

/* 背景层 */
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
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.15), transparent 70%);
  top: -10%;
  left: 50%;
  transform: translateX(-50%);
  animation: float-1 8s ease-in-out infinite;
}

.glow-2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.08), transparent 70%);
  bottom: 10%;
  left: -5%;
  animation: float-2 10s ease-in-out infinite;
}

.glow-3 {
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, oklch(0.79 0.18 145 / 0.06), transparent 70%);
  top: 40%;
  right: -5%;
  animation: float-3 12s ease-in-out infinite;
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

/* 登录卡片 */
.login-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 28px;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.04),
    0 6px 24px rgba(0, 0, 0, 0.03);
  backdrop-filter: blur(10px);
  transition: box-shadow 0.3s ease;
}

.login-card:hover {
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.04),
    0 8px 32px rgba(0, 0, 0, 0.06);
}

/* Dark mode 适配 */
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
    0 6px 24px rgba(0, 0, 0, 0.15);
}
</style>
