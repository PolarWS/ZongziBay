import { getConfigApiV1SystemConfigGet } from '@/api/system'

/** TMDB 图片域名缓存（通过 useState 在页面间共享） */
const tmdbImageDomain = useState<string>('tmdb-image-domain', () => '')

/** 是否已加载过配置 */
const tmdbConfigLoaded = useState<boolean>('tmdb-config-loaded', () => false)

/** 默认 TMDB 图片域名 */
const DEFAULT_IMAGE_DOMAIN = 'https://image.tmdb.org'

/**
 * 获取 TMDB 图片基础 URL。
 * 从后端配置中读取 tmdb.image_domain，若未配置则使用默认 image.tmdb.org。
 */
export const useTmdbImage = () => {
  /** 初始化：从后端获取图片域名配置 */
  const loadImageDomain = async () => {
    if (tmdbConfigLoaded.value) return
    try {
      const res = await getConfigApiV1SystemConfigGet()
      const cfg = (res as any)?.data || {}
      const domain = cfg?.tmdb?.image_domain || DEFAULT_IMAGE_DOMAIN
      tmdbImageDomain.value = domain
      tmdbConfigLoaded.value = true
    } catch {
      tmdbImageDomain.value = DEFAULT_IMAGE_DOMAIN
      tmdbConfigLoaded.value = true
    }
  }

  /** 图片基础 URL，带宽度参数，如 https://image.tmdb.org/t/p/w300 */
  const imgBase = computed(() => {
    const domain = cleanDomain(tmdbImageDomain.value)
    return `https://${domain}/t/p/w300`
  })

  /** 根据宽度获取不同尺寸的图片 URL */
  const imgUrl = (path: string | null | undefined, width: string = 'w300') => {
    if (!path) return ''
    const domain = cleanDomain(tmdbImageDomain.value)
    return `https://${domain}/t/p/${width}${path}`
  }

  return { imgBase, imgUrl, loadImageDomain }
}

/** 清理域名：去协议前缀、去末尾 / */
function cleanDomain(domain: string): string {
  let d = domain || DEFAULT_IMAGE_DOMAIN
  if (d.startsWith('https://')) d = d.slice(8)
  else if (d.startsWith('http://')) d = d.slice(7)
  d = d.replace(/\/+$/, '')
  return d
}
