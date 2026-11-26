/**
 * 组寝请求 API（docs/04 §3.9–§3.10、§4.4、§5.1）。
 *
 * 约定：
 * - 列表只返回 ConnectionSummary，**不含** contact 与双方确认时间；
 *   联系方式只从详情 `GET /connections/:id` 读取，未解锁时是 `{}`（不是 null）。
 * - 动作是否可执行一律以服务端 `actions` 为准，前端不自行推导状态机。
 * - `confirm` 是两步动作：第一次返回 `CONFIRMING`，第二次返回 `CONFIRMED` + `room`。
 * - 全部错误文案见 docs/05 §8.3；每条都给出下一步。
 */
import { api, apiErrorBody, apiErrorCode, apiErrorMessage } from '@/api/client'
import type { Paginated } from '@/api/matching'
import { normalizeRoomSummary, type RoomSummary } from '@/api/rooms'
import type { Gender, UserSummary } from '@/stores/auth'

export type ConnectionType = 'INVITE' | 'APPLY'
export type ConnectionStatus =
  | 'PENDING'
  | 'CONTACT_SHARED'
  | 'CONFIRMING'
  | 'CONFIRMED'
  | 'DECLINED'
  | 'CANCELLED'
  | 'EXPIRED'
export type ConnectionDirection = 'inbox' | 'sent'

/** docs/04 §5.1：服务端按当前用户算好的动作可用性。 */
export interface ConnectionActions {
  can_accept: boolean
  can_decline: boolean
  can_cancel: boolean
  can_confirm: boolean
  /** 发起人在 PENDING 阶段先确认（异步两步确认的第一步）。 */
  can_pre_approve: boolean
  can_view_contact: boolean
}

/** docs/04 §3.10：只含对方已公开且 `show_*` 为 true 的字段。 */
export interface ContactInfo {
  qq?: string
  wechat?: string
  phone?: string
  unlocked?: boolean
}

/** docs/04 §3.9。 */
export interface ConnectionSummary {
  id: number
  type: ConnectionType
  status: ConnectionStatus
  direction: ConnectionDirection
  initiator: UserSummary | null
  target: UserSummary | null
  room: RoomSummary | null
  message: string
  contact_shared_at: string | null
  expires_at: string | null
  /** 异步确认：对方最近一次活跃（带 JWT 的请求会节流刷新）。 */
  initiator_last_active_at: string | null
  target_last_active_at: string | null
  /** 发起人是否已经先确认（对方点“同意”即可直接成立）。 */
  initiator_pre_approved: boolean
  /** 关闭原因（docs/02 §3.8）；进行中为空串。 */
  close_reason: string
  actions: ConnectionActions
}

/** docs/04 §3.10：详情比列表多 contact、双方确认时间与关闭人。 */
export interface ConnectionDetail extends ConnectionSummary {
  initiator_confirm_at: string | null
  target_confirm_at: string | null
  closed_by: UserSummary | null
  contact: ContactInfo
  version: number
}

export interface ConnectionQuery {
  /** inbox=收到的；sent=发出的。默认 inbox。 */
  role?: ConnectionDirection
  /** 可叠加多个状态；空数组表示全部。 */
  statuses?: ConnectionStatus[]
  page?: number
  pageSize?: number
}

export interface CreateConnectionPayload {
  type: ConnectionType
  target_uid: string
  room_id?: number
  capacity_pref?: 2 | 4 | 6
  message?: string
}

const CONNECTION_TYPES: ConnectionType[] = ['INVITE', 'APPLY']
const CONNECTION_STATUSES: ConnectionStatus[] = [
  'PENDING',
  'CONTACT_SHARED',
  'CONFIRMING',
  'CONFIRMED',
  'DECLINED',
  'CANCELLED',
  'EXPIRED',
]

const OPEN_STATUSES: ConnectionStatus[] = ['PENDING', 'CONTACT_SHARED', 'CONFIRMING']
const CONTACT_STATUSES: ConnectionStatus[] = ['CONTACT_SHARED', 'CONFIRMING', 'CONFIRMED']

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asInt(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : fallback
}

function asBool(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

function nullableId(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return Math.round(value)
  }
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    const parsed = Number(value.trim())
    return parsed > 0 ? parsed : null
  }
  return null
}

function normalizeGender(value: unknown): Gender | null {
  return value === 'MALE' || value === 'FEMALE' ? value : null
}

function normalizeUser(value: unknown): UserSummary | null {
  if (!isRecord(value) || !asString(value.uid)) {
    return null
  }
  return {
    uid: asString(value.uid),
    nickname: asString(value.nickname, '同学'),
    avatar_key: asString(value.avatar_key, 'avatar-01'),
    gender: normalizeGender(value.gender) ?? 'MALE',
    college: asString(value.college),
    major: asString(value.major),
    grade: asInt(value.grade, 1),
  }
}

function normalizeType(value: unknown): ConnectionType {
  return CONNECTION_TYPES.includes(value as ConnectionType) ? (value as ConnectionType) : 'INVITE'
}

function normalizeStatus(value: unknown): ConnectionStatus {
  return CONNECTION_STATUSES.includes(value as ConnectionStatus)
    ? (value as ConnectionStatus)
    : 'PENDING'
}

function normalizeRoom(value: unknown): RoomSummary | null {
  if (!isRecord(value) || !asString(value.code)) {
    return null
  }
  return normalizeRoomSummary(value)
}

const DEFAULT_ACTIONS: ConnectionActions = {
  can_accept: false,
  can_decline: false,
  can_cancel: false,
  can_confirm: false,
  can_pre_approve: false,
  can_view_contact: false,
}

function normalizeActions(value: unknown): ConnectionActions {
  if (!isRecord(value)) {
    return { ...DEFAULT_ACTIONS }
  }
  return {
    can_accept: asBool(value.can_accept),
    can_decline: asBool(value.can_decline),
    can_cancel: asBool(value.can_cancel),
    can_confirm: asBool(value.can_confirm),
    can_pre_approve: asBool(value.can_pre_approve),
    can_view_contact: asBool(value.can_view_contact),
  }
}

/** 未解锁或对方全部关闭时后端返回 `{}`；这里保持同一个形状。 */
export function normalizeContact(value: unknown): ContactInfo {
  if (!isRecord(value)) {
    return {}
  }
  const contact: ContactInfo = {}
  if (asString(value.qq)) {
    contact.qq = asString(value.qq)
  }
  if (asString(value.wechat)) {
    contact.wechat = asString(value.wechat)
  }
  if (asString(value.phone)) {
    contact.phone = asString(value.phone)
  }
  if (contact.qq || contact.wechat || contact.phone) {
    contact.unlocked = true
  }
  return contact
}

export function normalizeConnectionSummary(payload: unknown): ConnectionSummary {
  const record = isRecord(payload) ? payload : {}
  const direction: ConnectionDirection = record.direction === 'sent' ? 'sent' : 'inbox'
  return {
    id: nullableId(record.id) ?? 0,
    type: normalizeType(record.type),
    status: normalizeStatus(record.status),
    direction,
    initiator: normalizeUser(record.initiator),
    target: normalizeUser(record.target),
    room: normalizeRoom(record.room),
    message: asString(record.message),
    contact_shared_at: nullableString(record.contact_shared_at),
    expires_at: nullableString(record.expires_at),
    initiator_last_active_at: nullableString(record.initiator_last_active_at),
    target_last_active_at: nullableString(record.target_last_active_at),
    initiator_pre_approved: asBool(record.initiator_pre_approved),
    close_reason: asString(record.close_reason),
    actions: normalizeActions(record.actions),
  }
}

export function normalizeConnectionDetail(payload: unknown): ConnectionDetail {
  const record = isRecord(payload) ? payload : {}
  return {
    ...normalizeConnectionSummary(payload),
    initiator_confirm_at: nullableString(record.initiator_confirm_at),
    target_confirm_at: nullableString(record.target_confirm_at),
    closed_by: normalizeUser(record.closed_by),
    close_reason: asString(record.close_reason),
    contact: normalizeContact(record.contact),
    version: asInt(record.version),
  }
}

export function normalizeConnectionPage(payload: unknown): Paginated<ConnectionSummary> {
  const record = isRecord(payload) ? payload : {}
  const results = Array.isArray(record.results)
    ? record.results.map((item) => normalizeConnectionSummary(item))
    : []
  return {
    count: Math.max(0, asInt(record.count, results.length)),
    next: typeof record.next === 'string' ? record.next : null,
    previous: typeof record.previous === 'string' ? record.previous : null,
    results,
  }
}

export function isConnectionOpen(status: ConnectionStatus): boolean {
  return OPEN_STATUSES.includes(status)
}

/** 处于可展示联系方式的阶段（是否真的有字段仍以 contact 为准）。 */
export function isContactStage(status: ConnectionStatus): boolean {
  return CONTACT_STATUSES.includes(status)
}

// ---------------------------------------------------------------------------
// 文案（docs/05 §8.2 / §8.3）
// ---------------------------------------------------------------------------

const CONNECTION_ERROR_COPY: Record<string, string> = {
  CONNECTION_NOT_FOUND: '这个请求不存在，或者你没有权限查看。',
  FORBIDDEN: '你没有权限执行这个操作。',
  INVALID_STATE: '请求状态已经变化，刷新页面后再试。',
  REQUEST_CLOSED: '这个请求已经关闭了，可以回列表看看其他请求。',
  REQUEST_EXPIRED: '这个请求已经过期了，可以重新发起。',
  ALREADY_CONFIRMED: '你已经确认过了，等对方确认就好。',
  WINDOW_CLOSED: '组寝窗口已关闭，暂时不能发起或确认请求。',
  DUPLICATE_REQUEST: '你们之间已经有一个进行中的请求了。',
  ALREADY_IN_ROOM: '你或对方已经在寝室里了，需要先处理现有寝室。',
  TARGET_IN_ROOM: '你或对方已经在寝室里了，需要先处理现有寝室。',
  ROOM_FULL: '这个寝室刚满员了。',
  ROOM_LOCKED: '这个寝室已锁定，暂不接收新成员。',
  ROOM_ARCHIVED: '寝室已归档，现在不能加入。',
  ROOM_DISSOLVED: '寝室已解散，现在不能加入。',
  PROFILE_INCOMPLETE: '画像还没完成，完成后才能继续。',
  TARGET_PROFILE_INCOMPLETE: '对方画像还没完成，暂时不能组寝。',
  WRONG_GENDER: '只能与同性别同学组寝。',
  WRONG_COLLEGE: '只能与同学院同学组寝。',
  BLOCKED: '你们之间暂时不能发起请求。',
  SELF_REQUEST: '不能向自己发起请求。',
  INVALID_TARGET: '这个请求对象不合法，刷新页面后再试。',
  INVALID_TYPE: '请求类型不合法，刷新页面后再试。',
  CAPACITY_INVALID: '容量只能是 2 / 4 / 6。',
  RATE_LIMITED: '操作太频繁，请稍后再试。',
  THROTTLED: '操作太频繁，请稍后再试。',
  COOLDOWN: '刚刚结束一段了解，24 小时后再试。',
  AUTH_REQUIRED: '请先登录。',
  TOKEN_EXPIRED: '登录已过期，请重新登录。',
}

/** `INVALID_STATE` 的 detail.reason 更具体时优先用它。 */
function invalidStateReason(error: unknown): string {
  const detail = apiErrorBody(error)?.detail
  if (!isRecord(detail)) {
    return ''
  }
  return asString(detail.reason)
}

const INVALID_STATE_REASON_COPY: Record<string, string> = {
  REJOIN_NOT_ALLOWED: '你们之前已经同寝过，不能再次组寝。',
  ALREADY_IN_ROOM: '你或对方已经在寝室里了，需要先处理现有寝室。',
  TARGET_IN_ROOM: '你或对方已经在寝室里了，需要先处理现有寝室。',
  ROOM_FULL: '这个寝室刚满员了。',
  ROOM_LOCKED: '这个寝室已锁定，暂不接收新成员。',
}

export function connectionErrorMessage(
  error: unknown,
  fallback = '操作没有完成，请稍后重试。',
): string {
  const code = apiErrorCode(error)
  if (code === 'INVALID_STATE') {
    const reason = invalidStateReason(error)
    if (reason && INVALID_STATE_REASON_COPY[reason]) {
      return INVALID_STATE_REASON_COPY[reason]
    }
  }
  const copy = code ? CONNECTION_ERROR_COPY[code] : ''
  if (copy) {
    return copy
  }
  return apiErrorMessage(error, fallback)
}

export const CONNECTION_STATUS_LABELS: Record<ConnectionStatus, string> = {
  PENDING: '待对方确认',
  CONTACT_SHARED: '联系方式已互见',
  CONFIRMING: '待二次确认',
  CONFIRMED: '组寝成立',
  DECLINED: '已拒绝',
  CANCELLED: '已取消',
  EXPIRED: '已过期',
}

export const CONNECTION_TYPE_LABELS: Record<ConnectionType, string> = {
  INVITE: '邀请',
  APPLY: '申请',
}

/** 关闭原因（docs/02 §3.8）；CONFIRMED 没有关闭原因。 */
export const CLOSE_REASON_LABELS: Record<string, string> = {
  DECLINED: '对方拒绝了请求',
  INITIATOR_CANCEL: '发起人撤回了请求',
  END_UNDERSTANDING: '双方结束了了解',
  TIMEOUT: '请求超时关闭',
  FULL: '寝室已满员',
  LOCKED: '寝室已锁定',
  ROOM_DISSOLVED: '寝室已解散',
  ARCHIVED: '组寝窗口已结束',
  USER_DISABLED: '对方账号已停用',
  RATE_LIMITED: '请求过于频繁',
  ADMIN: '管理员关闭了请求',
  BLOCKED: '你们之间已拉黑',
  AUTO_CANCELLED: '已加入其他寝室',
}

// ---------------------------------------------------------------------------
// 请求
// ---------------------------------------------------------------------------

/** GET /api/connections：收件箱 / 发件箱分页列表。 */
export async function fetchConnections(
  query: ConnectionQuery = {},
): Promise<Paginated<ConnectionSummary>> {
  const params: Record<string, string | number> = {
    role: query.role ?? 'inbox',
    page: query.page && query.page > 1 ? query.page : 1,
    page_size: query.pageSize ?? 20,
  }
  if (query.statuses?.length) {
    params.status = query.statuses.join(',')
  }
  const { data } = await api.get<unknown>('connections/', { params })
  return normalizeConnectionPage(data)
}

/** GET /api/connections/:id：参与者详情；contact 未解锁时为 `{}`。 */
export async function fetchConnection(id: number): Promise<ConnectionDetail> {
  const { data } = await api.get<unknown>(`connections/${id}/`)
  return normalizeConnectionDetail(data)
}

async function connectionAction(id: number, action: string): Promise<ConnectionDetail> {
  const { data } = await api.post<unknown>(`connections/${id}/${action}/`)
  return normalizeConnectionDetail(data)
}

/** POST /api/connections/:id/accept：仅目标；PENDING→CONTACT_SHARED。 */
export function acceptConnection(id: number): Promise<ConnectionDetail> {
  return connectionAction(id, 'accept')
}

/** POST /api/connections/:id/decline：仅目标；PENDING→DECLINED。 */
export function declineConnection(id: number): Promise<ConnectionDetail> {
  return connectionAction(id, 'decline')
}

/** POST /api/connections/:id/cancel：撤回 / 结束了解。 */
export function cancelConnection(id: number): Promise<ConnectionDetail> {
  return connectionAction(id, 'cancel')
}

/**
 * POST /api/connections/:id/confirm：两步确认。
 * 第一次返回 CONFIRMING；第二次返回 CONFIRMED，且响应里带 room。
 * 若对方已经先确认，这一次就直接返回 CONFIRMED。
 */
export function confirmConnection(id: number): Promise<ConnectionDetail> {
  return connectionAction(id, 'confirm')
}

/**
 * POST /api/connections/:id/pre-approve：发起人先确认。
 *
 * 状态仍是 PENDING，但对方上线后点一次“同意”就直接成立组寝，
 * 双方不必同时在线。幂等，重复调用不会产生副作用。
 */
export function preApproveConnection(id: number): Promise<ConnectionDetail> {
  return connectionAction(id, 'pre-approve')
}

/** POST /api/connections：创建邀请/申请（本任务主要做收件箱，保留完整能力）。 */
export async function createConnection(
  payload: CreateConnectionPayload,
): Promise<ConnectionDetail> {
  const { data } = await api.post<unknown>('connections/', payload)
  return normalizeConnectionDetail(data)
}
