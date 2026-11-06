/**
 * 从 blob 触发浏览器下载。
 *
 * 需要鉴权的下载接口不能直接挂 a 标签跳转，得先 fetch 拿 blob。这里统一处理两个
 * 浏览器差异，别在调用处各写一遍：
 * - Firefox 要求 a 在文档里才触发下载，光 createElement 不 append 不生效。
 * - revokeObjectURL 不能紧跟 click 同步调用，下载队列还没取走 blob 就释放 URL 会失败，
 *   延迟一秒足够。
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
