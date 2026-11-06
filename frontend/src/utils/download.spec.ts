import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadBlob } from '@/utils/download'

describe('blob 下载', () => {
  let createObjectURL: ReturnType<typeof vi.spyOn>
  let revokeObjectURL: ReturnType<typeof vi.spyOn>
  let click: ReturnType<typeof vi.spyOn>
  let clickedLink: HTMLAnchorElement | null
  let attachedOnClick: boolean

  beforeEach(() => {
    // 只 spy 静态方法，别 stubGlobal 整个 URL：happy-dom 点 a 标签时内部要 new URL()
    // 做导航，把构造函数换掉会炸出一堆 TypeError，测试还能假绿
    createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
    revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    clickedLink = null
    attachedOnClick = false
    click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clickedLink = this
      attachedOnClick = document.body.contains(this)
    })
    document.body.innerHTML = ''
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('把链接挂进文档、点了再摘掉，页面上不留残留节点', () => {
    const blob = new Blob(['hello'])
    downloadBlob(blob, '报告.md')

    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(click).toHaveBeenCalledTimes(1)
    expect(document.querySelectorAll('a')).toHaveLength(0)
  })

  it('文件名和 href 都写到链接上，且点击时链接仍在文档里', () => {
    downloadBlob(new Blob(['x']), '体检单.pdf')

    expect(clickedLink?.download).toBe('体检单.pdf')
    expect(clickedLink?.getAttribute('href')).toBe('blob:mock-url')
    // Firefox 要求 a 在文档里才触发下载，这个断言守住 appendChild
    expect(attachedOnClick).toBe(true)
  })

  it('revoke 不同步调用：click 刚结束时 URL 还得能用', () => {
    vi.useFakeTimers()
    downloadBlob(new Blob(['x']), 'a.md')

    expect(revokeObjectURL).not.toHaveBeenCalled()
    vi.advanceTimersByTime(999)
    expect(revokeObjectURL).not.toHaveBeenCalled()
  })

  it('一秒后释放 URL，不泄漏', () => {
    vi.useFakeTimers()
    downloadBlob(new Blob(['x']), 'a.md')

    vi.advanceTimersByTime(1000)
    expect(revokeObjectURL).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
  })
})
