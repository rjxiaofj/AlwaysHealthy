import { describe, expect, it } from 'vitest'

import { safeRedirect } from '@/utils/redirect'

describe('登录后的回跳地址', () => {
  it('站内路径原样返回', () => {
    expect(safeRedirect('/plans')).toBe('/plans')
    expect(safeRedirect('/reports/abc?tab=1')).toBe('/reports/abc?tab=1')
  })

  it('没有回跳参数时去首页', () => {
    expect(safeRedirect(undefined)).toBe('/')
    expect(safeRedirect(null)).toBe('/')
    expect(safeRedirect('')).toBe('/')
  })

  it('协议相对的地址当成站外，不跳', () => {
    // '//evil.com' 在浏览器里等价于 'https://evil.com'
    expect(safeRedirect('//evil.com')).toBe('/')
    expect(safeRedirect('//evil.com/plans')).toBe('/')
  })

  it('带协议的绝对地址当成站外，不跳', () => {
    expect(safeRedirect('https://evil.com')).toBe('/')
    expect(safeRedirect('javascript:alert(1)')).toBe('/')
  })

  it('相对路径不以斜杠开头时退回首页', () => {
    expect(safeRedirect('plans')).toBe('/')
    expect(safeRedirect('../admin')).toBe('/')
  })

  it('参数出现多次时只认第一个', () => {
    expect(safeRedirect(['/trends', '/profile'])).toBe('/trends')
    expect(safeRedirect(['//evil.com', '/trends'])).toBe('/')
  })

  it('非字符串一律退回首页', () => {
    expect(safeRedirect(42)).toBe('/')
    expect(safeRedirect({ path: '/plans' })).toBe('/')
  })
})
