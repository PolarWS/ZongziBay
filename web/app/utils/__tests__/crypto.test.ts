/**
 * SHA-256 加密工具测试
 */
import { describe, it, expect } from 'vitest'
import { sha256 } from '../crypto'

describe('sha256', () => {
  it('生成 64 位 hex 字符串', async () => {
    const hash = await sha256('hello')
    expect(hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(hash)).toBe(true)
  })

  it('相同输入产生相同输出', async () => {
    const h1 = await sha256('password123')
    const h2 = await sha256('password123')
    expect(h1).toBe(h2)
  })

  it('不同输入产生不同输出', async () => {
    const h1 = await sha256('password123')
    const h2 = await sha256('password124')
    expect(h1).not.toBe(h2)
  })

  it('空字符串也能哈希', async () => {
    const hash = await sha256('')
    expect(hash).toHaveLength(64)
  })

  it('中文密码', async () => {
    const hash = await sha256('密码测试123')
    expect(hash).toHaveLength(64)
  })

  it('已知 SHA-256 向量', async () => {
    // SHA-256('abc') = ba7816bf...
    const hash = await sha256('abc')
    expect(hash).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
  })
})
