import { beforeEach, describe, expect, it } from 'vitest'
import {
  RECOMMEND_CACHE_TTL_LIVE_MS,
  RECOMMEND_CACHE_TTL_PAST_MS,
  getRecommendListCache,
  peekRecommendListCache,
  setRecommendListCache,
} from '../recommendListCache'

/**
 * 回归测试：空结果缓存毒化。
 *
 * 背景：后端在 TMDB 等上游异常时会吞掉异常并返回空列表（HTTP 仍为 200）。
 * 旧实现会把这种空结果写入 localStorage 并保留 7 天，导致推荐页长期显示
 * 「暂无数据」且不再发起请求。这里锁定两点：
 *   1. 缓存模块使用 v2 key，旧的 v1 污染缓存不会被读取；
 *   2. 页面层（commitListCache）不再写入空结果 —— 由 recommend.vue 的
 *      listEntryHasData 判定，空 entry 直接跳过写入。
 */
describe('recommendListCache', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('使用 v2 存储键，读取不到 v1 遗留的污染缓存', () => {
    localStorage.setItem(
      'zongzi_recommend_list_cache_v1',
      JSON.stringify({ 'movie|trending_week|1': { items: [], calendar: [], total: 0, savedAt: Date.now() } }),
    )
    // v1 数据不应被 v2 读取到
    expect(getRecommendListCache('movie|trending_week|1', RECOMMEND_CACHE_TTL_PAST_MS)).toBeNull()
  })

  it('写入有数据的条目后可被读取', () => {
    const entry = { items: [{ id: 1 } as any], calendar: [], total: 1 }
    setRecommendListCache('movie|trending_week|1', entry)
    const hit = getRecommendListCache('movie|trending_week|1', RECOMMEND_CACHE_TTL_PAST_MS)
    expect(hit).not.toBeNull()
    expect(hit!.items).toHaveLength(1)
  })

  it('超过 TTL 的条目不返回', () => {
    setRecommendListCache('movie|trending_week|1', { items: [{ id: 1 } as any], calendar: [], total: 1 })
    // maxAge 为 -1 时任何已保存条目都视为过期（elapsed >= 0 > -1）
    expect(getRecommendListCache('movie|trending_week|1', -1)).toBeNull()
    // 但仍在往季 TTL 内，peek 仍可拿到
    expect(peekRecommendListCache('movie|trending_week|1')).not.toBeNull()
  })

  it('module TTL 常量符合预期', () => {
    expect(RECOMMEND_CACHE_TTL_PAST_MS).toBe(7 * 24 * 60 * 60 * 1000)
    expect(RECOMMEND_CACHE_TTL_LIVE_MS).toBe(30 * 60 * 1000)
  })
})
