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
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
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

type Query = Record<string, string | number | boolean | null | undefined>

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Query
  formData?: FormData
  retry?: boolean
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
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

  if (response.status === 401 && options.retry !== false) {
    const refreshed = await refreshAccess()
    if (refreshed) return api<T>(path, { ...options, retry: false })
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
