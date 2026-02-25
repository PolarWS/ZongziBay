<script setup lang="ts">
import Sonner from '@/components/ui/sonner/Sonner.vue'

// 首屏即跟随系统/偏好主题（与 plugins/theme.client 一致，此处兜底）
if (import.meta.client) {
  const theme = localStorage.getItem('zongzi_theme') as 'light' | 'dark' | 'system' | null
  const root = document.documentElement
  if (theme === 'dark') root.classList.add('dark')
  else if (theme === 'light') root.classList.remove('dark')
  else {
    const dark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (dark) root.classList.add('dark')
    else root.classList.remove('dark')
  }
}
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <Sonner />
</template>
<style>
/* Chrome, Safari, Edge */
input[type="search"]::-webkit-search-cancel-button {
  -webkit-appearance: none;
  appearance: none;
  display: none;
}

/* Firefox */
input[type="search"]::-moz-search-clear-button {
  display: none;
}
</style>