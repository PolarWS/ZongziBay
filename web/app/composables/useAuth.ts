import { readUsersMeApiV1UsersMeGet } from '~/api/users'

/**
 * 认证状态管理组合式函数
 * - JWT Token 通过 httpOnly Cookie 传输（自动发送，JS 无法读取）
 * - localStorage 仅存储登录状态标记，用于前端路由守卫的快速判断
 * - 实际认证有效性由服务端 Cookie 决定
 */
export const useAuth = () => {
  const token = useState<string | null>('auth-token', () => {
    return localStorage.getItem('access_token')
  })

  const authChecked = useState<boolean>('auth-checked', () => {
    return localStorage.getItem('auth_checked') === 'true'
  })

  /** 当前是否已登录（基于服务端初始化检查或 localStorage 标记） */
  const isAuthenticated = computed(() => !!token.value)

  /** 保存 Token（同步更新 state 和 localStorage） */
  const setToken = (newToken: string) => {
    token.value = newToken
    authChecked.value = true
    localStorage.setItem('access_token', newToken)
    localStorage.setItem('auth_checked', 'true')
  }

  /** 清除 Token（同步清除 state 和 localStorage） */
  const clearToken = () => {
    token.value = null
    authChecked.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('auth_checked')
  }

  /** 初始化：通过 API 检查认证状态，确定服务端 Cookie 是否有效 */
  const initAuth = async () => {
    try {
      const res = await readUsersMeApiV1UsersMeGet({ skipErrorHandler: true })
      if (res.data?.username) {
        token.value = 'authenticated'
        authChecked.value = true
        localStorage.setItem('access_token', 'authenticated')
        localStorage.setItem('auth_checked', 'true')
        return true
      }
    } catch {
      // 检查失败，清除状态
    }
    clearToken()
    return false
  }

  /** 退出登录 */
  const logout = async () => {
    clearToken()
    try {
      // 调用服务端 logout 清除 Cookie
      await $fetch('/api/v1/users/logout', {
        method: 'POST',
        credentials: 'include',
      })
    } catch {
      // 忽略网络错误，前端已清除状态
    }
    await navigateTo('/login')
  }

  return { token, authChecked, isAuthenticated, setToken, clearToken, logout, initAuth }
}
