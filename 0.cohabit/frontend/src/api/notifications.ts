/**
 * 通知 API（docs/04 §3.12、§4.5；docs/03 §9）。
 *
 * 约定：
 * - 列表按 `created_at DESC, id DESC`，分页默认 20、上限 50；
 * - `unread=true` 只返回未读；未读数单独走轻量接口，供铃铛 20–30s 轮询；
 * - 标记已读幂等，重复调用返回第一次的 `read_at`；
 * - 通知不存在或非本人统一 404 `NOTIFICATION_NOT_FOUND`（不泄露存在性）。
 */
import { api, apiErrorCode, apiErrorMessage } from '@/api/client'
import type { Paginated } from '@/api/matching'

/** 通知变化事件：铃铛与通知页用它同步未读数，避免各自轮询。 */
export const NOTIFICATIONS_CHANGED_EVENT = 'cohabit:notifications-changed'

export function notifyNotificationsChanged(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(NOTIFICATIONS_CHANGED_EVENT))
  }
}

export type NotificationType =
  | 'CONNECTION_RECEIVED'
  | 'CONTACT_SHARED'
  | 'CONFIRM_PENDING'
  | 'CONFIRMED'
  | 'DECLINED'
  | 'SYSTEM'
  | 'MEMBER_JOINED'
  | 'ROOM_FULL'
  | 'MEMBER_LEFT'
  | 'ROOM_LOCKED'
  | 'ROOM_DISSOLVED'
  | 'ROOM_ARCHIVED'
  | 'TRANSFER_RECEIVED'
  | 'TRANSFER_ACCEPTED'
  | 'TRANSFER_DECLINED'
  | 'TRANSFER_EXPIRED'
  | 'TRANSFER_CANCELLED'
  | 'WINDOW_CLOSING'

const NOTIFICATION_TYPES: NotificationType[] = [
  'CONNECTION_RECEIVED',
  'CONTACT_SHARED',
  'CONFIRM_PENDING',
  'CONFIRMED',
  'DECLINED',
  'SYSTEM',
  'MEMBER_JOINED',
  'ROOM_FULL',
  'MEMBER_LEFT',
  'ROOM_LOCKED',
  'ROOM_DISSOLVED',
  'ROOM_ARCHIVED',
  'TRANSFER_RECEIVED',
  'TRANSFER_ACCEPTED',
  'TRANSFER_DECLINED',
  'TRANSFER_EXPIRED',
  'TRANSFER_CANCELLED',
  'WINDOW_CLOSING',
]

/** 通知 payload 只含 id/昵称/房间号/原因/人数/时间，不含联系方式。 */
export interface NotificationPayload {
  connection_id: number | null
  room_code: string | null
  room_title: string | null
  from_nickname: string | null
  /** CONNECTION_RECEIVED 的请求类型：INVITE / APPLY。 */
  type: string
  reason: string
  member_count: number | null
  capacity: number | null
  is_self: boolean | null
  days_left: number | null
  end_at: string | null
  transfer_id: number | null
}

export interface AppNotification {
  id: number
  type: NotificationType
  title: string
  payload: NotificationPayload
  read_at: string | null
  created_at: string
}

export interface NotificationQuery {
  unread?: boolean
  page?: number
  pageSize?: number
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

function nullableInt(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.round(value)
  }
  if (typeof value === 'string' && /^-?\d+$/.test(value.trim())) {
    return Number(value.trim())
  }
  return null
}

function nullableBool(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}

function normalizePayload(value: unknown): NotificationPayload {
  const record = isRecord(value) ? value : {}
  return {
    connection_id: nullableInt(record.connection_id),
    room_code: nullableString(record.room_code),
    room_title: nullableString(record.room_title),
    from_nickname: nullableString(record.from_nickname),
    type: asString(record.type),
    reason: asString(record.reason),
    member_count: nullableInt(record.member_count),
    capacity: nullableInt(record.capacity),
    is_self: nullableBool(record.is_self),
    days_left: nullableInt(record.days_left),
    end_at: nullableString(record.end_at),
    transfer_id: nullableInt(record.transfer_id),
  }
}

export function normalizeNotificationType(value: unknown): NotificationType {
  return NOTIFICATION_TYPES.includes(value as NotificationType)
    ? (value as NotificationType)
    : 'SYSTEM'
}

export function normalizeNotification(payload: unknown): AppNotification {
  const record = isRecord(payload) ? payload : {}
  return {
    id: nullableInt(record.id) ?? 0,
    type: normalizeNotificationType(record.type),
    title: asString(record.title),
    payload: normalizePayload(record.payload),
    read_at: nullableString(record.read_at),
    created_at: asString(record.created_at),
  }
}

export function normalizeNotificationPage(payload: unknown): Paginated<AppNotification> {
  const record = isRecord(payload) ? payload : {}
  const results = Array.isArray(record.results)
    ? record.results.map((item) => normalizeNotification(item))
    : []
  return {
    count: Math.max(0, nullableInt(record.count) ?? results.length),
    next: typeof record.next === 'string' ? record.next : null,
    previous: typeof record.previous === 'string' ? record.previous : null,
    results,
  }
}

const NOTIFICATION_ERROR_COPY: Record<string, string> = {
  NOTIFICATION_NOT_FOUND: '这条通知不存在，可能已经被清理了。',
  AUTH_REQUIRED: '请先登录。',
  TOKEN_EXPIRED: '登录已过期，请重新登录。',
  RATE_LIMITED: '操作太频繁，请稍后再试。',
  THROTTLED: '操作太频繁，请稍后再试。',
}

export function notificationErrorMessage(
  error: unknown,
  fallback = '通知没有加载成功，请稍后重试。',
): string {
  const code = apiErrorCode(error)
  const copy = code ? NOTIFICATION_ERROR_COPY[code] : ''
  if (copy) {
    return copy
  }
  return apiErrorMessage(error, fallback)
}

/** GET /api/notifications：本人通知分页列表（unread=true 只看未读）。 */
export async function fetchNotifications(
  query: NotificationQuery = {},
): Promise<Paginated<AppNotification>> {
  const params: Record<string, string | number> = {
    page: query.page && query.page > 1 ? query.page : 1,
    page_size: query.pageSize ?? 20,
  }
  if (query.unread) {
    params.unread = 'true'
  }
  const { data } = await api.get<unknown>('notifications/', { params })
  return normalizeNotificationPage(data)
}

/** GET /api/notifications/unread-count：铃铛轮询用。 */
export async function fetchUnreadCount(): Promise<number> {
  const { data } = await api.get<unknown>('notifications/unread-count/')
  return Math.max(0, nullableInt(isRecord(data) ? data.count : null) ?? 0)
}

/** POST /api/notifications/:id/read：幂等，返回更新后的通知。 */
export async function markNotificationRead(id: number): Promise<AppNotification> {
  const { data } = await api.post<unknown>(`notifications/${id}/read/`)
  return normalizeNotification(data)
}

/** POST /api/notifications/read-all：返回本次更新条数。 */
export async function markAllNotificationsRead(): Promise<number> {
  const { data } = await api.post<unknown>('notifications/read-all/')
  return Math.max(0, nullableInt(isRecord(data) ? data.updated : null) ?? 0)
}
