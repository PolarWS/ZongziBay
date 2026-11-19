/**
 * Docker 环境变量注入值（GET /system/env-config）的预填决策。
 *
 * 后端对敏感字段**只返回布尔标记**，从不返回明文：例如 ZONGZI_SECURITY_PASSWORD
 * 已注入时返回 `password: true`，给 UI 看的掩码值另放在 `password_masked: "****"`。
 *
 * 因此敏感字段只能按「是否存在」处理——标记为已配置、让用户留空保持不变。
 * 若把它当作明文字符串直接填进表单，会填入字面量 "true"，并在提交时被当作
 * 真实密码写库（管理员密码变成 sha256("true")），环境变量里的真实密码则被绕过。
 */

/** 非敏感字段：后端返回真值，可直接预填 */
export type EnvPlainPrefill = {
  username?: string
  qbHost?: string
  qbUsername?: string
}

/** 敏感字段：后端只返回布尔标记，仅能用于「已配置」提示 */
export type EnvSensitiveConfigured = {
  password: boolean
  qbPassword: boolean
  qbApiKey: boolean
  tmdbApiKey: boolean
  assrtToken: boolean
}

export type EnvConfigPrefill = {
  plain: EnvPlainPrefill
  configured: EnvSensitiveConfigured
}

/**
 * 只接受非空字符串作为明文。
 * 布尔标记（true）、数字、null、空串一律视为「无明文可填」——
 * 这是防止把 `true` 当密码填入的最后一道防线。
 */
const asText = (v: unknown): string | undefined =>
  typeof v === 'string' && v.trim() !== '' ? v : undefined

export function parseEnvConfig(
  parsed: Record<string, unknown> | null | undefined,
): EnvConfigPrefill {
  const p = (parsed ?? {}) as Record<string, unknown>
  return {
    plain: {
      username: asText(p.username),
      qbHost: asText(p.qb_host),
      qbUsername: asText(p.qb_username),
    },
    configured: {
      password: Boolean(p.password),
      qbPassword: Boolean(p.qb_password),
      qbApiKey: Boolean(p.qb_api_key),
      tmdbApiKey: Boolean(p.tmdb_api_key),
      assrtToken: Boolean(p.assrt_token),
    },
  }
}

/** 表单里当前已有的值（可能来自 config.yml 的预填） */
export type PlainFieldValues = {
  username: string
  qbHost: string
  qbUsername: string
}

/**
 * 把环境变量注入的明文合并进表单当前值。
 *
 * 语义是**覆盖**，不是「仅在为空时填」。上游 `loadExistingConfig()` 会先用
 * config.yml 的值占位，而那份文件是模板：`qbittorrent.host` 默认就是
 * `http://localhost:8080`。若这里再要求「当前值为空才填」，环境变量永远进不去，
 * 容器内就会拿着 localhost 去连——那指向 app 自己，不是下载器容器。
 *
 * 环境变量没提供（undefined）时才保留原值。
 */
export function mergeEnvPlain(
  current: PlainFieldValues,
  plain: EnvPlainPrefill,
): PlainFieldValues {
  return {
    username: plain.username ?? current.username,
    qbHost: plain.qbHost ?? current.qbHost,
    qbUsername: plain.qbUsername ?? current.qbUsername,
  }
}
