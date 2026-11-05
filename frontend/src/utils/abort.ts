/** 判断一个异常是不是主动取消（AbortController）。组件卸载或重发时取消不该弹错误。 */
export function isAbortError(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false
  return (error as { name?: unknown }).name === 'AbortError'
}
