/**
 * 应用启动时立即根据「设置」偏好或系统主题设置 html.dark，避免首屏不跟随系统颜色。
 */
function applyTheme() {
  if (typeof document === 'undefined') return
  const theme = localStorage.getItem('zongzi_theme') as 'light' | 'dark' | 'system' | null
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
  } else if (theme === 'light') {
    root.classList.remove('dark')
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (prefersDark) root.classList.add('dark')
    else root.classList.remove('dark')
  }
}

export default defineNuxtPlugin(() => {
  applyTheme()
})
