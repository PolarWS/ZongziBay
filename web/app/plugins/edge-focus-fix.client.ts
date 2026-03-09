/**
 * 修复 Edge 浏览器在页面隐藏（最小化）时调用 history.replaceState 会导致疯狂聚焦的问题。
 * 参考：https://blog.csdn.net/u012961419/article/details/157805074
 */
export default defineNuxtPlugin(() => {
  if (!import.meta.client) return

  const isEdge = /Edg\//.test(window.navigator.userAgent)
  if (!isEdge) return

  const originalReplaceState = window.history.replaceState
  window.history.replaceState = function (state, title, url) {
    if (document.visibilityState === 'hidden') {
      return
    }
    return originalReplaceState.apply(this, [state, title, url])
  }

  const originalPushState = window.history.pushState
  window.history.pushState = function (state, title, url) {
    if (document.visibilityState === 'hidden') {
      return
    }
    return originalPushState.apply(this, [state, title, url])
  }
})
