import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** 认证端点：不触发 401 单航班刷新（登录、刷新、登出等）。 */
    skipAuthRefresh?: boolean
    /** 内部标记：该请求已用新 access 重放过一次，避免循环刷新。 */
    authRetried?: boolean
  }
}

let accessToken: string | null = null
let refreshPromise: Promise<string | null> | null = null
let sessionExpiredHandler: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

/**
 * 会话彻底失效（refresh 失败或重放后仍 401）时通知上层。
 * 由 router 注册，用来清理 store 并跳转登录页。
 */
export function onSessionExpired(handler: (() => void) | null): void {
  sessionExpiredHandler = handler
}

function notifySessionExpired(): void {
  setAccessToken(null)
  sessionExpiredHandler?.()
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  withCredentials: true,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  if (accessToken && !config.skipAuthRefresh) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

export interface ApiErrorBody {
  code?: string
  message?: string
  detail?: unknown
}

export function apiErrorBody(error: unknown): ApiErrorBody | null {
  if (!axios.isAxiosError(error)) {
    return null
  }
  const data = error.response?.data
  if (!data || typeof data !== 'object') {
    return null
  }
  return data as ApiErrorBody
}

export function apiErrorCode(error: unknown): string {
  return apiErrorBody(error)?.code ?? ''
}

export function apiErrorStatus(error: unknown): number | null {
  return axios.isAxiosError(error) ? (error.response?.status ?? null) : null
}

/** 从 `{code,message,detail:{fields:{...}}}` 中取出字段级错误。 */
export function apiErrorFields(error: unknown): Record<string, string[]> {
  const detail = apiErrorBody(error)?.detail
  if (!detail || typeof detail !== 'object') {
    return {}
  }
  const fields = (detail as { fields?: unknown }).fields
  if (!fields || typeof fields !== 'object') {
    return {}
  }
  const result: Record<string, string[]> = {}
  for (const [field, value] of Object.entries(fields as Record<string, unknown>)) {
    if (Array.isArray(value)) {
      result[field] = value.map((item) => String(item))
    } else if (typeof value === 'string') {
      result[field] = [value]
    }
  }
  return result
}

export function retryAfterSeconds(error: unknown): number | null {
  if (!axios.isAxiosError(error)) {
    return null
  }
  const headers = error.response?.headers as Record<string, unknown> | undefined
  const raw = headers?.['retry-after'] ?? headers?.['Retry-After']
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw
  }
  if (typeof raw === 'string' && /^\d+$/.test(raw.trim())) {
    return Number(raw.trim())
  }
  return null
}

const ERROR_COPY: Record<string, string> = {
  AUTH_REQUIRED: '请先登录。',
  TOKEN_EXPIRED: '登录已过期，请重新登录。',
  TOKEN_INVALID: '登录已过期，请重新登录。',
  INVALID_CREDENTIALS: '邮箱或密码不正确。',
  ACCOUNT_DISABLED: '账号已被停用，请联系管理员。',
  VALIDATION_ERROR: '有字段需要修改，请检查后再提交。',
  EMAIL_TAKEN: '这个邮箱已经注册过了，直接登录？',
  CODE_INVALID: '验证码不正确，请重新输入。',
  CODE_EXPIRED: '验证码已过期，请重新获取。',
  INVITE_REQUIRED: '本次注册需要邀请码，请填写后重试。',
  INVITE_INVALID: '邀请码无效或已用完。',
  RATE_LIMITED: '操作太频繁，请稍后再试。',
  THROTTLED: '操作太频繁，请稍后再试。',
  FORBIDDEN: '没有权限执行这个操作。',
  PROFILE_INCOMPLETE: '画像还未完成，完成后才能继续。',
}

export function apiErrorMessage(error: unknown, fallback = '请求失败，请稍后重试'): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return '网络不稳定，已保留你的输入，请重试。'
    }
    const body = apiErrorBody(error)
    const code = body?.code ?? ''
    if (code === 'RATE_LIMITED' || code === 'THROTTLED') {
      const seconds = retryAfterSeconds(error)
      return seconds ? `操作太频繁，请 ${seconds} 秒后再试。` : ERROR_COPY[code]
    }
    return ERROR_COPY[code] || body?.message || fallback
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

interface RefreshResponse {
  access?: string
}

async function requestRefresh(): Promise<string | null> {
  try {
    const { data } = await api.post<RefreshResponse>('/auth/refresh', undefined, {
      skipAuthRefresh: true,
      timeout: 8000,
    })
    if (!data?.access) {
      setAccessToken(null)
      return null
    }
    setAccessToken(data.access)
    return data.access
  } catch {
    setAccessToken(null)
    return null
  }
}

/**
 * 单航班刷新：并发的多个 401 共享同一个 refresh 请求，
 * 其余请求在 Promise 上排队，拿到新 access 后各自重放一次。
 */
export function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = requestRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const config = error.config as InternalAxiosRequestConfig | undefined
    const status = error.response?.status

    if (!config || status !== 401 || config.skipAuthRefresh) {
      return Promise.reject(error)
    }
    // 登录接口的 401 是“凭证错误”，不能拿旧 refresh 去刷新。
    if (apiErrorCode(error) === 'INVALID_CREDENTIALS') {
      return Promise.reject(error)
    }
    if (config.authRetried) {
      notifySessionExpired()
      return Promise.reject(error)
    }

    config.authRetried = true
    const token = await refreshAccessToken()
    if (!token) {
      notifySessionExpired()
      return Promise.reject(error)
    }

    config.headers.Authorization = `Bearer ${token}`
    return api.request(config)
  },
)
