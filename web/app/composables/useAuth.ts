/**
 * 认证状态管理组合式函数
 * 管理 JWT Token 的存取与登录状态
 */
export const useAuth = () => {
  const token = useState<string | null>('auth-token', () => {
    return localStorage.getItem('access_token')
  })

  /** 当前是否已登录 */
  const isAuthenticated = computed(() => !!token.value)

  /** 保存 Token（同步更新 state 和 localStorage） */
  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('access_token', newToken)
  }

  /** 清除 Token（同步清除 state 和 localStorage） */
  const clearToken = () => {
    token.value = null
    localStorage.removeItem('access_token')
  }

  /** 退出登录 */
  const logout = async () => {
    clearToken()
    await navigateTo('/login')
  }

  return { token, isAuthenticated, setToken, clearToken, logout }
}
