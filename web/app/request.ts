import Axios from 'axios'
import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import { toast } from 'vue-sonner'

// 扩展 AxiosRequestConfig 类型以支持自定义选项
declare module 'axios' {
  export interface AxiosRequestConfig {
    skipErrorHandler?: boolean
  }
}

const client = Axios.create({
  baseURL: import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
})

// ===== 请求拦截器：自动附加 JWT Token =====
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ===== 响应拦截器：处理网络层错误 =====
client.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // 如果配置了 skipErrorHandler，则不显示全局错误提示
    if (error.config?.skipErrorHandler) {
      return Promise.reject(error)
    }
    const message = error.response?.data?.message || error.message || 'Request failed'
    toast.error(message)
    return Promise.reject(error)
  }
)

export default async function request<T = any>(url: string, options: AxiosRequestConfig): Promise<T> {
  const res: AxiosResponse<T> = await client.request({ url, ...options })
  const payload: any = res.data as any
  if (payload && typeof payload === 'object' && 'code' in payload && payload.code !== 200) {
    // ===== 未登录 (40100)：清除 Token 并跳转登录页 =====
    if (payload.code === 40100) {
      localStorage.removeItem('access_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      throw new Error(payload.message || '请先登录')
    }
    // 如果配置了 skipErrorHandler，则不显示全局错误提示
    if (options.skipErrorHandler) {
       throw new Error(payload.message || 'Request failed')
    }
    const message = payload.message || 'Request failed'
    toast.error(message)
    throw new Error(message)
  }
  return res.data
}
