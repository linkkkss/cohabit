/**
 * 寝室 API（docs/04 §3.6–§3.8、§4.3、§5.2、§5.3）。
 *
 * 约定：
 * - 广场（GET /rooms）只有同学院、同性别、`RECRUITING` 且有空位的寝室；分页信封见 §1.4。
 * - 详情与动作路由用的是**数字 id**（`/rooms/:room_id`），页面路由用的是 9 位 `code`
 *   （`/rooms/:code`）；后端当前在 RoomSummary 里只回 `code`，`id` 是可选字段，
 *   因此这里把 `id` 归一化为 `number | null`，视图在缺 id 时禁用房主动作而不是静默失败。
 * - 没有「公开建房 / 公开加入」接口：组寝只能走连接确认（docs/04 §4.3）。
 */
import { api, apiErrorBody, apiErrorCode, apiErrorMessage } from '@/api/client'
import type { Paginated } from '@/api/matching'
import type { Gender, RoomRole, RoomStatus, UserSummary } from '@/stores/auth'

export type { Gender, Paginated, RoomRole, RoomStatus, UserSummary }

/** docs/04 §3.6：寝室标题最长 30 字；标签最多 8 个（房间标签允许 0 个）。 */
export const ROOM_TITLE_MAX_LENGTH = 30
export const ROOM_TAGS_MAX = 8
/** docs/04 §3.6：member_preview 最多 6 个。 */
export const MEMBER_PREVIEW_LIMIT = 6
/** 广场一页 12 间，正好 3 列 × 4 行。 */
export const ROOM_SQUARE_PAGE_SIZE = 12

export type RoomTransferStatus = 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'CANCELLED' | 'EXPIRED'

/** docs/04 §3.8。 */
export interface RoomTransfer {
  id: number | null
  status: RoomTransferStatus
  from_owner: UserSummary | null
  to_member: UserSummary | null
  expires_at: string | null
  created_at: string | null
}

/** docs/04 §3.7：寝室成员（后端只回 `ACTIVE` 成员）。 */
export interface RoomMember {
  uid: string
  nickname: string
  avatar_key: string
  role: RoomRole
  status: string
  created_at: string | null
}

/** docs/04 §3.7：服务端算好的动作可用性；前端不再自己推导规则。 */
export interface RoomActions {
  can_lock: boolean
  can_unlock: boolean
  can_dissolve: boolean
  can_leave: boolean
  can_remove: boolean
  can_transfer: boolean
  can_edit: boolean
}

/** docs/04 §3.6。 */
export interface RoomSummary {
  /** 动作路由需要；后端补齐前为 null。 */
  id: number | null
  code: string
  title: string
  capacity: number
  member_count: number
  status: RoomStatus
  gender: Gender | null
  college: string
  major: string
  tags: string[]
  owner: UserSummary | null
  member_preview: UserSummary[]
  can_apply: boolean
  my_role: RoomRole | null
  pending_transfer: RoomTransfer | null
}

/** docs/04 §3.7。 */
export interface RoomDetail extends RoomSummary {
  members: RoomMember[]
  actions: RoomActions
  created_at: string | null
  archived_at: string | null
  dissolved_at: string | null
}

/** docs/04 §4.3：房主视角的待处理组寝请求（只用于计数与跳转）。 */
export interface PendingApplication {
  id: number | null
  type: string
  status: string
  initiator: UserSummary | null
  message: string
  expires_at: string | null
}

/** docs/04 §4.3 `GET /api/rooms/mine`。 */
export interface RoomMine {
  room: RoomDetail | null
  pending_applications: PendingApplication[]
  pending_transfer: RoomTransfer | null
}

/** docs/04 §4.3 公开寝室页：只有概况与成员昵称，无 uid/联系方式。 */
export interface PublicRoomMember {
  nickname: string
  avatar_key: string
}

export interface PublicRoom {
  code: string
  title: string
  capacity: number
  member_count: number
  status: RoomStatus
  college: string
  tags: string[]
  members: PublicRoomMember[]
}

export interface RoomSquareQuery {
  /** 精确匹配专业；空字符串表示全部。 */
  major?: string
  capacity?: 2 | 4 | 6 | null
  /** 需同时包含全部标签（AND）。 */
  tags?: string[]
  page?: number
  pageSize?: number
}

export interface RoomPatch {
  title?: string
  tags?: string[]
}

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

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string' && item !== '')
}

const ROOM_STATUSES: RoomStatus[] = ['RECRUITING', 'FULL', 'LOCKED', 'ARCHIVED', 'DISSOLVED']

function normalizeStatus(value: unknown): RoomStatus {
  return ROOM_STATUSES.includes(value as RoomStatus) ? (value as RoomStatus) : 'RECRUITING'
}

function normalizeGender(value: unknown): Gender | null {
  if (value === 'MALE' || value === 'FEMALE') {
    return value
  }
  return null
}

function normalizeRole(value: unknown): RoomRole | null {
  if (value === 'OWNER' || value === 'MEMBER') {
    return value
  }
  return null
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

const TRANSFER_STATUSES: RoomTransferStatus[] = [
  'PENDING',
  'ACCEPTED',
  'DECLINED',
  'CANCELLED',
  'EXPIRED',
]

export function normalizeTransfer(value: unknown): RoomTransfer | null {
  if (!isRecord(value)) {
    return null
  }
  const status = TRANSFER_STATUSES.includes(value.status as RoomTransferStatus)
    ? (value.status as RoomTransferStatus)
    : 'PENDING'
  return {
    id: nullableId(value.id),
    status,
    from_owner: normalizeUser(value.from_owner),
    to_member: normalizeUser(value.to_member),
    expires_at: nullableString(value.expires_at),
    created_at: nullableString(value.created_at),
  }
}

function normalizeMember(value: unknown): RoomMember | null {
  const user = normalizeUser(value)
  if (!user) {
    return null
  }
  const record = isRecord(value) ? value : {}
  return {
    uid: user.uid,
    nickname: user.nickname,
    avatar_key: user.avatar_key,
    role: normalizeRole(record.role) ?? 'MEMBER',
    status: asString(record.status, 'ACTIVE'),
    created_at: nullableString(record.created_at),
  }
}

function normalizeUrlList<T>(value: unknown, normalize: (item: unknown) => T | null): T[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map(normalize).filter((item): item is T => item !== null)
}

export function normalizeRoomSummary(payload: unknown): RoomSummary {
  const record = isRecord(payload) ? payload : {}
  return {
    id: nullableId(record.id),
    code: asString(record.code),
    title: asString(record.title),
    capacity: asInt(record.capacity, 0),
    member_count: asInt(record.member_count, 0),
    status: normalizeStatus(record.status),
    gender: normalizeGender(record.gender),
    college: asString(record.college),
    major: asString(record.major),
    tags: stringArray(record.tags),
    owner: normalizeUser(record.owner),
    member_preview: normalizeUrlList(record.member_preview, normalizeUser),
    can_apply: asBool(record.can_apply),
    my_role: normalizeRole(record.my_role),
    pending_transfer: normalizeTransfer(record.pending_transfer),
  }
}

const DEFAULT_ACTIONS: RoomActions = {
  can_lock: false,
  can_unlock: false,
  can_dissolve: false,
  can_leave: false,
  can_remove: false,
  can_transfer: false,
  can_edit: false,
}

function normalizeActions(value: unknown): RoomActions {
  if (!isRecord(value)) {
    return { ...DEFAULT_ACTIONS }
  }
  return {
    can_lock: asBool(value.can_lock),
    can_unlock: asBool(value.can_unlock),
    can_dissolve: asBool(value.can_dissolve),
    can_leave: asBool(value.can_leave),
    can_remove: asBool(value.can_remove),
    can_transfer: asBool(value.can_transfer),
    can_edit: asBool(value.can_edit),
  }
}

export function normalizeRoomDetail(payload: unknown): RoomDetail {
  const record = isRecord(payload) ? payload : {}
  return {
    ...normalizeRoomSummary(payload),
    members: normalizeUrlList(record.members, normalizeMember),
    actions: normalizeActions(record.actions),
    created_at: nullableString(record.created_at),
    archived_at: nullableString(record.archived_at),
    dissolved_at: nullableString(record.dissolved_at),
  }
}

function normalizePendingApplication(value: unknown): PendingApplication | null {
  if (!isRecord(value)) {
    return null
  }
  return {
    id: nullableId(value.id),
    type: asString(value.type),
    status: asString(value.status),
    initiator: normalizeUser(value.initiator),
    message: asString(value.message),
    expires_at: nullableString(value.expires_at),
  }
}

export function normalizeRoomMine(payload: unknown): RoomMine {
  const record = isRecord(payload) ? payload : {}
  const room = isRecord(record.room) ? normalizeRoomDetail(record.room) : null
  return {
    room,
    pending_applications: normalizeUrlList(record.pending_applications, normalizePendingApplication),
    pending_transfer: normalizeTransfer(record.pending_transfer),
  }
}

function normalizePublicMember(value: unknown): PublicRoomMember | null {
  if (!isRecord(value)) {
    return null
  }
  return {
    nickname: asString(value.nickname, '同学'),
    avatar_key: asString(value.avatar_key, 'avatar-01'),
  }
}

export function normalizePublicRoom(payload: unknown): PublicRoom {
  const record = isRecord(payload) ? payload : {}
  return {
    code: asString(record.code),
    title: asString(record.title),
    capacity: asInt(record.capacity, 0),
    member_count: asInt(record.member_count, 0),
    status: normalizeStatus(record.status),
    college: asString(record.college),
    tags: stringArray(record.tags),
    members: normalizeUrlList(record.members, normalizePublicMember),
  }
}

export function normalizeRoomPage(payload: unknown): Paginated<RoomSummary> {
  const record = isRecord(payload) ? payload : {}
  const results = normalizeUrlList(record.results, (item) => normalizeRoomSummary(item))
  return {
    count: Math.max(0, asInt(record.count, results.length)),
    next: typeof record.next === 'string' ? record.next : null,
    previous: typeof record.previous === 'string' ? record.previous : null,
    results,
  }
}

// ---------------------------------------------------------------------------
// 文案（docs/05 §8.2 / §8.3）：每条都给出下一步，不出现内部信息。
// ---------------------------------------------------------------------------

const ROOM_ERROR_COPY: Record<string, string> = {
  ROOM_NOT_FOUND: '这间寝室不存在，或者你没有权限查看。',
  TRANSFER_NOT_FOUND: '这条房主转让已经不在了，刷新页面后再试。',
  NOT_OWNER: '只有房主可以这样做。',
  NOT_MEMBER: '只有寝室成员可以这样做。',
  FORBIDDEN: '你没有权限执行这个操作。',
  INVALID_STATE: '寝室当前的状态不允许这个操作，刷新页面后再试。',
  CAPACITY_IMMUTABLE: '寝室容量建立后不可修改；要换容量需要重新组寝。',
  ROOM_FULL: '这个寝室刚满员了。',
  ROOM_LOCKED: '这个寝室已锁定，暂不接收新成员。',
  ROOM_ARCHIVED: '寝室已归档，现在只能查看。',
  ROOM_DISSOLVED: '寝室已解散，现在只能查看。',
  OWNER_MUST_TRANSFER_OR_DISSOLVE: '房主不能直接退出：请先转让房主，或解散寝室。',
  CANNOT_REMOVE_OWNER: '不能移除房主；房主需要先转让或解散寝室。',
  TRANSFER_EXISTS: '这间寝室已有一条待处理的转让，先处理它再发起新的。',
  TRANSFER_EXPIRED: '房主转让已过期，请重新发起。',
  WINDOW_CLOSED: '组寝窗口已关闭，暂时不能发起或确认请求。',
  ALREADY_IN_ROOM: '你或对方已经在寝室里了，需要先处理现有寝室。',
  TARGET_IN_ROOM: '你或对方已经在寝室里了，需要先处理现有寝室。',
  VALIDATION_ERROR: '有字段需要修改，请检查后再提交。',
  INVALID_TARGET: '这个操作对象不合法，刷新页面后再试。',
  CAPACITY_INVALID: '容量只能是 2 / 4 / 6。',
  AUTH_REQUIRED: '请先登录。',
  TOKEN_EXPIRED: '登录已过期，请重新登录。',
  RATE_LIMITED: '操作太频繁，请稍后再试。',
  THROTTLED: '操作太频繁，请稍后再试。',
}

/** `INVALID_STATE` 的 detail.reason 更具体时优先用它。 */
function invalidStateReason(error: unknown): string {
  const detail = apiErrorBody(error)?.detail
  if (!isRecord(detail)) {
    return ''
  }
  return asString(detail.reason)
}

/**
 * 寝室相关错误的展示文案：先查寝室错误码表，再回落到通用错误文案
 * （通用表已覆盖网络错误、限频与 401）。
 */
export function roomErrorMessage(error: unknown, fallback = '操作没有完成，请稍后重试。'): string {
  const code = apiErrorCode(error)
  if (code === 'INVALID_STATE') {
    const reason = invalidStateReason(error)
    if (reason && ROOM_ERROR_COPY[reason]) {
      return ROOM_ERROR_COPY[reason]
    }
  }
  const copy = code ? ROOM_ERROR_COPY[code] : ''
  if (copy) {
    return copy
  }
  return apiErrorMessage(error, fallback)
}

export const ROOM_STATUS_LABELS: Record<RoomStatus, string> = {
  RECRUITING: '招募中',
  FULL: '已满员',
  LOCKED: '已锁定',
  ARCHIVED: '已归档',
  DISSOLVED: '已解散',
}

export function roomStatusLabel(status: RoomStatus): string {
  return ROOM_STATUS_LABELS[status] ?? '招募中'
}

/** 全局样式只有 recruiting/full/locked 三档；归档与解散用中性档（docs/05 §2.3）。 */
export function roomStatusClass(status: RoomStatus): string {
  if (status === 'RECRUITING') {
    return 'status-recruiting'
  }
  if (status === 'LOCKED') {
    return 'status-locked'
  }
  return 'status-full'
}

export function roomRoleLabel(role: RoomRole | null): string {
  if (role === 'OWNER') {
    return '房主'
  }
  if (role === 'MEMBER') {
    return '成员'
  }
  return ''
}

export function roomSeatsText(room: Pick<RoomSummary, 'capacity' | 'member_count'>): string {
  return `${room.member_count} / ${room.capacity} 人`
}

/** 寝室是否可写：ARCHIVED / DISSOLVED 只读（docs/05 §7.2）。 */
export function isRoomReadOnly(status: RoomStatus): boolean {
  return status === 'ARCHIVED' || status === 'DISSOLVED'
}

// ---------------------------------------------------------------------------
// 请求
// ---------------------------------------------------------------------------

/** GET /api/rooms：广场（同学院同性别、招募中且有空位）。 */
export async function fetchRoomSquare(query: RoomSquareQuery = {}): Promise<Paginated<RoomSummary>> {
  const params: Record<string, string | number> = {
    page: query.page && query.page > 1 ? query.page : 1,
    page_size: query.pageSize ?? ROOM_SQUARE_PAGE_SIZE,
  }
  if (query.major) {
    params.major = query.major
  }
  if (query.capacity) {
    params.capacity = query.capacity
  }
  if (query.tags?.length) {
    params.tags = query.tags.join(',')
  }
  const { data } = await api.get<unknown>('rooms/', { params })
  return normalizeRoomPage(data)
}

/** GET /api/rooms/mine：当前寝室 + 待处理申请 + 待处理转让。 */
export async function fetchMyRoom(): Promise<RoomMine> {
  const { data } = await api.get<unknown>('rooms/mine/')
  return normalizeRoomMine(data)
}

/** GET /api/rooms/:code：按 9 位编号查详情（页面路由用的就是这个）。 */
export async function fetchRoomByCode(code: string): Promise<RoomDetail> {
  const { data } = await api.get<unknown>(`rooms/${encodeURIComponent(code)}/`)
  return normalizeRoomDetail(data)
}

/** GET /api/public/rooms/:code：公开页（免登录、有限字段）。 */
export async function fetchPublicRoom(code: string): Promise<PublicRoom> {
  const { data } = await api.get<unknown>(`public/rooms/${encodeURIComponent(code)}/`)
  return normalizePublicRoom(data)
}

/** PATCH /api/rooms/:id：房主改标题 / 标签。 */
export async function updateRoom(roomId: number, patch: RoomPatch): Promise<RoomDetail> {
  const { data } = await api.patch<unknown>(`rooms/${roomId}/`, patch)
  return normalizeRoomDetail(data)
}

async function roomAction(roomId: number, action: string): Promise<RoomDetail> {
  const { data } = await api.post<unknown>(`rooms/${roomId}/${action}/`)
  return normalizeRoomDetail(data)
}

/** POST /api/rooms/:id/lock（仅 RECRUITING）。 */
export function lockRoom(roomId: number): Promise<RoomDetail> {
  return roomAction(roomId, 'lock')
}

/** POST /api/rooms/:id/unlock（仅 LOCKED）。 */
export function unlockRoom(roomId: number): Promise<RoomDetail> {
  return roomAction(roomId, 'unlock')
}

/** POST /api/rooms/:id/dissolve（房主解散；不可逆）。 */
export function dissolveRoom(roomId: number): Promise<RoomDetail> {
  return roomAction(roomId, 'dissolve')
}

/** POST /api/rooms/:id/leave（成员退出；房主会得到 409 OWNER_MUST_TRANSFER_OR_DISSOLVE）。 */
export function leaveRoom(roomId: number): Promise<RoomDetail> {
  return roomAction(roomId, 'leave')
}

/** DELETE /api/rooms/:id/members/:uid（房主移除成员）。 */
export async function removeRoomMember(roomId: number, uid: string): Promise<RoomDetail> {
  const { data } = await api.delete<unknown>(
    `rooms/${roomId}/members/${encodeURIComponent(uid)}/`,
  )
  return normalizeRoomDetail(data)
}

/** POST /api/rooms/:id/transfer：房主发起转让（201，返回转让自身）。 */
export async function createRoomTransfer(roomId: number, toUid: string): Promise<RoomTransfer> {
  const { data } = await api.post<unknown>(`rooms/${roomId}/transfer/`, { to_uid: toUid })
  const transfer = normalizeTransfer(data)
  if (!transfer) {
    throw new Error('转让创建成功，但返回数据无法解析，请刷新页面。')
  }
  return transfer
}

async function transferAction(transferId: number, action: string): Promise<RoomTransfer> {
  const { data } = await api.post<unknown>(`room-transfers/${transferId}/${action}/`)
  const transfer = normalizeTransfer(data)
  if (!transfer) {
    throw new Error('转让状态已更新，但返回数据无法解析，请刷新页面。')
  }
  return transfer
}

/** POST /api/room-transfers/:id/accept（被转让的成员接受）。 */
export function acceptRoomTransfer(transferId: number): Promise<RoomTransfer> {
  return transferAction(transferId, 'accept')
}

/** POST /api/room-transfers/:id/decline（被转让的成员拒绝）。 */
export function declineRoomTransfer(transferId: number): Promise<RoomTransfer> {
  return transferAction(transferId, 'decline')
}

/** POST /api/room-transfers/:id/cancel（房主撤销）。 */
export function cancelRoomTransfer(transferId: number): Promise<RoomTransfer> {
  return transferAction(transferId, 'cancel')
}
