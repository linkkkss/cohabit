import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, apiErrorMessage, refreshAccessToken, setAccessToken } from '@/api/client'

export type Gender = 'MALE' | 'FEMALE'
export type UserRole = 'STUDENT' | 'ADMIN'
export type UserStatus = 'ACTIVE' | 'DISABLED'
export type RoomRole = 'OWNER' | 'MEMBER'
export type RoomStatus = 'RECRUITING' | 'FULL' | 'LOCKED' | 'ARCHIVED' | 'DISSOLVED'

export interface UserSummary {
  uid: string
  nickname: string
  avatar_key: string
  gender: Gender
  college: string
  major: string
  grade: number
}

/** docs/04 §3.6 的子集：前端守卫只需要判断“是否已入寝”。 */
export interface RoomSummary {
  code: string
  title: string
  capacity: number
  member_count: number
  status: RoomStatus
  gender?: Gender
  college?: string
  major?: string
  my_role?: RoomRole | null
}

/** docs/04 §4.1 的 Me；后端当前返回扁平结构，这里的归一化同时兼容外层包装。 */
export interface Me extends UserSummary {
  role: UserRole
  status: UserStatus
  profile_completeness: number
  questionnaire_version: string
  room: RoomSummary | null
  unread_count: number
}

export interface RegisterPayload {
  email: string
  code: string
  password: string
  nickname: string
  gender: Gender
  grade: number
  college: string
  major?: string
  invite_code?: string
}

interface AuthResponse {
  access?: string
  expires_in?: number
  user?: unknown
}

interface SendCodeResponse {
  dev_code?: string
}

type SessionStatus = 'idle' | 'loading' | 'ready'

/** 只有显式配置为字符串 "true" 时才开放前端预览模式。 */
export const ALLOW_PREVIEW = import.meta.env.VITE_ALLOW_PREVIEW === 'true'

const PREVIEW_UID = '0000000000'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function normalizeRoom(value: unknown): RoomSummary | null {
  if (typeof value === 'string' && value) {
    return { code: value, title: '', capacity: 0, member_count: 0, status: 'RECRUITING' }
  }
  if (!isRecord(value)) {
    return null
  }
  const code = asString(value.code)
  if (!code) {
    return null
  }
  const status = asString(value.status, 'RECRUITING')
  return {
    code,
    title: asString(value.title),
    capacity: asNumber(value.capacity),
    member_count: asNumber(value.member_count),
    status: (['RECRUITING', 'FULL', 'LOCKED', 'ARCHIVED', 'DISSOLVED'] as const).includes(
      status as RoomStatus,
    )
      ? (status as RoomStatus)
      : 'RECRUITING',
    gender: value.gender === 'MALE' || value.gender === 'FEMALE' ? value.gender : undefined,
    college: typeof value.college === 'string' ? value.college : undefined,
    major: typeof value.major === 'string' ? value.major : undefined,
    my_role:
      value.my_role === 'OWNER' || value.my_role === 'MEMBER'
        ? value.my_role
        : value.my_role === null
          ? null
          : undefined,
  }
}

function normalizeMe(payload: unknown): Me {
  const record = isRecord(payload) ? payload : {}
  // 兼容两种响应：扁平 Me，或 { user: UserSummary, profile_completeness, ... }。
  const nested = isRecord(record.user) ? record.user : {}
  const merged: Record<string, unknown> = { ...nested, ...record }

  return {
    uid: asString(merged.uid),
    nickname: asString(merged.nickname, '同学'),
    avatar_key: asString(merged.avatar_key, 'avatar-01'),
    gender: merged.gender === 'FEMALE' ? 'FEMALE' : 'MALE',
    college: asString(merged.college),
    major: asString(merged.major),
    grade: asNumber(merged.grade, 1),
    role: merged.role === 'ADMIN' ? 'ADMIN' : 'STUDENT',
    status: merged.status === 'DISABLED' ? 'DISABLED' : 'ACTIVE',
    profile_completeness: Math.min(100, Math.max(0, asNumber(merged.profile_completeness))),
    questionnaire_version: asString(merged.questionnaire_version, 'v1'),
    room: normalizeRoom(merged.room),
    unread_count: Math.max(0, asNumber(merged.unread_count)),
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<Me | null>(null)
  const status = ref<SessionStatus>('idle')
  const loading = ref(false)
  const error = ref('')
  const initialized = ref(false)
  const sessionExpired = ref(false)
  const previewMode = ref(false)

  let bootstrapPromise: Promise<void> | null = null

  const isAuthenticated = computed(() => user.value !== null)
  const isPreview = computed(() => previewMode.value)
  const isProfileComplete = computed(() => (user.value?.profile_completeness ?? 0) >= 100)
  const hasRoom = computed(() => Boolean(user.value?.room))
  const room = computed(() => user.value?.room ?? null)
  const unreadCount = computed(() => user.value?.unread_count ?? 0)
  const displayName = computed(() => user.value?.nickname || '同学')

  function clearSession(): void {
    user.value = null
    previewMode.value = false
    sessionExpired.value = false
    error.value = ''
    setAccessToken(null)
    initialized.value = true
    status.value = 'ready'
  }

  /** refresh 失败或重放请求仍 401：清空内存会话，由 router 决定是否跳登录。 */
  function handleSessionExpired(): void {
    if (user.value) {
      sessionExpired.value = true
    }
    user.value = null
    previewMode.value = false
    setAccessToken(null)
    initialized.value = true
    status.value = 'ready'
  }

  async function loadMe(): Promise<Me> {
    const { data } = await api.get<unknown>('/me')
    const me = normalizeMe(data)
    user.value = me
    status.value = 'ready'
    return me
  }

  async function fetchMe(): Promise<void> {
    try {
      await loadMe()
    } catch (caught) {
      error.value = apiErrorMessage(caught)
      throw caught
    }
  }

  /** 页面刷新后用 HttpOnly refresh Cookie 静默恢复会话；只执行一次。 */
  async function bootstrap(): Promise<void> {
    if (previewMode.value || initialized.value) {
      return
    }
    if (bootstrapPromise) {
      return bootstrapPromise
    }
    status.value = 'loading'
    bootstrapPromise = (async () => {
      const token = await refreshAccessToken()
      if (token) {
        try {
          await loadMe()
        } catch {
          clearSession()
          return
        }
      }
      initialized.value = true
      status.value = 'ready'
    })().finally(() => {
      bootstrapPromise = null
    })
    return bootstrapPromise
  }

  /** 路由守卫入口：从没初始化过才等待静默恢复。 */
  async function ensureReady(): Promise<void> {
    await bootstrap()
  }

  async function applyAuth(data: AuthResponse): Promise<void> {
    if (typeof data.access !== 'string' || !data.access) {
      throw new Error('登录响应缺少凭证，请稍后重试。')
    }
    setAccessToken(data.access)
    previewMode.value = false
    sessionExpired.value = false
    error.value = ''
    if (data.user) {
      user.value = normalizeMe(data.user)
    } else {
      await loadMe()
    }
    initialized.value = true
    status.value = 'ready'
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const { data } = await api.post<AuthResponse>(
        '/auth/login',
        { email, password },
        { skipAuthRefresh: true },
      )
      await applyAuth(data)
    } catch (caught) {
      error.value = apiErrorMessage(caught)
      throw caught
    } finally {
      loading.value = false
    }
  }

  async function register(payload: RegisterPayload): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const body: Record<string, unknown> = {
        email: payload.email,
        code: payload.code,
        password: payload.password,
        nickname: payload.nickname,
        gender: payload.gender,
        grade: payload.grade,
        college: payload.college,
      }
      if (payload.major) {
        body.major = payload.major
      }
      if (payload.invite_code) {
        body.invite_code = payload.invite_code
      }
      const { data } = await api.post<AuthResponse>('/auth/register', body, {
        skipAuthRefresh: true,
      })
      await applyAuth(data)
    } catch (caught) {
      error.value = apiErrorMessage(caught)
      throw caught
    } finally {
      loading.value = false
    }
  }

  /** 开发环境后端会返回 dev_code；正式环境为 204，返回 null。 */
  async function sendCode(email: string): Promise<string | null> {
    error.value = ''
    const { data } = await api.post<SendCodeResponse | ''>(
      '/auth/send-code',
      { email, purpose: 'REGISTER' },
      { skipAuthRefresh: true },
    )
    return isRecord(data) && typeof data.dev_code === 'string' ? data.dev_code : null
  }

  async function logout(): Promise<void> {
    if (!previewMode.value) {
      try {
        await api.post('/auth/logout', undefined, { skipAuthRefresh: true, timeout: 8000 })
      } catch {
        // 网络失败也要清空本地会话；服务端 Cookie 由下次 refresh 自然失效。
      }
    }
    clearSession()
  }

  /** 仅当 VITE_ALLOW_PREVIEW 显式为 "true" 时可用；不写入任何持久化存储。 */
  function startPreview(): void {
    if (!ALLOW_PREVIEW) {
      return
    }
    setAccessToken(null)
    previewMode.value = true
    sessionExpired.value = false
    error.value = ''
    user.value = {
      uid: PREVIEW_UID,
      nickname: '预览用户',
      avatar_key: 'avatar-01',
      gender: 'MALE',
      college: '计算机学院',
      major: '',
      grade: 1,
      role: 'STUDENT',
      status: 'ACTIVE',
      profile_completeness: 100,
      questionnaire_version: 'v1',
      room: null,
      unread_count: 0,
    }
    initialized.value = true
    status.value = 'ready'
  }

  return {
    user,
    status,
    loading,
    error,
    initialized,
    sessionExpired,
    previewMode,
    isAuthenticated,
    isPreview,
    isProfileComplete,
    hasRoom,
    room,
    unreadCount,
    displayName,
    bootstrap,
    ensureReady,
    fetchMe,
    login,
    register,
    sendCode,
    logout,
    startPreview,
    clearSession,
    handleSessionExpired,
  }
})
