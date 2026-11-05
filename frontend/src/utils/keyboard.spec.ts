import { describe, expect, it } from 'vitest'

import { shouldSubmitOnEnter } from '@/utils/keyboard'

describe('回车发送', () => {
  it('普通回车发送', () => {
    expect(shouldSubmitOnEnter({ key: 'Enter' })).toBe(true)
  })

  it('Shift 加回车是换行，不发送', () => {
    expect(shouldSubmitOnEnter({ key: 'Enter', shiftKey: true })).toBe(false)
  })

  it('输入法组字时的回车不发送', () => {
    expect(shouldSubmitOnEnter({ key: 'Enter', isComposing: true })).toBe(false)
  })

  it('组字结束那一下如果 isComposing 还是真，也不发送', () => {
    expect(shouldSubmitOnEnter({ key: 'Enter', isComposing: true, shiftKey: false })).toBe(false)
  })

  it('其他按键不触发发送', () => {
    expect(shouldSubmitOnEnter({ key: 'a' })).toBe(false)
    expect(shouldSubmitOnEnter({ key: 'NumpadEnter' })).toBe(false)
  })
})
