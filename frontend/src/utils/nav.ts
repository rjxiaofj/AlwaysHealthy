/**
 * 导航栏高亮判定。
 *
 * 不能直接用 RouterLink 自带的 `router-link-active`：它是包含匹配，而首页的 `to` 是 `/`，
 * 所有路径都以 `/` 开头，结果无论点进哪个栏目首页都亮着，同时出现两个高亮。
 * `router-link-exact-active` 又太严：`/plans/xxx` 这类子路径不会高亮父项。
 */
export function isNavActive(currentPath: string, target: string): boolean {
  const strip = (value: string) => (value.length > 1 && value.endsWith('/') ? value.slice(0, -1) : value)
  const current = strip(currentPath || '/')
  const path = strip(target)

  // 首页只认全等，否则它就是所有路径的前缀
  if (path === '/') return current === '/'
  // 子路径算父项：`/plans/123` 要让「健康管理」亮着。
  // 要求后面跟 `/`，避免 `/plans-history` 命中 `/plans`
  return current === path || current.startsWith(`${path}/`)
}
