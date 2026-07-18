/**
 * 智能媒体文件重命名
 *
 * 命名规则：
 *   电影/剧场版：名称 (年份)/名称 (年份).ext
 *   剧集/番剧：  名称/Season XX/名称 SXXEXX.ext
 *
 * - 名称与年份来自 TMDB（通过 query 参数传入）
 * - 季与集从文件名 / 文件夹路径中推断
 * - 文件名中已有明确 SxxExx 时优先信任，不被文件夹路径覆盖
 * - 支持 Season 0（OVA/特别篇）、小数集号 (.5)、.sup 字幕、E0S01 格式
 * - Anime 类型下无 S/E 的文件自动按电影格式处理（剧场版）
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

// V2: 新增 .sup
const SUB_EXTS = new Set([
  '.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx', '.sup',
])

const MEDIA_EXTS = new Set([...VIDEO_EXTS, ...SUB_EXTS])

/** 常见分辨率数值，不应被当作集数 */
const RESOLUTION_NUMBERS = new Set([240, 360, 480, 720, 1080, 1440, 2160])

/** 季号合理范围（V2：支持 S0） */
const SEASON_MIN = 0
const SEASON_MAX = 99
/** 集数合理范围 */
const EPISODE_MAX = 999

/** 中文数字单字 → 数值（仅 零～九） */
const CN_DIGIT: Record<string, number> = {
  '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
  '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}

/** 正片以外的内容类型：PV/Menu/NCOP/NCED 等，用于生成文件名后缀 */
const EXTRA_TYPE_REGEX = /\[(?:PV\d*|Menu|NCOP|NCED|SP\d*|CM|Trailer|Preview|OP\d*|ED\d*|OVA|OAD)\]/gi

/** 字幕语言常见标记 → 统一缩写 */
const SUB_LANG_MAP: Record<string, string> = {
  'CHT': 'CHT', 'TC': 'CHT', '繁中': 'CHT', '繁体': 'CHT', 'BIG5': 'CHT',
  'CHS': 'CHS', 'SC': 'CHS', '简中': 'CHS', '简体': 'CHS', 'GB': 'CHS',
  'JP': 'JP', '日': 'JP', '日文': 'JP', 'JPN': 'JP',
  'EN': 'EN', '英': 'EN', '英文': 'EN', 'ENG': 'EN',
  'KO': 'KO', '韩': 'KO', '韩文': 'KO', 'KOR': 'KO',
}
/** 复合语言码 → 拆成 "A+B" */
const SUB_LANG_COMPOUND: Record<string, string> = {
  'JPSC': 'JP+CHS', 'JPTC': 'JP+CHT', 'SCJP': 'CHS+JP', 'TCJP': 'CHT+JP',
  'CHTEN': 'CHT+EN', 'CHSEN': 'CHS+EN', 'ENCHT': 'EN+CHT', 'ENCHS': 'EN+CHS',
  'JPEN': 'JP+EN', 'ENJP': 'EN+JP', 'KOJP': 'KO+JP', 'JPKO': 'JP+KO',
}

// V2: 已知字幕组名称，不当作语言码
const FANSUB_NAMES = new Set(['DMG', 'DMHY', 'KTXP', 'CASO', 'FLSNOW', 'POPGO', 'LKSUB', 'KNA', 'KISSSUB'])

const SUB_LANG_REGEX = /\[([A-Za-z一-龥]{2,6}(?:\+[A-Za-z一-龥]{2,6})*)\]|\.(cht|chs|sc|tc|jp|jpn|en|eng|ko|kor|jpsc|jptc|scjp|tcjp)\b/gi

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

/** 判断扩展名是否为媒体文件 */
function isMediaFile(ext: string): boolean {
  return MEDIA_EXTS.has(ext)
}

/** 从正则捕获组安全解析整数 */
function safeParseInt(group: string | undefined): number {
  return parseInt(group ?? '', 10)
}

/**
 * 将中文数字字符串解析为整数，支持 十、百、千、万。
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
 * 从文本中解析季数。V2: 支持 S0（Season 0）。
 */
function parseSeason(text: string): number | null {
  let m: RegExpMatchArray | null
  let n: number

  // 0. 补丁：中文「第X季」简写
  if (/第二季/.test(text)) return 2
  if (/第三季/.test(text)) return 3
  if (/第一季/.test(text)) return 1
  if (/第四季/.test(text)) return 4
  if (/第五季/.test(text)) return 5
  if (/第六季/.test(text)) return 6
  if (/第七季/.test(text)) return 7
  if (/第八季/.test(text)) return 8
  if (/第九季/.test(text)) return 9
  if (/第十季/.test(text)) return 10

  // 1. 标准：S01 或 S01E01（V2: >= SEASON_MIN 即 >= 0）
  m = text.match(/S(\d+)/i)
  if (m) {
    n = safeParseInt(m[1])
    if (n >= SEASON_MIN && n <= SEASON_MAX) return n
  }

  // 2. 备选：1x01
  m = text.match(/(\d+)x\d+/i)
  if (m) {
    n = safeParseInt(m[1])
    if (n >= SEASON_MIN && n <= SEASON_MAX) return n
  }

  // 3. V2 新增：E0S01 / E1S01 格式（E先于S）
  m = text.match(/E(\d+)S(\d+)/i)
  if (m) {
    n = safeParseInt(m[2])
    if (n >= SEASON_MIN && n <= SEASON_MAX) return n
  }

  // 4. 中文：第X季（中文数字）
  m = text.match(/第([零一二三四五六七八九十百千万]+)季/)
  if (m && m[1]) {
    const cn = parseCnNumber(m[1])
    if (cn !== null && cn >= SEASON_MIN && cn <= SEASON_MAX) return cn
  }

  // 5. 中文：第X季（阿拉伯数字）
  m = text.match(/第(\d+)季/)
  if (m) {
    n = safeParseInt(m[1])
    if (n >= SEASON_MIN && n <= SEASON_MAX) return n
  }

  // 6. 文件夹风格：Season 01 / Season01
  m = text.match(/Season\s*(\d+)/i)
  if (m) {
    n = safeParseInt(m[1])
    if (n >= SEASON_MIN && n <= SEASON_MAX) return n
  }

  return null
}

/**
 * 从文本中解析集数。V2: 支持小数集号 (E18.5)，仅接受 .5 以避免分辨率误匹配。
 */
function parseEpisode(text: string): number | null {
  let m: RegExpMatchArray | null
  let n: number

  // 1. 标准：S01E01 / S01E18.5（V2: 仅 .5 小数集号，避免 E01.1080p 被误解析为 E1.108）
  m = text.match(/S(\d+)E(\d+(?:\.5)?)/i)
  if (m) {
    const s = safeParseInt(m[1])
    n = parseFloat(m[2] ?? '')
    if (s >= SEASON_MIN && s <= SEASON_MAX && n >= 1 && n <= EPISODE_MAX) return n
  }

  // 2. 备选：1x01
  m = text.match(/(\d+)x(\d+)/i)
  if (m) {
    const s = safeParseInt(m[1])
    n = safeParseInt(m[2])
    if (s >= SEASON_MIN && s <= SEASON_MAX && n >= 1 && n <= EPISODE_MAX) return n
  }

  // 3. V2 新增：E0S01 / E1S01 格式
  m = text.match(/E(\d+)S(\d+)/i)
  if (m) {
    n = safeParseInt(m[1])
    if (!isNaN(n) && n >= 1 && n <= EPISODE_MAX) return n
  }

  // 4. 中文：第XX话 / 第XX集 / 第XX話
  m = text.match(/第(\d+)[话集話]/)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }
  m = text.match(/第([零一二三四五六七八九十百千万]+)[话集話]/)
  if (m && m[1]) {
    const cn = parseCnNumber(m[1])
    if (cn !== null) return cn
  }

  // 5. 独立 EP01 / E01
  m = text.match(/(?<![Ss]\d{1,4})\bEP?\.?(\d+)\b/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 6. 动漫短横线风格：" - 01"
  m = text.match(/\s-\s(\d+)\s*(?:[\[\(v]|$)/i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 7. 动漫短横线风格（宽松）：" - 01."
  m = text.match(/\s-\s(\d+)\./i)
  if (m) { n = safeParseInt(m[1]); if (!isNaN(n)) return n }

  // 8. 方括号集数 [01]
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
 * V2 重写：从文件名（及可选的文件夹路径）解析季与集。
 *
 * 核心改动：
 *   → 文件名中已有明确 SxxExx 时，优先信任文件名季号，不再被文件夹覆盖
 *   → 支持 Season 0
 *   → 若无 S/E 且为 anime 类型，返回 null（后续按电影处理）
 */
function parseSeasonEpisode(filename: string, folderPath?: string): SEInfo | null {
  // ── V2 核心改动：文件名有 SxxExx 则直接采纳 ──
  const fileSE = filename.match(/S(\d+)E(\d+(?:\.5)?)/i)
  if (fileSE) {
    const s = safeParseInt(fileSE[1])
    const e = parseFloat(fileSE[2])
    if (s >= SEASON_MIN && s <= SEASON_MAX && e >= 1 && e <= EPISODE_MAX) {
      return { season: s, episode: e }
    }
  }

  // ── V2 新增：E0S01 / E1S01 格式 ──
  const eBeforeS = filename.match(/E(\d+)S(\d+)/i)
  if (eBeforeS) {
    const ep = safeParseInt(eBeforeS[1])
    const sn = safeParseInt(eBeforeS[2])
    if (sn >= SEASON_MIN && sn <= SEASON_MAX && ep >= 1 && ep <= EPISODE_MAX) {
      return { season: sn, episode: ep }
    }
  }

  // ── 文件名没有明确 S/E → 从文件夹推断季号 ──
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
 * 从文件名中提取「非正片」类型（PV/Menu/NCOP 等）。
 * V2: 扩展了总集篇、番外等。
 */
function getExtraType(filename: string): string {
  const m = filename.match(EXTRA_TYPE_REGEX)
  if (!m || m.length === 0) return ''
  const raw = m[0].replace(/^\[|\]$/g, '')
  const normalized = raw.replace(/^PV$/i, 'PV')
  return ` - ${normalized}`
}

/**
 * V2 增强：从文件名中提取字幕语言标记。
 * 改进：过滤已知字幕组名（DMG 等），避免误识别。
 */
function getSubtitleLanguageSuffix(filename: string, ext: string): string {
  if (!SUB_EXTS.has(ext)) return ''
  const lower = filename.toLowerCase()
  const parts: string[] = []
  const add = (key: string) => {
    const k = key.replace(/\./g, '').trim()
    if (!k) return
    const upper = k.toUpperCase()

    // V2: 过滤字幕组名
    if (FANSUB_NAMES.has(upper)) return

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
      // V2: 过滤 "DMG+CHS" 中的 "DMG"
      token.split('+').forEach((s) => {
        const t = s.trim()
        if (t && !FANSUB_NAMES.has(t.toUpperCase()) && !FANSUB_NAMES.has(t)) {
          add(t)
        }
      })
    } else {
      add(token)
    }
  }
  // 单独匹配 .语言码.字幕扩展名（如 .JPSC.ass / .JPTC.ass）
  const compoundBeforeExt = filename.match(/\.([A-Z]{2,6})\.(ass|srt|ssa|vtt|sub|idx|sup)$/i)
  if (compoundBeforeExt?.[1]) add(compoundBeforeExt[1])
  const dotLang = lower.match(/\.(cht|chs|sc|tc|jp|jpn|en|eng|ko|kor)(?:\.|$)/)
  if (dotLang?.[1]) add(dotLang[1])
  if (parts.length === 0) return ''
  return ` - ${parts.join('+')}`
}

// ─── 年份提取 ───────────────────────────────────────────────────

/**
 * 从文件名中尝试提取四位年份。
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

/** 智能重命名可用的占位符 */
export type RenameTemplates = { movie?: string; tv?: string; anime?: string }

/**
 * 会话级占位符覆盖（非空才生效）。
 */
export type RenameVarOverrides = {
  season?: string
  episode?: string
  extra?: string
  sub_suffix?: string
  ext?: string
}

/** 将模板中的 {key} 替换为 vars 中的对应值 */
export function applyTemplate(tpl: string, vars: Record<string, string>): string {
  let out = tpl
  for (const [key, value] of Object.entries(vars)) {
    out = out.replace(new RegExp(`\\{${key}\\}`, 'g'), value ?? '')
  }
  return out
}

/** 默认智能重命名模板 */
export const DEFAULT_RENAME_TEMPLATES: Required<RenameTemplates> = {
  movie: '{name} ({year})/{name} ({year}){extra}{sub_suffix}{ext}',
  tv: '{name}/Season {season}/{name} S{ss}E{ee}{extra}{sub_suffix}{ext}',
  anime: '{name}/Season {season}/{name} S{ss}E{ee}{extra}{sub_suffix}{ext}',
}

/**
 * V2 改进的智能重命名。
 *
 * 主要改动：
 *   1. 文件名 SxxExx 优先于文件夹季号
 *   2. 支持 Season 0
 *   3. Anime 无 S/E 时按电影处理（剧场版）
 *   4. 支持小数集号
 */
export function performSmartRename(
  files: RenameFile[],
  type: MediaType,
  tmdbName: string,
  tmdbYear?: string,
  templates?: RenameTemplates,
  overrides?: RenameVarOverrides,
): void {
  if (!tmdbName) return

  const name = tmdbName.trim()
  const year = tmdbYear?.trim() || ''
  const forceSeason = overrides?.season?.trim() || ''
  const forceEpisode = overrides?.episode?.trim() || ''
  const forceExtra = overrides?.extra
  const forceSubSuffix = overrides?.sub_suffix
  const forceExt = overrides?.ext?.trim() || ''

  const template = type !== 'default' ? templates?.[type] : undefined

  for (const file of files) {
    if (!file.checked) continue

    const originalName = file.name || file.path || ''
    const detectedExt = getExt(originalName)
    const ext = forceExt || detectedExt

    if (!isMediaFile(detectedExt)) continue

    const pathParts = (file.path || '').replace(/\\/g, '/').split('/')
    const folderPath = pathParts.length > 1
      ? pathParts.slice(0, -1).join('/')
      : ''

    const extra = forceExtra !== undefined && forceExtra !== ''
      ? forceExtra
      : getExtraType(originalName)
    const subSuffix = forceSubSuffix !== undefined && forceSubSuffix !== ''
      ? forceSubSuffix
      : getSubtitleLanguageSuffix(originalName, detectedExt)

    const resolveSeasonEpisode = (): { season: number; episode: number } | null => {
      if (forceSeason || forceEpisode) {
        const parsed = parseSeasonEpisode(originalName, folderPath)
        const season = forceSeason
          ? Number.parseInt(forceSeason, 10)
          : (parsed?.season ?? 1)
        const episode = forceEpisode
          ? Number.parseInt(forceEpisode, 10)
          : (parsed?.episode ?? 1)
        if (!Number.isFinite(season) || !Number.isFinite(episode)) return null
        return { season, episode }
      }
      return parseSeasonEpisode(originalName, folderPath)
    }

    if (template && (type === 'movie' || type === 'tv' || type === 'anime')) {
      const vars: Record<string, string> = {
        name,
        year,
        season: '',
        ss: '',
        episode: '',
        ee: '',
        extra,
        sub_suffix: subSuffix,
        ext,
      }
      if (type === 'movie') {
        file.newName = applyTemplate(template, vars)
        continue
      }
      const se = resolveSeasonEpisode()
      if (se) {
        vars.season = String(se.season)
        vars.ss = pad2(se.season)
        vars.episode = String(se.episode)
        // V2: 支持小数集号 — 小数部分直接拼接，不在补零
        vars.ee = Number.isInteger(se.episode)
          ? pad2(se.episode)
          : String(se.episode)
        file.newName = applyTemplate(template, vars)
      } else if (type === 'anime') {
        // ── V2 新增：anime 无 S/E → 按电影格式（剧场版）──
        const label = year ? `${name} (${year})` : name
        file.newName = `${label}/${label}${extra}${subSuffix}${ext}`
      } else {
        file.newName = `${name}/${originalName}`
      }
      continue
    }

    // 无自定义模板时使用内置格式
    if (type === 'movie') {
      const label = year ? `${name} (${year})` : name
      file.newName = `${label}/${label}${extra}${subSuffix}${ext}`
    } else if (type === 'tv' || type === 'anime') {
      const se = resolveSeasonEpisode()
      if (se) {
        const ss = pad2(se.season)
        const ee = Number.isInteger(se.episode)
          ? pad2(se.episode)
          : String(se.episode)
        file.newName = `${name}/Season ${se.season}/${name} S${ss}E${ee}${extra}${subSuffix}${ext}`
      } else if (type === 'anime') {
        // ── V2 新增：anime 无 S/E → 按电影格式（剧场版）──
        const label = year ? `${name} (${year})` : name
        file.newName = `${label}/${label}${extra}${subSuffix}${ext}`
      } else {
        file.newName = `${name}/${originalName}`
      }
    } else {
      file.newName = `${name}/${originalName}`
    }
  }
}
