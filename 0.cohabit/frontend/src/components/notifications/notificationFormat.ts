/**
 * 通知展示辅助（docs/03 §9、docs/04 §4.5）。
 *
 * 通知本身只带 id / 昵称 / 房间号 / 原因 / 人数 / 时间，不含联系方式；
 * 跳转目标也只用 payload 里的 id 与 room_code 推导。
 */
import type { AppNotification, NotificationType } from '@/api/notifications'
import { formatDateTime, roomDetailPath } from '@/components/rooms/roomFormat'

export const NOTIFICATION_TYPE_LABELS: Record<NotificationType, string> = {
  CONNECTION_RECEIVED: '新的组寝请求',
  CONTACT_SHARED: '联系方式已互见',
  CONFIRM_PENDING: '待二次确认',
  CONFIRMED: '组寝成立',
  DECLINED: '请求被拒绝',
  SYSTEM: '系统通知',
  MEMBER_JOINED: '新成员加入',
  ROOM_FULL: '寝室已满',
  MEMBER_LEFT: '成员离开',
  ROOM_LOCKED: '寝室已锁定',
  ROOM_DISSOLVED: '寝室已解散',
  ROOM_ARCHIVED: '寝室已归档',
  TRANSFER_RECEIVED: '收到转让请求',
  TRANSFER_ACCEPTED: '转让已接受',
  TRANSFER_DECLINED: '转让已拒绝',
  TRANSFER_EXPIRED: '转让已过期',
  TRANSFER_CANCELLED: '转让已取消',
  WINDOW_CLOSING: '组寝窗口即将关闭',
}

export const NOTIFICATION_REASON_LABELS: Record<string, string> = {
  INITIATOR_CANCEL: '对方已撤回请求',
  END_UNDERSTANDING: '对方已结束了解',
  TIMEOUT: '请求已过期',
  FULL: '房间已满，请求已关闭',
  LOCKED: '房间已锁定，请求已关闭',
  ROOM_DISSOLVED: '房间已解散',
  ARCHIVED: '组寝窗口已结束',
  USER_DISABLED: '对方账号已被禁用',
  RATE_LIMITED: '请求过于频繁',
  ADMIN: '请求已被管理员关闭',
  BLOCKED: '请求已关闭',
  AUTO_CANCELLED: '你已加入其他寝室',
}

const ROOM_TYPES: NotificationType[] = [
  'CONFIRMED',
  'ROOM_FULL',
  'MEMBER_JOINED',
  'MEMBER_LEFT',
  'ROOM_LOCKED',
  'ROOM_DISSOLVED',
  'ROOM_ARCHIVED',
  'TRANSFER_RECEIVED',
  'TRANSFER_ACCEPTED',
  'TRANSFER_DECLINED',
  'TRANSFER_EXPIRED',
  'TRANSFER_CANCELLED',
]

export function notificationTypeLabel(type: NotificationType): string {
  return NOTIFICATION_TYPE_LABELS[type] || '通知'
}

export function notificationReasonText(reason: string): string {
  return NOTIFICATION_REASON_LABELS[reason] || ''
}

/** 通知点击后的目标；没有可用 id 时返回 null（只标记已读，不导航）。 */
export function notificationPath(notification: AppNotification): string | null {
  const payload = notification.payload
  if (ROOM_TYPES.includes(notification.type) && payload.room_code) {
    return roomDetailPath(payload.room_code)
  }
  if (payload.connection_id && payload.connection_id > 0) {
    return `/connections/${payload.connection_id}`
  }
  if (payload.room_code) {
    return roomDetailPath(payload.room_code)
  }
  return null
}

/** 卡片第二行：昵称 + 房间 + 人数 + 原因/窗口剩余时间。 */
export function notificationMeta(notification: AppNotification): string {
  const payload = notification.payload
  const parts: string[] = []
  if (payload.from_nickname) {
    parts.push(payload.from_nickname)
  }
  if (payload.room_code) {
    parts.push(`#${payload.room_code}`)
  }
  if (payload.member_count !== null && payload.capacity !== null) {
    parts.push(`${payload.member_count} / ${payload.capacity} 人`)
  } else if (payload.member_count !== null) {
    parts.push(`${payload.member_count} 人`)
  }
  const reason = notificationReasonText(payload.reason)
  if (reason) {
    parts.push(reason)
  }
  if (payload.days_left !== null) {
    parts.push(
      payload.days_left <= 0 ? '今天结束' : `还剩 ${payload.days_left} 天`,
    )
  }
  return parts.join(' · ')
}

/** 相对时间；跨年或无效时间回退到固定格式。 */
export function relativeTime(value: string): string {
  if (!value) {
    return '时间未知'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return formatDateTime(value)
  }
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) {
    return '刚刚'
  }
  if (diff < 3_600_000) {
    return `${Math.floor(diff / 60_000)} 分钟前`
  }
  if (diff < 86_400_000) {
    return `${Math.floor(diff / 3_600_000)} 小时前`
  }
  if (diff < 7 * 86_400_000) {
    return `${Math.floor(diff / 86_400_000)} 天前`
  }
  return formatDateTime(value)
}

/** 通知类型的小字符标记，避免额外的图标依赖。 */
export function notificationGlyph(type: NotificationType): string {
  if (type === 'CONNECTION_RECEIVED') return '请'
  if (type === 'CONTACT_SHARED') return '联'
  if (type === 'CONFIRM_PENDING') return '确'
  if (type === 'CONFIRMED') return '寝'
  if (type === 'DECLINED') return '拒'
  if (type === 'MEMBER_JOINED') return '人'
  if (type === 'ROOM_FULL') return '满'
  if (type === 'MEMBER_LEFT') return '离'
  if (type === 'ROOM_LOCKED') return '锁'
  if (type === 'ROOM_DISSOLVED') return '散'
  if (type === 'ROOM_ARCHIVED') return '档'
  if (type === 'WINDOW_CLOSING') return '窗'
  if (type.startsWith('TRANSFER_')) return '转'
  return '·'
}

export function notificationTone(type: NotificationType): 'coral' | 'ink' | 'sand' {
  if (type === 'CONNECTION_RECEIVED' || type === 'CONFIRM_PENDING' || type === 'WINDOW_CLOSING') {
    return 'coral'
  }
  if (type === 'CONFIRMED' || type === 'CONTACT_SHARED') {
    return 'ink'
  }
  return 'sand'
}

export function badgeText(count: number): string {
  if (count <= 0) {
    return ''
  }
  return count > 99 ? '99+' : String(count)
}

export function isUnread(notification: AppNotification): boolean {
  return !notification.read_at
}

export function notificationEmptyCopy(unreadOnly: boolean): string {
  return unreadOnly ? '没有未读通知，新的动静会出现在这里。' : '还没有通知。'
}
