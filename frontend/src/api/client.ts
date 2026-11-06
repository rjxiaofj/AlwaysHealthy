import type { ApiEnvelope, TokenPayload } from './types'

const BASE = '/api/v1'
const ACCESS_KEY = 'ah_access'
const REFRESH_KEY = 'ah_refresh'

export class ApiError extends Error {
  code: string
  status: number
  detail: unknown

  constructor(code: string, message: string, status: number, detail: unknown = null) {
    super(message)
    this.code = code
    this.status = status
    this.detail = detail
  }
}

let expiredNotified = false

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY) || ''
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY) || ''
  },
  save(payload: TokenPayload) {
    localStorage.setItem(ACCESS_KEY, payload.access_token)
    localStorage.setItem(REFRESH_KEY, payload.refresh_token)
    // 换了新令牌就重新有机会报一次过期，否则退出再登录后过期不跳转
    expiredNotified = false
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

let sessionExpiredHandler: (() => void) | null = null

/**
 * 注册「登录态彻底失效」的回调。页面侧用它把人送回登录页。
 * 放在这里注册而不是 import router，是为了不让 api 层反向依赖路由。
 */
export function setSessionExpiredHandler(handler: (() => void) | null) {
  sessionExpiredHandler = handler
}

function notifySessionExpired() {
  // 布局和页面会同时发请求，一起拿到 401 时只报一次，别弹一屏提示
  if (expiredNotified) return
  expiredNotified = true
  tokens.clear()
  sessionExpiredHandler?.()
}

let refreshTask: Promise<boolean> | null = null

async function refreshAccess(): Promise<boolean> {
  if (!tokens.refresh) return false
  if (!refreshTask) {
    refreshTask = (async () => {
      try {
        const response = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: tokens.refresh }),
        })
        if (!response.ok) {
          tokens.clear()
          return false
        }
        const body = (await response.json()) as ApiEnvelope<TokenPayload>
        tokens.save(body.data)
        return true
      } catch {
        tokens.clear()
        return false
      } finally {
        refreshTask = null
      }
    })()
  }
  return refreshTask
}

/**
 * 手动续一次令牌。流式请求走的是裸 fetch，不经过 `api()`，要自己调这个。
 * 并发调用会被 `refreshTask` 合并成一次 `/auth/refresh`。
 */
export function refreshSession(): Promise<boolean> {
  return refreshAccess()
}

type Query = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Query
  formData?: FormData
  retry?: boolean
  /** 覆盖默认的 /api/v1 前缀。/health/* 挂在根路径，不走版本前缀 */
  base?: string
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${options.base ?? BASE}${path}`, window.location.origin)
  if (options.params) {
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') url.searchParams.set(key, String(value))
    })
  }

  const headers: Record<string, string> = {}
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const response = await fetch(url.toString(), {
    method: options.method || (options.body || options.formData ? 'POST' : 'GET'),
    headers,
    body,
  })

  if (response.status === 401) {
    if (options.retry !== false) {
      const refreshed = await refreshAccess()
      if (refreshed) return api<T>(path, { ...options, retry: false })
    }
    // 带着令牌还被判 401、续期又没救回来，说明会话真的失效了。
    // 登录接口自己返回 401（密码错）不会走到这里，因为那次请求没带 Authorization
    if (headers.Authorization) notifySessionExpired()
  }

  const payload = (await response.json().catch(() => null)) as ApiEnvelope<T> | null
  if (!response.ok || !payload || payload.code !== 'SUCCESS') {
    throw new ApiError(
      payload?.code || 'INTERNAL_ERROR',
      payload?.message || `请求失败 ${response.status}`,
      response.status,
      payload?.data,
    )
  }
  return payload.data
}
