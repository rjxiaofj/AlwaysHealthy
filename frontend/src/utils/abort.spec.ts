import { describe, expect, it } from 'vitest'

import { isAbortError } from '@/utils/abort'

describe('取消判断', () => {
  it('AbortError 认出来', () => {
    expect(isAbortError(new DOMException('aborted', 'AbortError'))).toBe(true)
  })

  it('普通错误不算', () => {
    expect(isAbortError(new Error('网络异常'))).toBe(false)
  })

  it('非对象不炸', () => {
    expect(isAbortError(null)).toBe(false)
    expect(isAbortError(undefined)).toBe(false)
    expect(isAbortError('AbortError')).toBe(false)
  })
})
