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
