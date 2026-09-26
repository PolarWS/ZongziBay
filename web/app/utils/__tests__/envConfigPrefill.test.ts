import { describe, expect, it } from 'vitest'
import { mergeEnvPlain, parseEnvConfig } from '../envConfigPrefill'

/**
 * 回归测试：Docker 环境变量预填把布尔标记当成了明文密码。
 *
 * 背景：后端 /system/env-config 对敏感字段只返回布尔标记（已注入则为 true），
 * 明文从不返回。setup.vue 曾直接 `password.value = p.password`，导致密码框被
 * 填入字面量 "true"，提交时 `sha256("true")` 被当作真实管理员密码写库，
 * 环境变量里的真实密码被静默绕过。
 *
 * 下面的 fixture 是从真实运行的容器里抓到的响应原文。
 */
const REAL_RESPONSE = {
  qb_host: 'http://qbittorrent:8080',
  qb_username: 'admin',
  qb_password: true,
  qb_password_masked: '****',
  username: 'admin',
  password: true,
  password_masked: '****',
  secret_key: true,
  secret_key_masked: '****',
}

describe('parseEnvConfig', () => {
  describe('真实 Docker 响应（回归）', () => {
    const { plain, configured } = parseEnvConfig(REAL_RESPONSE)

    it('不把敏感字段的布尔标记当作明文', () => {
      // 修复前 password.value 会被赋值成 true（表单里显示 "true"）
      expect(plain.username).toBe('admin')
      expect(plain).not.toHaveProperty('password')
      expect(plain).not.toHaveProperty('qbPassword')
    })

    it('非敏感字段正常预填', () => {
      expect(plain.qbHost).toBe('http://qbittorrent:8080')
      expect(plain.qbUsername).toBe('admin')
    })

    it('已注入的敏感字段被标记为已配置', () => {
      expect(configured.password).toBe(true)
      expect(configured.qbPassword).toBe(true)
    })

    it('未注入的敏感字段不被误标', () => {
      // 该容器未设置 ZONGZI_TMDB_API_KEY / ZONGZI_ASSRT_TOKEN，后端不返回这两个键
      expect(configured.tmdbApiKey).toBe(false)
      expect(configured.assrtToken).toBe(false)
      expect(configured.qbApiKey).toBe(false)
    })

    it('plain 中任何值都不是布尔、也不含字符串 "true"', () => {
      for (const v of Object.values(plain)) {
        expect(typeof v).not.toBe('boolean')
        expect(v).not.toBe('true')
      }
    })
  })

  describe('防御性：非字符串一律不当作明文', () => {
    it('布尔标记不会被填成 "true"', () => {
      const { plain } = parseEnvConfig({ username: true, qb_host: true, qb_username: true })
      expect(plain.username).toBeUndefined()
      expect(plain.qbHost).toBeUndefined()
      expect(plain.qbUsername).toBeUndefined()
    })

    it('数字 / null / undefined / 空串 / 纯空白 都被忽略', () => {
      const { plain } = parseEnvConfig({
        username: 123,
        qb_host: null,
        qb_username: undefined,
      })
      expect(plain.username).toBeUndefined()
      expect(plain.qbHost).toBeUndefined()
      expect(plain.qbUsername).toBeUndefined()

      expect(parseEnvConfig({ username: '' }).plain.username).toBeUndefined()
      expect(parseEnvConfig({ username: '   ' }).plain.username).toBeUndefined()
    })

    it('对象 / 数组不会被字符串化填入', () => {
      const { plain } = parseEnvConfig({ username: { a: 1 }, qb_host: ['x'] })
      expect(plain.username).toBeUndefined()
      expect(plain.qbHost).toBeUndefined()
    })
  })

  describe('边界输入', () => {
    it('null / undefined / 空对象都安全且标记全为未配置', () => {
      for (const input of [null, undefined, {}]) {
        const { plain, configured } = parseEnvConfig(input as any)
        expect(plain).toEqual({
          username: undefined,
          qbHost: undefined,
          qbUsername: undefined,
        })
        expect(Object.values(configured).every((v) => v === false)).toBe(true)
      }
    })

    it('掩码字段不会被当作可用明文（只认布尔标记）', () => {
      // 只有 _masked 而没有布尔标记时，不应标记为已配置
      const { configured } = parseEnvConfig({ password_masked: '****' })
      expect(configured.password).toBe(false)
    })
  })
})

describe('mergeEnvPlain', () => {
  /**
   * 回归：环境变量注入值必须**覆盖** config.yml 的占位值。
   *
   * setup.vue 里 loadExistingConfig() 先跑，会用 config.yml 的模板默认值
   * 占位（qbittorrent.host 默认 http://localhost:8080）；loadEnvConfig() 后跑，
   * 修复前带着 `!qbHost.value` 守卫，于是环境变量里的 http://qbittorrent:8080
   * 永远填不进去。容器内 localhost 指向 app 自己，连接必然被拒：
   *   HTTPConnectionPool(host='localhost', port=8080): Connection refused
   */
  const OCCUPIED = {
    username: '',
    qbHost: 'http://localhost:8080',
    qbUsername: '',
  }

  it('覆盖 config.yml 的模板默认地址', () => {
    const merged = mergeEnvPlain(OCCUPIED, {
      username: 'admin',
      qbHost: 'http://qbittorrent:8080',
      qbUsername: 'admin',
    })
    expect(merged.qbHost).toBe('http://qbittorrent:8080')
    expect(merged.username).toBe('admin')
    expect(merged.qbUsername).toBe('admin')
  })

  it('真实 Docker 响应端到端：localhost 占位被 qbittorrent 覆盖', () => {
    const { plain } = parseEnvConfig(REAL_RESPONSE)
    const merged = mergeEnvPlain(OCCUPIED, plain)
    expect(merged.qbHost).toBe('http://qbittorrent:8080')
    expect(merged.username).toBe('admin')
  })

  it('环境变量没提供该字段时保留原值', () => {
    const merged = mergeEnvPlain(
      { username: 'existing', qbHost: 'http://localhost:8080', qbUsername: 'xxx' },
      { qbHost: 'http://qbittorrent:8080' },
    )
    expect(merged.username).toBe('existing')
    expect(merged.qbUsername).toBe('xxx')
    expect(merged.qbHost).toBe('http://qbittorrent:8080')
  })
})
