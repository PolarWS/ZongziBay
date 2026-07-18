/**
 * 智能重命名 — 单元测试 + 流程测试
 *
 * 覆盖：
 *   getExt / parseYearFromFilename / extractYearFromFiles / applyTemplate
 *   performSmartRename：电影 / 剧集 / 番剧 各模式
 *   流程测试：真实种子文件列表 → 完整重命名管线
 */
import { describe, it, expect } from 'vitest'
import {
  getExt,
  parseYearFromFilename,
  extractYearFromFiles,
  applyTemplate,
  DEFAULT_RENAME_TEMPLATES,
  performSmartRename,
  type RenameFile,
  type MediaType,
} from '../renamer'

// ─── 辅助：构造 RenameFile ───────────────────────────────────────

function f(name: string, path?: string, checked = true, size = 1000): RenameFile {
  return { name, path: path ?? name, size, newName: '', checked }
}

// ─── getExt ──────────────────────────────────────────────────────

describe('getExt', () => {
  it('提取普通扩展名', () => {
    expect(getExt('video.mkv')).toBe('.mkv')
    expect(getExt('subtitle.srt')).toBe('.srt')
    expect(getExt('file.ass')).toBe('.ass')
  })

  it('转为小写', () => {
    expect(getExt('FILE.MKV')).toBe('.mkv')
    expect(getExt('File.SRT')).toBe('.srt')
  })

  it('无扩展名返回空字符串', () => {
    expect(getExt('noext')).toBe('')
    expect(getExt('')).toBe('')
  })

  it('多点号取最后一个', () => {
    expect(getExt('video.1080p.mkv')).toBe('.mkv')
    expect(getExt('Show.S01E01.ass')).toBe('.ass')
  })
})

// ─── parseYearFromFilename ───────────────────────────────────────

describe('parseYearFromFilename', () => {
  it('提取四位年份', () => {
    expect(parseYearFromFilename('Movie (2024).mkv')).toBe('2024')
    expect(parseYearFromFilename('Show.2023.S01.mkv')).toBe('2023')
  })

  it('忽略非年份数字', () => {
    expect(parseYearFromFilename('Show.1080p.mkv')).toBe('')
    expect(parseYearFromFilename('Show.S01E01.mkv')).toBe('')
  })

  it('空字符串返回空', () => {
    expect(parseYearFromFilename('')).toBe('')
  })
})

// ─── extractYearFromFiles ────────────────────────────────────────

describe('extractYearFromFiles', () => {
  it('从文件列表中提取年份', () => {
    const files = [
      f('Show.S01E01.mkv', '/dl/Show (2024) S01/Show.S01E01.mkv'),
    ]
    expect(extractYearFromFiles(files)).toBe('2024')
  })

  it('无年份返回空', () => {
    const files = [f('video.mkv', '/dl/video.mkv')]
    expect(extractYearFromFiles(files)).toBe('')
  })
})

// ─── applyTemplate ───────────────────────────────────────────────

describe('applyTemplate', () => {
  it('替换所有占位符', () => {
    const tpl = '{name} ({year})/{name} ({year}){ext}'
    const result = applyTemplate(tpl, { name: 'Inception', year: '2010', ext: '.mkv' })
    expect(result).toBe('Inception (2010)/Inception (2010).mkv')
  })

  it('缺少的占位符保留原样', () => {
    const tpl = '{name}{ext}'
    const result = applyTemplate(tpl, { name: 'Test' })
    expect(result).toBe('Test{ext}')
  })

  it('空值替换为空字符串', () => {
    expect(applyTemplate('{name}{year}', { name: 'A', year: '' })).toBe('A')
  })
})

// ==================================================================
//  performSmartRename 单元测试
// ==================================================================

// ─── 电影模式 ────────────────────────────────────────────────────

describe('performSmartRename - 电影', () => {
  it('基本命名：名称 (年份)/名称 (年份).ext', () => {
    const files = [f('video.mkv')]
    performSmartRename(files, 'movie', 'Inception', '2010')
    expect(files[0].newName).toBe('Inception (2010)/Inception (2010).mkv')
  })

  it('无年份时省略括号', () => {
    const files = [f('movie.mp4')]
    performSmartRename(files, 'movie', 'Fight Club')
    expect(files[0].newName).toBe('Fight Club/Fight Club.mp4')
  })

  it('电影字幕文件：加语言后缀', () => {
    const files = [f('movie.chs.srt', 'movie.chs.srt')]
    performSmartRename(files, 'movie', 'Inception', '2010')
    expect(files[0].newName).toContain('Inception (2010)')
    expect(files[0].newName).toContain('CHS')
    expect(files[0].newName).toContain('.srt')
  })

  it('unchecked 文件跳过', () => {
    const files = [f('video.mkv', undefined, false)]
    performSmartRename(files, 'movie', 'Test')
    expect(files[0].newName).toBe('')
  })

  it('非媒体文件跳过', () => {
    const files = [f('readme.txt')]
    performSmartRename(files, 'movie', 'Test')
    expect(files[0].newName).toBe('')
  })

  it('空 tmdbName 不处理', () => {
    const files = [f('video.mkv')]
    performSmartRename(files, 'movie', '')
    expect(files[0].newName).toBe('')
  })
})

// ─── 剧集模式 ────────────────────────────────────────────────────

describe('performSmartRename - 剧集 (TV)', () => {
  it('文件名有 SxxExx：优先采纳', () => {
    const files = [f('Show.S01E05.1080p.mkv')]
    performSmartRename(files, 'tv', 'Breaking Bad')
    expect(files[0].newName).toBe(
      'Breaking Bad/Season 1/Breaking Bad S01E05.mkv'
    )
  })

  it('文件夹 Season 信息被文件名 SxxExx 覆盖', () => {
    const files = [
      f('Show.S02E03.mkv', '/dl/Season 1/Show.S02E03.mkv'),
    ]
    performSmartRename(files, 'tv', 'Show Name')
    // 文件名 S02 优先于文件夹 Season 1
    expect(files[0].newName).toContain('Season 2')
    expect(files[0].newName).toContain('S02E03')
  })

  it('从文件夹推断季号（文件名无 S/E）', () => {
    const files = [
      f('Show - 05.mkv', '/dl/Season 3/Show - 05.mkv'),
    ]
    performSmartRename(files, 'tv', 'Stranger Things')
    expect(files[0].newName).toContain('Season 3')
    expect(files[0].newName).toContain('S03E05')
  })

  it('1x05 格式', () => {
    const files = [f('Show.1x05.mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('S01E05')
  })

  it('中文「第X集」', () => {
    const files = [f('Show.第05集.mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('S01E05')
  })

  it('中文「第X季」', () => {
    const files = [f('Show.第05集.mkv', '/dl/第二季/Show.第05集.mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('Season 2')
  })

  it('E0S01 格式（E 先于 S）', () => {
    const files = [f('Show.E05S02.mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('Season 2')
    expect(files[0].newName).toContain('S02E05')
  })

  it('Season 0 支持（OVA/特别篇）', () => {
    const files = [f('Show.S00E01.mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('Season 0')
    expect(files[0].newName).toContain('S00E01')
  })

  it('字幕文件：自身含 S/E 时正常匹配', () => {
    const files = [
      f('Show.S01E03.chs.srt', '/dl/Show.S01E03.chs.srt'),
    ]
    performSmartRename(files, 'tv', 'Show')
    // 字幕文件名包含 S01E03，直接被主逻辑解析
    expect(files[0].newName).toContain('S01E03')
    expect(files[0].newName).toContain('CHS')
    expect(files[0].newName).toContain('.srt')
  })

  it('字幕有语言标记', () => {
    const files = [
      f('Show.S01E01.mkv', '/dl/Show.S01E01.mkv'),
      f('Show.S01E01.chs.srt', '/dl/Show.S01E01.chs.srt'),
    ]
    performSmartRename(files, 'tv', 'Show')
    // 字幕文件本身也有 S01E01，应被主逻辑匹配
    const sub = files[1]
    expect(sub.newName).toContain('CHS')
    expect(sub.newName).toContain('S01E01')
    expect(sub.newName).toContain('.srt')
  })

  it('OVA 被检测为 Season 0', () => {
    // isSpecial 检测 OVA 关键字，parseSeasonEpisode 会将 episode 匹配到 S0
    const files = [f('[OVA] Show - 01.mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('Season 0')
    expect(files[0].newName).toContain('S00E01')
  })

  it('PV/Menu/NCOP 被标记为 extra', () => {
    const files = [f('Show.S01E01.[NCOP].mkv')]
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('NCOP')
  })
})

// ─── 番剧模式 ────────────────────────────────────────────────────

describe('performSmartRename - 番剧 (Anime)', () => {
  it('有 S/E 时按剧集格式', () => {
    const files = [f('[SubGroup] Anime S01E03 [1080p].mkv')]
    performSmartRename(files, 'anime', 'Test Anime')
    expect(files[0].newName).toContain('Season 1')
    expect(files[0].newName).toContain('S01E03')
  })

  it('无 S/E 时按电影格式（剧场版）', () => {
    const files = [f('[SubGroup] Movie [1080p].mkv')]
    performSmartRename(files, 'anime', 'Gekijouban', '2024')
    expect(files[0].newName).toBe('Gekijouban (2024)/Gekijouban (2024).mkv')
  })

  it('番剧字幕：双语标记', () => {
    const files = [f('[SubGroup] Anime S01E01 [CHS+JP].ass')]
    performSmartRename(files, 'anime', 'Anime')
    // 复合语言码
    expect(files[0].newName).toContain('CHS+JP')
    expect(files[0].newName).toContain('.ass')
  })

  it('动漫短横线风格「 - 05」', () => {
    const files = [f('[SubGroup] Anime - 05 [1080p].mkv')]
    performSmartRename(files, 'anime', 'Anime')
    expect(files[0].newName).toContain('S01E05')
  })

  it('方括号集数 [05]', () => {
    const files = [f('[SubGroup] Anime [05].mkv')]
    performSmartRename(files, 'anime', 'Anime')
    expect(files[0].newName).toContain('S01E05')
  })

  it('方括号集数过滤分辨率数字', () => {
    // [1080] 不应被当作集数
    const files = [f('[SubGroup] Movie [1080].mkv')]
    performSmartRename(files, 'anime', 'Movie', '2024')
    expect(files[0].newName).toContain('Movie (2024)')
  })

  it('中文「第XX话」', () => {
    const files = [f('[字幕组] Anime 第08话 [1080p].mkv')]
    performSmartRename(files, 'anime', 'Anime')
    expect(files[0].newName).toContain('S01E08')
  })
})

// ─── 自定义模板 ──────────────────────────────────────────────────

describe('performSmartRename - 自定义模板', () => {
  it('使用自定义电影模板', () => {
    const files = [f('movie.mkv')]
    const tpl = { movie: '{name}{ext}' }
    performSmartRename(files, 'movie', 'Test', '', tpl)
    expect(files[0].newName).toBe('Test.mkv')
  })

  it('使用自定义剧集模板', () => {
    const files = [f('Show.S02E03.mkv')]
    const tpl = { tv: '{name} - S{ss}E{ee}{ext}' }
    performSmartRename(files, 'tv', 'Show', '', tpl)
    expect(files[0].newName).toBe('Show - S02E03.mkv')
  })
})

// ─── force overrides ─────────────────────────────────────────────

describe('performSmartRename - force overrides', () => {
  it('force season 覆盖解析值', () => {
    const files = [f('Show.E05.mkv')]
    performSmartRename(files, 'tv', 'Show', '', undefined, { season: '3' })
    expect(files[0].newName).toContain('Season 3')
    expect(files[0].newName).toContain('S03E05')
  })

  it('force episode 覆盖解析值', () => {
    const files = [f('Show.S01E99.mkv')]
    performSmartRename(files, 'tv', 'Show', '', undefined, { episode: '7' })
    expect(files[0].newName).toContain('E07')
  })

  it('force ext 覆盖扩展名', () => {
    const files = [f('video.mkv')]
    performSmartRename(files, 'movie', 'Movie', '', undefined, { ext: '.mp4' })
    expect(files[0].newName).toContain('.mp4')
  })

  it('force extra 覆盖自动检测', () => {
    const files = [f('Show.S01E01.mkv')]
    performSmartRename(files, 'tv', 'Show', '', undefined, { extra: ' - Director Cut' })
    expect(files[0].newName).toContain('Director Cut')
  })

  it('force sub_suffix 覆盖语言检测', () => {
    const files = [f('Show.S01E01.ass', 'Show.S01E01.ass')]
    performSmartRename(files, 'tv', 'Show', '', DEFAULT_RENAME_TEMPLATES, { sub_suffix: ' - Custom' })
    expect(files[0].newName).toContain('Custom')
  })
})

// ─── 语言检测 ────────────────────────────────────────────────────

describe('performSmartRename - 字幕语言', () => {
  const makeSubs = (...names: string[]) =>
    names.map((n) => f(n, n))

  it('简体中文 .chs', () => {
    const files = makeSubs('Show.S01E01.chs.ass')
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('CHS')
  })

  it('繁体中文 .cht', () => {
    const files = makeSubs('Show.S01E01.cht.ass')
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('CHT')
  })

  it('日语 .jp', () => {
    const files = makeSubs('Show.S01E01.jp.srt')
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('JP')
  })

  it('双语 [CHS+JP]', () => {
    const files = makeSubs('Show.S01E01.[CHS+JP].ass')
    performSmartRename(files, 'tv', 'Show')
    expect(files[0].newName).toContain('CHS+JP')
  })

  it('过滤字幕组名（DMG 不应被当作语言）', () => {
    const files = makeSubs('[DMG] Show.S01E01.ass')
    performSmartRename(files, 'tv', 'Show')
    // DMG 是字幕组名，不应出现在 sub_suffix 中
    expect(files[0].newName).not.toMatch(/- DMG/)
  })
})

// ==================================================================
//  流程测试：模拟真实种子下载后的文件列表 → 完整重命名管线
// ==================================================================

describe('流程测试 — 真实场景', () => {
  // ─── 场景 1：美剧种子（多集 + 字幕）──────────────────────────
  it('场景1: 美剧多集 + 多语言字幕', () => {
    const files: RenameFile[] = [
      f('Stranger.Things.S04E01.1080p.mkv', '/dl/Stranger.Things.S04/Stranger.Things.S04E01.1080p.mkv'),
      f('Stranger.Things.S04E02.1080p.mkv', '/dl/Stranger.Things.S04/Stranger.Things.S04E02.1080p.mkv'),
      f('Stranger.Things.S04E03.1080p.mkv', '/dl/Stranger.Things.S04/Stranger.Things.S04E03.1080p.mkv'),
      f('Stranger.Things.S04E01.chs.srt', '/dl/Stranger.Things.S04/Stranger.Things.S04E01.chs.srt'),
      f('Stranger.Things.S04E01.eng.srt', '/dl/Stranger.Things.S04/Stranger.Things.S04E01.eng.srt'),
      f('Stranger.Things.S04E02.chs.srt', '/dl/Stranger.Things.S04/Stranger.Things.S04E02.chs.srt'),
      f('Stranger.Things.S04E03.chs.srt', '/dl/Stranger.Things.S04/Stranger.Things.S04E03.chs.srt'),
    ]

    performSmartRename(files, 'tv', 'Stranger Things')

    // E01 视频
    expect(files[0].newName).toBe(
      'Stranger Things/Season 4/Stranger Things S04E01.mkv'
    )
    // E02 视频
    expect(files[1].newName).toContain('S04E02.mkv')
    // E03 视频
    expect(files[2].newName).toContain('S04E03.mkv')

    // E01 中文字幕（有 S01E01 模式，被主逻辑匹配）
    expect(files[3].newName).toContain('S04E01')
    expect(files[3].newName).toContain('CHS')

    // E01 英文字幕
    expect(files[4].newName).toContain('S04E01')
    expect(files[4].newName).toContain('EN')

    // E02 中文字幕
    expect(files[5].newName).toContain('S04E02')
    expect(files[5].newName).toContain('CHS')

    // E03 中文字幕
    expect(files[6].newName).toContain('S04E03')
    expect(files[6].newName).toContain('CHS')

    // 所有文件基础结构一致
    for (const file of files) {
      expect(file.newName).toContain('Stranger Things/Season 4/Stranger Things')
    }
  })

  // ─── 场景 2：番剧种子（字幕文件名含 S/E）─────────────────────
  it('场景2: 番剧 — 字幕文件名含 S/E 直接解析', () => {
    const files: RenameFile[] = [
      f('[KTXP] Anime S02E03 [1080p].mkv', '/dl/Anime/[KTXP] Anime S02E03 [1080p].mkv'),
      f('[KTXP] Anime S02E03 [1080p].CHS.ass', '/dl/Anime/[KTXP] Anime S02E03 [1080p].CHS.ass'),
      f('[KTXP] Anime S02E03 [1080p].JP.ass', '/dl/Anime/[KTXP] Anime S02E03 [1080p].JP.ass'),
    ]

    performSmartRename(files, 'anime', 'Test Anime')

    // 视频
    expect(files[0].newName).toContain('Season 2')
    expect(files[0].newName).toContain('S02E03')

    // 字幕（文件名含 S02E03，被主逻辑直接解析）
    expect(files[1].newName).toContain('S02E03')
    expect(files[1].newName).toContain('CHS')
    expect(files[1].newName).toContain('.ass')

    expect(files[2].newName).toContain('S02E03')
    expect(files[2].newName).toContain('JP')
    expect(files[2].newName).toContain('.ass')
  })

  // ─── 场景 3：电影种子（含字幕 + Sample 文件）─────────────────
  it('场景3: 电影 + 多语言字幕 + Sample', () => {
    const files: RenameFile[] = [
      f('Inception.2010.1080p.mkv', '/dl/Inception.2010.1080p.mkv'),
      f('Inception.2010.1080p.chs.srt', '/dl/Inception.2010.1080p.chs.srt'),
      f('Inception.2010.1080p.eng.srt', '/dl/Inception.2010.1080p.eng.srt'),
      f('Inception.2010.1080p.chs+eng.ass', '/dl/Inception.2010.1080p.chs+eng.ass'),
      f('sample.mkv', '/dl/sample.mkv', false), // 不勾选
    ]

    performSmartRename(files, 'movie', 'Inception', '2010')

    expect(files[0].newName).toBe('Inception (2010)/Inception (2010).mkv')
    expect(files[1].newName).toBe('Inception (2010)/Inception (2010) - CHS.srt')
    expect(files[2].newName).toBe('Inception (2010)/Inception (2010) - EN.srt')
    expect(files[3].newName).toBe('Inception (2010)/Inception (2010) - CHS.ass')
    // Sample 不勾选
    expect(files[4].newName).toBe('')
  })

  // ─── 场景 4：番剧剧场版（无 S/E）─────────────────────────────
  it('场景4: 番剧剧场版（无 S/E → 电影格式）', () => {
    const files: RenameFile[] = [
      f('[DMG] Movie [1080p][BDRip].mkv', '/dl/[DMG] Movie [1080p][BDRip].mkv'),
      f('[DMG] Movie [1080p][BDRip].chs.ass', '/dl/[DMG] Movie [1080p][BDRip].chs.ass'),
    ]

    performSmartRename(files, 'anime', 'Gekijouban Movie', '2024')

    expect(files[0].newName).toBe('Gekijouban Movie (2024)/Gekijouban Movie (2024).mkv')
    expect(files[1].newName).toBe('Gekijouban Movie (2024)/Gekijouban Movie (2024) - CHS.ass')
  })

  // ─── 场景 5：嵌套目录结构 ─────────────────────────────────────
  it('场景5: 嵌套目录 — 从路径提取季号', () => {
    const files: RenameFile[] = [
      f('Show - 01.mkv', '/dl/Game of Thrones/Season 1/Show - 01.mkv'),
      f('Show - 02.mkv', '/dl/Game of Thrones/Season 1/Show - 02.mkv'),
      f('Show - 01.mkv', '/dl/Game of Thrones/Season 2/Show - 01.mkv'),
    ]

    performSmartRename(files, 'tv', 'Game of Thrones')

    // Season 1 — 文件夹路径含 "Season 1"
    expect(files[0].newName).toContain('Season 1')
    expect(files[0].newName).toContain('S01E01')
    expect(files[1].newName).toContain('Season 1')
    expect(files[1].newName).toContain('S01E02')

    // Season 2
    expect(files[2].newName).toContain('Season 2')
    expect(files[2].newName).toContain('S02E01')
  })

  // ─── 场景 6：OVA + 特别篇混合种子 ─────────────────────────────
  it('场景6: OVA/特别篇 Season 0', () => {
    const files: RenameFile[] = [
      f('[OVA] Show - 01.mkv', '/dl/[OVA] Show - 01.mkv'),
      f('[OVA] Show - 02.mkv', '/dl/[OVA] Show - 02.mkv'),
      f('Show.S01E01.mkv', '/dl/Show.S01E01.mkv'),
    ]

    performSmartRename(files, 'tv', 'Test Show')

    // OVA → Season 0（isSpecial 检测 OVA → season=0）
    expect(files[0].newName).toContain('Season 0')
    expect(files[0].newName).toContain('S00E01')
    expect(files[1].newName).toContain('Season 0')
    expect(files[1].newName).toContain('S00E02')

    // 正片 → Season 1
    expect(files[2].newName).toContain('Season 1')
    expect(files[2].newName).toContain('S01E01')
  })

  // ─── 场景 7：动漫花园典型文件列表 ─────────────────────────────
  it('场景7: 动漫花园典型番剧（中日双语 + 繁简字幕）', () => {
    const files: RenameFile[] = [
      f('[KTXP] Anime S02E05 [1080p][CHS+JP].mkv', '/dl/[KTXP] Anime S02E05.mkv'),
      f('[KTXP] Anime S02E06 [1080p][CHT+JP].mkv', '/dl/[KTXP] Anime S02E06.mkv'),
      f('[KTXP] Anime S02E05 [1080p].CHT.ass', '/dl/[KTXP] Anime S02E05.CHT.ass'),
      f('[KTXP] Anime S02E06 [1080p].CHS.ass', '/dl/[KTXP] Anime S02E06.CHS.ass'),
    ]

    performSmartRename(files, 'anime', 'Test Anime')

    // E05 视频（语言标记仅对字幕文件生效，视频不附加）
    expect(files[0].newName).toContain('Season 2')
    expect(files[0].newName).toContain('S02E05.mkv')

    // E06 视频
    expect(files[1].newName).toContain('S02E06.mkv')

    // E05 繁中字幕
    expect(files[2].newName).toContain('S02E05')
    expect(files[2].newName).toContain('CHT')

    // E06 简中字幕
    expect(files[3].newName).toContain('S02E06')
    expect(files[3].newName).toContain('CHS')
  })

  // ─── 场景 8：批量重命名（全部 unchecked 应无修改）─────────────
  it('场景8: 全部 unchecked → newName 全为空', () => {
    const files: RenameFile[] = [
      f('a.mkv', '/dl/a.mkv', false),
      f('b.mkv', '/dl/b.mkv', false),
      f('c.srt', '/dl/c.srt', false),
    ]

    performSmartRename(files, 'tv', 'Show')

    for (const file of files) {
      expect(file.newName).toBe('')
    }
  })

  // ─── 场景 9：default 类型兜底 ──────────────────────────────────
  it('场景9: default 类型保留原名', () => {
    const files: RenameFile[] = [
      f('random.file.mkv', '/dl/random.file.mkv'),
      f('another.file.srt', '/dl/another.file.srt'),
    ]

    performSmartRename(files, 'default', 'MyName')

    expect(files[0].newName).toBe('MyName/random.file.mkv')
    expect(files[1].newName).toBe('MyName/another.file.srt')
  })
})
