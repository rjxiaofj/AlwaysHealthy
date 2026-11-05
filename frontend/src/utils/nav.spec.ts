import { describe, expect, it } from 'vitest'

import { isNavActive } from '@/utils/nav'

describe('导航高亮', () => {
  it('首页只在根路径高亮', () => {
    expect(isNavActive('/', '/')).toBe(true)
    // 改动前用的 router-link-active 是前缀匹配，这两条会是 true，于是首页永远亮着
    expect(isNavActive('/plans', '/')).toBe(false)
    expect(isNavActive('/trends', '/')).toBe(false)
  })

  it('同一路径高亮', () => {
    expect(isNavActive('/plans', '/plans')).toBe(true)
    expect(isNavActive('/trends', '/trends')).toBe(true)
  })

  it('子路径让父项高亮', () => {
    expect(isNavActive('/plans/123', '/plans')).toBe(true)
    expect(isNavActive('/reports/abc', '/reports')).toBe(true)
  })

  it('同前缀的其他路径不算', () => {
    expect(isNavActive('/plans-history', '/plans')).toBe(false)
    expect(isNavActive('/trends2', '/trends')).toBe(false)
  })

  it('尾斜杠不影响判定', () => {
    expect(isNavActive('/plans/', '/plans')).toBe(true)
    expect(isNavActive('/plans', '/plans/')).toBe(true)
    expect(isNavActive('/', '/')).toBe(true)
  })

  it('空路径按根路径处理', () => {
    expect(isNavActive('', '/')).toBe(true)
    expect(isNavActive('', '/plans')).toBe(false)
  })

  it('登录页不点亮任何栏目', () => {
    expect(isNavActive('/login', '/')).toBe(false)
    expect(isNavActive('/login', '/plans')).toBe(false)
  })
})
