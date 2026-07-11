import { getPreferencesApiV1SystemPreferencesGet, savePreferencesApiV1SystemPreferencesPut } from '@/api/system'

// 模块级全局共享状态，所有组件共用同一个 ref，一处修改处处响应
// 默认不显示，等 API 确认开启后才显示，避免关闭状态下的"闪现"
const showZongzibayChan = ref(false)
let initialized = false

export function useZongzibayChan() {
  const init = async () => {
    if (initialized) return
    initialized = true
    try {
      const pref = await getPreferencesApiV1SystemPreferencesGet({ skipErrorHandler: true })
      // 只有接口明确表示要显示时才显示，否则继续隐藏
      if (pref.data?.show_zongzibay_chan) showZongzibayChan.value = true
    } catch { /* 接口失败保持隐藏 */ }
  }

  const setShowChan = async (v: boolean) => {
    showZongzibayChan.value = v
    try {
      await savePreferencesApiV1SystemPreferencesPut({ show_zongzibay_chan: v }, { skipErrorHandler: true })
    } catch { /* ignore */ }
  }

  return {
    showZongzibayChan,
    init,
    setShowChan,
  }
}
