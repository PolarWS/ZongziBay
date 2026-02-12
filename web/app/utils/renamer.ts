/**
 * 智能媒体文件重命名
 *
 * 命名规则：
 *   电影：  名称 (年份)/名称 (年份).ext
 *   剧集/番剧：名称/Season XX/名称 SXXEXX.ext
 *
 * - 名称与年份来自 TMDB（通过 query 参数传入）
 * - 季与集从文件名 / 文件夹路径中推断
 */

// ─── 类型定义 ─────────────────────────────────────────────────

export type MediaType = 'movie' | 'tv' | 'anime' | 'default'

export interface RenameFile {
  name: string
  path: string
  size: number
  newName: string
  checked: boolean
}

// ─── 常量 ─────────────────────────────────────────────────────

const VIDEO_EXTS = new Set([
  '.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv',
  '.m4v', '.webm', '.ts', '.rmvb', '.mpg', '.mpeg',
])

const SUB_EXTS = new Set([
  '.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx',
])

const MEDIA_EXTS = new Set([...VIDEO_EXTS, ...SUB_EXTS])

/** 常见分辨率数值，不应被当作集数 */
const RESOLUTION_NUMBERS = new Set([240, 360, 480, 720, 1080, 1440, 2160])

/** 中文数字单字 → 数值（仅 零～九） */
const CN_DIGIT: Record<string, number> = {
  '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
  '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}

/** 正片以外的内容类型：PV/Menu/NCOP/NCED 等，用于生成文件名后缀 */
const EXTRA_TYPE_REGEX = /\[(?:PV\d*|Menu|NCOP|NCED|SP\d*|CM|Trailer|Preview|OP\d*|ED\d*|OVA|OAD)\]/gi

/** 字幕语言常见标记 → 统一缩写（用于多语言字幕区分文件名） */
const SUB_LANG_MAP: Record<string, string> = {
  'CHT': 'CHT', 'TC': 'CHT', '繁中': 'CHT', '繁体': 'CHT', 'BIG5': 'CHT',
  'CHS': 'CHS', 'SC': 'CHS', '简中': 'CHS', '简体': 'CHS', 'GB': 'CHS',
  'JP': 'JP', '日': 'JP', '日文': 'JP', 'JPN': 'JP',
  'EN': 'EN', '英': 'EN', '英文': 'EN', 'ENG': 'EN',
  'KO': 'KO', '韩': 'KO', '韩文': 'KO', 'KOR': 'KO',
}
/** 复合语言码（.JPSC.ass / .JPTC.ass 等）→ 拆成 "A+B" 便于统一展示 */
const SUB_LANG_COMPOUND: Record<string, string> = {
  'JPSC': 'JP+CHS', 'JPTC': 'JP+CHT', 'SCJP': 'CHS+JP', 'TCJP': 'CHT+JP',
  'CHTEN': 'CHT+EN', 'CHSEN': 'CHS+EN', 'ENCHT': 'EN+CHT', 'ENCHS': 'EN+CHS',
  'JPEN': 'JP+EN', 'ENJP': 'EN+JP', 'KOJP': 'KO+JP', 'JPKO': 'JP+KO',
}
const SUB_LANG_REGEX = /\[([A-Za-z\u4e00-\u9fa5]{2,6}(?:\+[A-Za-z\u4e00-\u9fa5]{2,6})*)\]|\.(cht|chs|sc|tc|jp|jpn|en|eng|ko|kor|jpsc|jptc|scjp|tcjp)\b/gi

// ─── 工具函数 ─────────────────────────────────────────────────

/** 提取文件扩展名（小写、带点号） */
export function getExt(filename: string): string {
  const m = filename.match(/(\.[a-zA-Z0-9]+)$/)
  return m && m[1] ? m[1].toLowerCase() : ''
}

/** 数字补零至少两位 */
function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

/** 判断扩展名是否为媒体文件（视频/字幕） */
function isMediaFile(ext: string): boolean {
  return MEDIA_EXTS.has(ext)
}

/** 从正则捕获组安全解析整数（组缺失时返回 NaN） */
function safeParseInt(group: string | undefined): number {
  return parseInt(group ?? '', 10)
}

/**
 * 将中文数字字符串解析为整数，支持 十、百、千、万。
 * 例如：一、十、十一、二十、九十九、一百、一百零一、一千二百、一万。
 */
function parseCnNumber(s: string): number | null {
  const raw = (s ?? '').trim()
  if (!raw) return null
  const n = parseInt(raw, 10)
  if (!isNaN(n)) return n
  if (!/^[零一二三四五六七八九十百千万]+$/.test(raw)) return null
  let current = 0
  let segment = 0
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i]!
    if (c === '零') {
      segment = 0
      continue
    }
    const d = CN_DIGIT[c]
    if (d !== undefined) {
      segment = d
      continue
    }
    if (c === '十') {
      current += (segment || 1) * 10
      segment = 0
      continue
    }
    if (c === '百') {
      current += (segment || 1) * 100
      segment = 0
      continue
    }
    if (c === '千') {
      current += (segment || 1) * 1000
      segment = 0
      continue
    }
    if (c === '万') {
      current += (segment || 1) * 10000
      segment = 0
      continue
    }
  }
  current += segment
  return current
}

// ─── 季 / 集解析 ───────────────────────────────────────────────

interface SEInfo {
  season: number
  episode: number
}

/**
 * 从文本中解析季数。
 * 按优先级尝试多种常见格式。
 */
function parseSeason(text: string): number | null {
  let m: RegExpMatchArray | null
  let n: number

  // 1. 标准：S01 或 S01E01
  m = text.match(/S(\d+)/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 2. 备选：1x01
  m = text.match(/(\d+)x\d+/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 3. 中文：第X季（中文数字，支持十百千万）
  m = text.match(/第([零一二三四五六七八九十百千万]+)季/)
  if (m && m[1]) {
    const cn = parseCnNumber(m[1])
    if (cn !== null) return cn
  }

  // 4. 中文：第X季（阿拉伯数字）
  m = text.match(/第(\d+)季/)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 5. 文件夹风格：Season 01 / Season01
  m = text.match(/Season\s*(\d+)/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  return null
}

/**
 * 从文本中解析集数。
 * 按优先级尝试多种常见格式。
 */
function parseEpisode(text: string): number | null {
  let m: RegExpMatchArray | null
  let n: number

  // 1. 标准：S01E01
  m = text.match(/S\d+E(\d+)/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 2. 备选：1x01
  m = text.match(/\d+x(\d+)/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 3. 中文：第XX话 / 第XX集 / 第XX話（数字或中文数字）
  m = text.match(/第(\d+)[话集話]/)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }
  m = text.match(/第([零一二三四五六七八九十百千万]+)[话集話]/)
  if (m && m[1]) {
    const cn = parseCnNumber(m[1])
    if (cn !== null) return cn
  }

  // 4. 独立 EP01 / E01（非 SxxExx 的一部分）
  m = text.match(/(?<![Ss]\d{1,4})\bEP?\.?(\d+)\b/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 5. 动漫短横线风格：" - 01" 后接空格/方括号/圆括号/v/结尾，如 "[Group] Title - 01 [1080p].mkv"
  m = text.match(/\s-\s(\d+)\s*(?:[\[\(v]|$)/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 6. 动漫短横线风格（宽松）：" - 01." 紧接扩展名前
  m = text.match(/\s-\s(\d+)\./i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 7. 方括号集数 [01]，排除分辨率与年份，如 "[One Piece][1100][1080P]" 中 1100 为集数
  const brackets = [...text.matchAll(/\[(\d{1,4})\]/g)]
  for (const bm of brackets) {
    const num = safeParseInt(bm[1])
    if (isNaN(num)) continue
    if (RESOLUTION_NUMBERS.has(num)) continue
    if (num >= 1900 && num <= 2099) continue
    if (num >= 1920) continue
    return num
  }

  return null
}

/** 判断是否为 OVA / 特别篇 / OAD */
function isSpecial(text: string): boolean {
  return /\b(OVA|OAD|SP|Special|SPECIAL|特别篇|特別篇)\b/i.test(text)
}

/**
 * 从文件名（及可选的文件夹路径）解析季与集。
 *
 * 优先级：
 *   1. 先从文件夹路径取季，再从文件名取
 *   2. 集始终从文件名取
 *   3. 若有集无季 → 默认 Season 01（OVA/特别篇为 Season 00）
 *   4. 二者都未解析到则返回 null
 */
function parseSeasonEpisode(filename: string, folderPath?: string): SEInfo | null {
  let season: number | null = folderPath ? parseSeason(folderPath) : null

  if (season === null) {
    season = parseSeason(filename)
  }

  const episode = parseEpisode(filename)

  if (episode !== null && season === null) {
    season = isSpecial(filename) ? 0 : 1
  }

  if (season !== null && episode !== null) {
    return { season, episode }
  }

  return null
}

// ─── 正片外类型与字幕语言 ───────────────────────────────────────

/**
 * 从文件名中提取「非正片」类型（PV/Menu/NCOP 等），返回用于文件名的后缀，如 " - PV01"、" - Menu"。
 * 正片返回空字符串。
 */
function getExtraType(filename: string): string {
  const m = filename.match(EXTRA_TYPE_REGEX)
  if (!m || m.length === 0) return ''
  // 取第一个匹配并统一格式：去掉方括号，PV 保留数字
  const raw = m[0].replace(/^\[|\]$/g, '')
  const normalized = raw.replace(/^PV$/i, 'PV') // PV → PV，PV01 保持
  return ` - ${normalized}`
}

/**
 * 从文件名中提取字幕语言标记，归一化为 " - CHT"、" - CHS+JP" 等形式，便于多语言字幕不重名。
 * 非字幕文件或未识别语言时返回空字符串。
 */
function getSubtitleLanguageSuffix(filename: string, ext: string): string {
  if (!SUB_EXTS.has(ext)) return ''
  const lower = filename.toLowerCase()
  const parts: string[] = []
  const add = (key: string) => {
    const k = key.replace(/\./g, '').trim()
    if (!k) return
    const upper = k.toUpperCase()
    const compound = SUB_LANG_COMPOUND[upper]
    if (compound) {
      compound.split('+').forEach((p) => add(p))
      return
    }
    const normalized = SUB_LANG_MAP[k] ?? SUB_LANG_MAP[k.toLowerCase()] ?? SUB_LANG_MAP[upper] ?? (k.length <= 4 ? upper : '')
    if (normalized && !parts.includes(normalized)) parts.push(normalized)
  }
  let match: RegExpExecArray | null
  SUB_LANG_REGEX.lastIndex = 0
  while ((match = SUB_LANG_REGEX.exec(filename)) !== null) {
    const token = (match[1] || match[2] || '').trim()
    if (!token) continue
    if (token.includes('+')) {
      token.split('+').forEach((s) => add(s.trim()))
    } else {
      add(token)
    }
  }
  // 单独匹配 .语言码.字幕扩展名（如 .JPSC.ass / .JPTC.ass）
  const compoundBeforeExt = filename.match(/\.([A-Z]{2,6})\.(ass|srt|ssa|vtt|sub|idx)$/i)
  if (compoundBeforeExt?.[1]) add(compoundBeforeExt[1])
  const dotLang = lower.match(/\.(cht|chs|sc|tc|jp|jpn|en|eng|ko|kor)(?:\.|$)/)
  if (dotLang?.[1]) add(dotLang[1])
  if (parts.length === 0) return ''
  return ` - ${parts.join('+')}`
}

// ─── 年份提取 ───────────────────────────────────────────────────

/**
 * 从文件名中尝试提取四位年份。
 * 匹配 ".2023."、"(2023)"、"[2023]"、" 2023 " 等，仅接受 1900–2099。
 */
export function parseYearFromFilename(filename: string): string {
  const m = filename.match(/(?:^|[\.\s\-_\(\[\{])(\d{4})(?:[\.\s\-_\)\]\}]|$)/)
  if (m && m[1]) {
    const y = parseInt(m[1], 10)
    if (y >= 1900 && y <= 2099) return m[1]
  }
  return ''
}

/**
 * 从文件列表中任意文件尝试提取年份。
 * 遍历所有文件名与路径，返回第一个有效年份。
 */
export function extractYearFromFiles(files: RenameFile[]): string {
  for (const file of files) {
    const text = `${file.path || ''} ${file.name || ''}`
    const year = parseYearFromFilename(text)
    if (year) return year
  }
  return ''
}

// ─── 主重命名逻辑 ────────────────────────────────────────────────

/**
 * 根据媒体类型与 TMDB 元数据对文件进行智能重命名。
 * 直接修改各 file.newName。
 *
 * @param files    - 文件列表（会改写 newName）
 * @param type     - 'movie' | 'tv' | 'anime' | 'default'
 * @param tmdbName - TMDB 中文名
 * @param tmdbYear - 上映年份（仅电影使用）
 */
export function performSmartRename(
  files: RenameFile[],
  type: MediaType,
  tmdbName: string,
  tmdbYear?: string,
): void {
  if (!tmdbName) return

  const name = tmdbName.trim()
  const year = tmdbYear?.trim() || ''

  for (const file of files) {
    const originalName = file.name || file.path || ''
    const ext = getExt(originalName)

    // 仅对媒体文件（视频+字幕）重命名
    if (!isMediaFile(ext)) continue

    // 从文件完整路径中拆出文件夹路径
    const pathParts = (file.path || '').replace(/\\/g, '/').split('/')
    const folderPath = pathParts.length > 1
      ? pathParts.slice(0, -1).join('/')
      : ''

    if (type === 'movie') {
      // ─── Movie: 名称 (年份)/名称 (年份)[ - PV01][ - 字幕语言].ext ───
      const label = year ? `${name} (${year})` : name
      const extra = getExtraType(originalName)
      const subSuffix = getSubtitleLanguageSuffix(originalName, ext)
      file.newName = `${label}/${label}${extra}${subSuffix}${ext}`
    } else if (type === 'tv' || type === 'anime') {
      // ─── TV / Anime: 名称/Season XX/名称 SXXEXX[ - PV].ext ───
      const se = parseSeasonEpisode(originalName, folderPath)
      const extra = getExtraType(originalName)
      const subSuffix = getSubtitleLanguageSuffix(originalName, ext)
      if (se) {
        const ss = pad2(se.season)
        const ee = pad2(se.episode)
        // 文件夹：季不补零（Season 5）；文件名：保持 S05E01
        file.newName = `${name}/Season ${se.season}/${name} S${ss}E${ee}${extra}${subSuffix}${ext}`
      } else {
        file.newName = `${name}/${originalName}`
      }
    } else {
      // 默认：仅放入名称文件夹下
      file.newName = `${name}/${originalName}`
    }
  }
}
