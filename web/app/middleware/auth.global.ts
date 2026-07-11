import { readUsersMeApiV1UsersMeGet } from '~/api/users'
import { getSystemStatusApiV1SystemStatusGet } from '~/api/system'

/**
 * 全局路由守卫
 * - /setup 页面始终允许访问（系统初始化引导）
 * - 系统未初始化时，所有其他路由强制跳转到 /setup
 * - 访问 /login 时若已登录则跳转首页
 * - 访问其他页面时通过 API 检查认证状态
 */
export default defineNuxtRouteMiddleware(async (to) => {
  // 初始化引导页面无需认证
  if (to.path === '/setup') {
    return
  }

  // SSR/SSG 预渲染阶段无后端可用，跳过所有 API 调用，交给客户端判断
  if (import.meta.server) return

  // 检查系统是否已初始化，未初始化则跳转引导页
  try {
    const statusRes = await getSystemStatusApiV1SystemStatusGet({ skipErrorHandler: true })
    if (statusRes.data && !statusRes.data.initialized) {
      return navigateTo('/setup')
    }
  } catch {
    // 网络错误等，继续后续认证检查
  }

  const { isAuthenticated, setToken, clearToken } = useAuth()

  if (to.path === '/login') {
    // 已登录用户访问登录页，跳转首页
    if (isAuthenticated.value) {
      return navigateTo('/')
    }
    return
  }

  // 如果已经通过之前的检查确认已登录，直接放行
  if (isAuthenticated.value) {
    return
  }

  // 通过 API 验证 Cookie 是否有效
  try {
    const res = await readUsersMeApiV1UsersMeGet({ skipErrorHandler: true })
    if (res.data?.username) {
      setToken('authenticated')
      return
    }
  } catch {
    // 认证失败，继续重定向
  }

  // 未登录，清除状态并跳转登录页
  clearToken()
  return navigateTo('/login')
})
