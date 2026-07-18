/** 推荐页列表持久缓存（localStorage），刷新页面后仍可命中 */

const STORAGE_KEY = 'zongzi_recommend_list_cache_v1'
const MAX_ENTRIES = 48
/** 往季等稳定列表：7 天 */
export const RECOMMEND_CACHE_TTL_PAST_MS = 7 * 24 * 60 * 60 * 1000
/** 当前季 / 本周：仍可读缓存做秒开，但超过 30 分钟视为过期需刷新 */
export const RECOMMEND_CACHE_TTL_LIVE_MS = 30 * 60 * 1000

export type RecommendListCacheEntry = {
  items: (API.TMDBMovie | API.TMDBTV)[]
  calendar: API.BangumiCalendarDay[]
  total: number
}

type StoredEntry = RecommendListCacheEntry & { savedAt: number }
type Store = Record<string, StoredEntry>

const memory = new Map<string, StoredEntry>()
let hydrated = false

function canUseStorage() {
  return typeof localStorage !== 'undefined'
}

function hydrate() {
  if (hydrated) return
  hydrated = true
  if (!canUseStorage()) return
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Store
    if (!parsed || typeof parsed !== 'object') return
    for (const [k, v] of Object.entries(parsed)) {
      if (v && typeof v.savedAt === 'number') memory.set(k, v)
    }
  } catch {
    // 损坏则清空
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }
}

function persist() {
  if (!canUseStorage()) return
  const obj: Store = {}
  for (const [k, v] of memory.entries()) obj[k] = v
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(obj))
  } catch {
    // 配额满：丢掉最旧一半再试
    const entries = [...memory.entries()].sort((a, b) => a[1].savedAt - b[1].savedAt)
    const drop = Math.ceil(entries.length / 2)
    for (let i = 0; i < drop; i++) memory.delete(entries[i]![0])
    try {
      const retry: Store = {}
      for (const [k, v] of memory.entries()) retry[k] = v
      localStorage.setItem(STORAGE_KEY, JSON.stringify(retry))
    } catch {
      // ignore
    }
  }
}

function pruneExpired(now = Date.now()) {
  for (const [k, v] of memory.entries()) {
    // 超过往季 TTL 一律删；live 更短 TTL 在读取时判断
    if (now - v.savedAt > RECOMMEND_CACHE_TTL_PAST_MS) memory.delete(k)
  }
  while (memory.size > MAX_ENTRIES) {
    let oldestKey: string | null = null
    let oldestAt = Infinity
    for (const [k, v] of memory.entries()) {
      if (v.savedAt < oldestAt) {
        oldestAt = v.savedAt
        oldestKey = k
      }
    }
    if (!oldestKey) break
    memory.delete(oldestKey)
  }
}

/** 读取缓存；maxAgeMs 内有效则返回，否则 null（数据仍可能留在存储里供 live 次开） */
export function getRecommendListCache(
  key: string,
  maxAgeMs: number,
): RecommendListCacheEntry | null {
  hydrate()
  const hit = memory.get(key)
  if (!hit) return null
  if (Date.now() - hit.savedAt > maxAgeMs) return null
  return { items: hit.items || [], calendar: hit.calendar || [], total: hit.total || 0 }
}

/** 读取任意未超往季 TTL 的缓存（用于当前季秒开后再刷新） */
export function peekRecommendListCache(key: string): RecommendListCacheEntry | null {
  return getRecommendListCache(key, RECOMMEND_CACHE_TTL_PAST_MS)
}

export function setRecommendListCache(key: string, entry: RecommendListCacheEntry) {
  hydrate()
  memory.set(key, {
    items: entry.items,
    calendar: entry.calendar,
    total: entry.total,
    savedAt: Date.now(),
  })
  pruneExpired()
  persist()
}
