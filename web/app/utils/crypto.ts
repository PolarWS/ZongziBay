import SHA256 from 'crypto-js/sha256'

/**
 * SHA-256 哈希工具
 * 将密码在前端做一次 SHA-256 后再发送到后端，避免传输明文密码
 *
 * 优先使用浏览器原生 Web Crypto API（性能更好），
 * 在不支持的降级环境（如非 HTTPS / 非 localhost）中自动回退到 crypto-js。
 */
export function sha256(input: string): Promise<string> {
  // 优先使用 Web Crypto API
  if (crypto?.subtle) {
    const encoder = new TextEncoder()
    const data = encoder.encode(input)
    return crypto.subtle.digest('SHA-256', data).then((buffer) => {
      return Array.from(new Uint8Array(buffer))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('')
    })
  }

  // 降级：使用 crypto-js（纯 JS 实现，不依赖安全上下文）
  return Promise.resolve(SHA256(input).toString())
}
