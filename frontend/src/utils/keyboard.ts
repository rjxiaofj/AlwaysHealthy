// 中文输入法选词时按 Enter 也会触发 keydown，isComposing 为真说明还在组字。
// 不挡掉的话，选词那一下会把半截输入直接发出去
export function shouldSubmitOnEnter(event: {
  key: string
  shiftKey?: boolean
  isComposing?: boolean
}): boolean {
  return event.key === 'Enter' && !event.shiftKey && !event.isComposing
}
