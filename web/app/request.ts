import Axios from 'axios'
import type { AxiosRequestConfig, AxiosResponse } from 'axios'

// 扩展 AxiosRequestConfig 类型以支持自定义选项
declare module 'axios' {
  export interface AxiosRequestConfig {
    skipErrorHandler?: boolean
  }
}

const client = Axios.create({
  baseURL: import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''),
  withCredentials: true,  // 发送 httpOnly Cookie 认证
})

// ===== 刷新 Token 的互斥锁，防止并发刷新 =====
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: any) => void
}> = []

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

// ===== 请求拦截器：不再需要手动附加 Token（Cookie 自动发送） =====
client.interceptors.request.use((config) => {
  return config
})

// ===== 响应拦截器：处理 401 自动刷新 =====
client.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    const originalRequest = error.config

    // 如果是 401 且还没重试过，尝试刷新 Token
    if (error.response?.data?.code === 40100 && !originalRequest._retry) {
      // 排除刷新接口自身和登录接口
      if (originalRequest.url?.includes('/users/refresh') || originalRequest.url?.includes('/users/login')) {
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // 正在刷新中，将请求加入队列等待
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then(() => {
            return client(originalRequest)
          })
          .catch((err) => {
            return Promise.reject(err)
          })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // 调用 /api/v1/users/refresh 刷新 Token
        const refreshRes = await Axios.post(
          `${client.defaults.baseURL}/api/v1/users/refresh`,
          {},
          { withCredentials: true }
        )

        if (refreshRes.data?.data?.access_token) {
          processQueue(null)
          return client(originalRequest)
        }

        // 刷新失败，清除状态并跳转登录页
        processQueue(new Error('Refresh failed'))
        await clearAuthAndRedirect()
        return Promise.reject(new Error('凭证已过期，请重新登录'))
      } catch (refreshError: any) {
        processQueue(refreshError)
        await clearAuthAndRedirect()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // 非 401 错误的处理
    if (error.config?.skipErrorHandler) {
      return Promise.reject(error)
    }
    return Promise.reject(error)
  }
)

async function clearAuthAndRedirect() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('auth_checked')
  const path = window.location.pathname
  if (path === '/login' || path === '/setup') return

  // 系统未初始化时跳转到引导页，否则跳登录页
  try {
    const res = await Axios.get(`${client.defaults.baseURL}/api/v1/system/status`, {
      withCredentials: true,
    } as any)
    if (res.data?.data && !res.data.data.initialized) {
      window.location.href = '/setup'
      return
    }
  } catch { /* 状态检查失败，跳登录页兜底 */ }
  window.location.href = '/login'
}

export default async function request<T = any>(url: string, options: AxiosRequestConfig): Promise<T> {
  const res: AxiosResponse<T> = await client.request({ url, ...options })
  const payload: any = res.data as any
  if (payload && typeof payload === 'object' && 'code' in payload && payload.code !== 200) {
    // ===== 未登录 (40100)：清除状态并跳转登录页 =====
    if (payload.code === 40100) {
      await clearAuthAndRedirect()
      throw new Error(payload.message || '请先登录')
    }
    // 如果配置了 skipErrorHandler，则不显示全局错误提示
    if (options.skipErrorHandler) {
      throw new Error(payload.message || 'Request failed')
    }
    throw new Error(payload.message || 'Request failed')
  }
  return res.data
}
