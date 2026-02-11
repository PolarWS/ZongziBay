/**
 * 全局路由守卫：未登录时自动跳转登录页
 * - 访问 /login 时若已登录则跳转首页
 * - 访问其他页面时若未登录则跳转登录页
 */
export default defineNuxtRouteMiddleware((to) => {
  const token = localStorage.getItem('access_token')

  if (to.path === '/login') {
    // 已登录用户访问登录页，跳转首页
    if (token) {
      return navigateTo('/')
    }
    return
  }

  // 未登录，跳转登录页
  if (!token) {
    return navigateTo('/login')
  }
})
