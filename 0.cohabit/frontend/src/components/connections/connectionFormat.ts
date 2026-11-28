/**
 * 组寝请求的展示辅助（docs/05 §4.4、§7.2、§8.2）。
 *
 * 只负责“把服务端字段变成文案与类名”，不推导状态机：
 * 能不能点某个按钮一律看 `actions`。
 */
import type {
  ConnectionStatus,
  ConnectionSummary,
  ConnectionType,
  ContactInfo,
} from '@/api/connections'
import type { UserSummary } from '@/stores/auth'

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

const CLOSE_REASON_TEXT: Record<string, string> = {
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

const TERMINAL_STATUSES: ConnectionStatus[] = ['CONFIRMED', 'DECLINED', 'CANCELLED', 'EXPIRED']

export function connectionPath(id: number): string {
  return `/connections/${id}`
}

export function isTerminalStatus(status: ConnectionStatus): boolean {
  return TERMINAL_STATUSES.includes(status)
}

export function connectionStatusLabel(
  status: ConnectionStatus,
  direction?: 'inbox' | 'sent',
): string {
  if (status === 'PENDING' && direction === 'inbox') {
    return '待你确认'
  }
  return CONNECTION_STATUS_LABELS[status] ?? status
}

/** 状态胶囊沿用全局 `.status-*` 三档之外的语义色，在组件内补充 scoped 样式。 */
export function connectionStatusClass(status: ConnectionStatus): string {
  if (status === 'CONFIRMED') {
    return 'status-confirmed'
  }
  if (status === 'CONTACT_SHARED' || status === 'CONFIRMING') {
    return 'status-shared'
  }
  if (isTerminalStatus(status)) {
    return 'status-closed'
  }
  return 'status-pending'
}

export function connectionTypeLabel(type: ConnectionType): string {
  return CONNECTION_TYPE_LABELS[type] ?? type
}

export function connectionCounterpart(
  connection: Pick<ConnectionSummary, 'direction' | 'initiator' | 'target'>,
): UserSummary | null {
  return connection.direction === 'sent' ? connection.target : connection.initiator
}

export function counterpartMeta(user: UserSummary | null): string {
  if (!user) {
    return ''
  }
  const parts = [user.college, user.major, user.grade ? `${user.grade} 年级` : '']
  return parts.filter(Boolean).join(' · ')
}

/** 卡片第二行：这到底是一封什么请求。 */
export function connectionSummaryLine(
  connection: Pick<ConnectionSummary, 'type' | 'room' | 'direction'>,
): string {
  const roomName = connection.room?.title || connection.room?.code || ''
  if (connection.type === 'APPLY') {
    return roomName ? `申请加入「${roomName}」` : '申请加入寝室'
  }
  if (connection.type === 'INVITE' && roomName) {
    return connection.direction === 'sent'
      ? `邀请对方加入「${roomName}」`
      : `邀请你加入「${roomName}」`
  }
  return connection.direction === 'sent' ? '你发出的组寝邀请' : '发来的组寝邀请'
}

export function closeReasonText(reason: string): string {
  return CLOSE_REASON_TEXT[reason] ?? ''
}

/** 失败后的“下一步”建议：解释这次为什么没成，避免用户卡在原地。 */
const CLOSE_REASON_ADVICE: Record<string, string> = {
  DECLINED: '对方这次不打算组寝。看看其他候选人，或者过一段时间再联系。',
  INITIATOR_CANCEL: '发起人撤回了这条请求。你可以主动发起新的组寝邀请。',
  END_UNDERSTANDING: '你们结束了这次了解。换一个更合适的人试试。',
  TIMEOUT: '双方没能及时确认。新的请求会重新计时，这次可以早点确认。',
  FULL: '寝室在你确认之前已经满员了。可以申请其他寝室，或者重新找室友。',
  LOCKED: '寝室已经锁定，不再接收新成员。去找正在招人的寝室吧。',
  ROOM_DISSOLVED: '寝室解散了，这次组寝没法继续。重新匹配一个新寝室。',
  ARCHIVED: '组寝窗口已经结束，本学院暂时不能继续组寝。',
  USER_DISABLED: '对方账号已停用，这条请求无法继续。重新匹配其他候选人。',
  RATE_LIMITED: '短时间内请求太多，被系统关闭了。稍后再试。',
  ADMIN: '管理员关闭了这条请求。如有疑问可以联系管理员。',
  BLOCKED: '你们之间已经拉黑，无法继续组寝。',
  AUTO_CANCELLED: '你或对方已经加入了其他寝室，这条请求自动关闭了。',
}

export function closeReasonAdvice(reason: string): string {
  return CLOSE_REASON_ADVICE[reason] ?? '这次组寝没能成立，重新匹配一个更合适的室友。'
}

/**
 * 对方最近活跃：`刚刚活跃` / `12 分钟前活跃` / `3 天前活跃` / `暂无活跃记录`。
 * 只做展示，不参与任何状态判断。
 */
export function lastActiveText(value: string | null): string {
  const date = parseDate(value)
  if (!date) {
    return '暂无活跃记录'
  }
  const diff = Date.now() - date.getTime()
  if (diff < 0) {
    return '刚刚活跃'
  }
  const minutes = Math.floor(diff / 60000)
  if (minutes < 2) {
    return '刚刚活跃'
  }
  if (minutes < 60) {
    return `${minutes} 分钟前活跃`
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 24) {
    return `${hours} 小时前活跃`
  }
  const days = Math.floor(hours / 24)
  if (days < 30) {
    return `${days} 天前活跃`
  }
  return '超过 30 天没有活跃'
}

/** 取“对方”的最近活跃时间（发起人看目标，目标看发起人）。 */
export function counterpartLastActive(
  connection: Pick<
    ConnectionSummary,
    'direction' | 'initiator_last_active_at' | 'target_last_active_at'
  >,
): string | null {
  return connection.direction === 'sent'
    ? connection.target_last_active_at
    : connection.initiator_last_active_at
}

/** PENDING 的发起人撤回；已互见之后的任一方是“结束了解”。 */
export function cancelLabel(status: ConnectionStatus): string {
  return status === 'PENDING' ? '撤回请求' : '结束了解'
}

export function confirmLabel(status: ConnectionStatus): string {
  return status === 'CONFIRMING' ? '确认并组寝' : '确认组寝'
}

/** 详情里的四步进度（终态不显示进度条）。 */
export const CONNECTION_PHASES = ['请求已发出', '联系方式互见', '等待双方确认', '组寝成立'] as const

export function connectionPhase(status: ConnectionStatus): number {
  if (status === 'PENDING') {
    return 1
  }
  if (status === 'CONTACT_SHARED') {
    return 2
  }
  if (status === 'CONFIRMING') {
    return 3
  }
  if (status === 'CONFIRMED') {
    return 4
  }
  return 0
}

function parseDate(value: string | null): Date | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/**
 * 截止时间文案：`还剩 2 天 4 小时` / `已过期` / `时间未知`。
 * 只用于展示；最终是否过期仍以服务端 409 为准。
 */
export function connectionDeadline(expiresAt: string | null): string {
  const date = parseDate(expiresAt)
  if (!date) {
    return '时间未知'
  }
  const diff = date.getTime() - Date.now()
  if (diff <= 0) {
    return '已过期'
  }
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) {
    return '还剩不到 1 分钟'
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 1) {
    return `还剩 ${minutes} 分钟`
  }
  const days = Math.floor(hours / 24)
  if (days >= 1) {
    return `还剩 ${days} 天 ${hours % 24} 小时`
  }
  return `还剩 ${hours} 小时 ${minutes % 60} 分`
}

/**
 * 三个开放阶段各自的窗口长度，必须与后端
 * `backend/apps/connections/services.py` 的 `PENDING_TTL` / `CONTACT_TTL` / `CONFIRM_TTL`
 * 保持一致。服务端每次进入阶段都会把 `expires_at` 写成「现在 + 窗口」，
 * 所以阶段起点可以由 `expires_at - 窗口` 反推，不需要额外接口。
 */
const PHASE_WINDOW_MS: Record<string, number> = {
  PENDING: 48 * 60 * 60 * 1000,
  CONTACT_SHARED: 7 * 24 * 60 * 60 * 1000,
  CONFIRMING: 48 * 60 * 60 * 1000,
}

/** 当前阶段的窗口文案，用于「为什么是 48 小时 / 7 天」的说明链接。 */
export function phaseWindowLabel(status: ConnectionStatus): string {
  return status === 'CONTACT_SHARED' ? '7 天' : '48 小时'
}

/**
 * 当前阶段已经过去多少（0–1），用来画剩余时间进度条。
 * 终止态或缺少 `expires_at` 时返回 0，由调用方决定是否渲染。
 */
export function phaseElapsedRatio(status: ConnectionStatus, expiresAt: string | null): number {
  const window = PHASE_WINDOW_MS[status]
  const end = parseDate(expiresAt)
  if (!window || !end) {
    return 0
  }
  const startedAt = end.getTime() - window
  const elapsed = (Date.now() - startedAt) / window
  return Math.min(1, Math.max(0, elapsed))
}

export interface ContactRow {
  key: 'qq' | 'wechat' | 'phone'
  label: string
  value: string
}

export function contactRows(contact: ContactInfo): ContactRow[] {
  const rows: ContactRow[] = []
  if (contact.qq) {
    rows.push({ key: 'qq', label: 'QQ', value: contact.qq })
  }
  if (contact.wechat) {
    rows.push({ key: 'wechat', label: '微信', value: contact.wechat })
  }
  if (contact.phone) {
    rows.push({ key: 'phone', label: '手机号', value: contact.phone })
  }
  return rows
}

/**
 * 脱敏展示：默认只露首尾，避免旁人一眼看全。
 * 复制按钮复制的仍是完整值（用户主动操作）。
 */
export function maskContactValue(key: ContactRow['key'], value: string): string {
  const text = value.trim()
  if (!text) {
    return ''
  }
  if (key === 'phone') {
    return text.length >= 7 ? `${text.slice(0, 3)}****${text.slice(-4)}` : `${text.slice(0, 1)}***`
  }
  if (text.length <= 4) {
    return `${text.slice(0, 1)}***`
  }
  return `${text.slice(0, 2)}${'*'.repeat(Math.min(6, Math.max(2, text.length - 4)))}${text.slice(-2)}`
}
