/**
 * 寝室页面的展示辅助：时间、剩余时间、路由与「学院 → 专业」候选。
 *
 * 专业不是词库接口，docs/03 §1 只固定了两个学院的演示专业；
 * 广场与筛选都从这份映射取候选，取不到就退化成自由输入（见 RoomFilters）。
 */
export function roomDetailPath(code: string): string {
  return `/rooms/${encodeURIComponent(code)}`
}

export function publicRoomPath(code: string): string {
  return `/r/${encodeURIComponent(code)}`
}

function parseDate(value: string | null): Date | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function pad(value: number): string {
  return value < 10 ? `0${value}` : String(value)
}

/** `2026-11-15 21:00`（本地时区）；无值返回 `—`。 */
export function formatDateTime(value: string | null): string {
  const date = parseDate(value)
  if (!date) {
    return '—'
  }
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

/** `2026-11-15`；无值返回 `—`。 */
export function formatDate(value: string | null): string {
  const date = parseDate(value)
  if (!date) {
    return '—'
  }
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/**
 * 转让的有效期文案：`剩余 3 小时 12 分` / `已过期` / `时间未知`。
 * 过期与否以文案呈现，不改变后端判定（过期由服务端返回 409 TRANSFER_EXPIRED）。
 */
export function deadlineText(expiresAt: string | null): string {
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
    return '不到 1 分钟'
  }
  const hours = Math.floor(minutes / 60)
  if (hours < 1) {
    return `剩余 ${minutes} 分钟`
  }
  const days = Math.floor(hours / 24)
  if (days >= 1) {
    return `剩余 ${days} 天 ${hours % 24} 小时`
  }
  return `剩余 ${hours} 小时 ${minutes % 60} 分`
}

const COLLEGE_MAJORS: Record<string, string[]> = {
  计算机学院: ['软件工程', '计算机科学'],
  外国语学院: ['英语', '日语'],
}

/** docs/03 §1 的演示专业；没有映射时返回空数组。 */
export function majorsForCollege(college: string): string[] {
  return COLLEGE_MAJORS[college] ?? []
}

/** 复制到剪贴板；失败时调用方展示可手动复制的链接。 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    const pending = navigator.clipboard.writeText(text).then(
      () => true,
      () => false,
    )
    // 有些环境（权限弹窗未决、无用户手势）会让 writeText 一直挂着，加个上限别卡住按钮。
    const result = await Promise.race([
      pending,
      new Promise<boolean>((resolve) => window.setTimeout(() => resolve(false), 1200)),
    ])
    if (result) {
      return true
    }
  }
  return legacyCopy(text)
}

function legacyCopy(text: string): boolean {
  try {
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.top = '-1000px'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(area)
    return copied
  } catch {
    return false
  }
}
