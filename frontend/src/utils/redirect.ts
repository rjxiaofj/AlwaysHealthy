/**
 * 登录成功后的回跳地址。
 *
 * 只接受站内绝对路径。`?redirect=` 是登录页最容易被忽略的一处：
 * 传进来的若是 `//evil.com` 或 `https://evil.com`，浏览器会把它当外站跳走，
 * 用户刚输完密码就落到别人的页面上，还以为是被踢下线了。
 */
export function safeRedirect(raw: unknown): string {
  // 同一个参数出现多次时 vue-router 给的是数组，取第一个就够了
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string') return '/'
  if (!value.startsWith('/') || value.startsWith('//')) return '/'
  return value
}
