/**
 * 组寝时间窗状态（docs/04 §1.8、§3.13、§4.7；P2-1/WK-03）。
 *
 * - `GET /api/timewindow/` 只读，需登录；未登录 401；
 * - 无记录、用户无学院或窗口已结束都返回 `200 CLOSED`，不会返回 409；
 * - `start_at/end_at/server_time` 是服务器本地时区（默认 Asia/Shanghai）带偏移量的
 *   ISO 8601，前端直接交给 `Date` 按浏览器本地时区展示；
 * - `days_until_*` 是剩余时间向上取整到天：整 7 天 → 7，多 1 秒 → 8。
 */
import { api } from '@/api/client'

/** docs/04 §3.13：`status ∈ {OPEN,UPCOMING,CLOSED}`。 */
export type TimeWindowPhase = 'OPEN' | 'UPCOMING' | 'CLOSED'

/** `TimeWindowStatus`：后端固定返回这 8 个字段。 */
export interface TimeWindowState {
  college: string
  status: TimeWindowPhase
  is_open: boolean
  start_at: string | null
  end_at: string | null
  days_until_start: number | null
  days_until_end: number | null
  server_time: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
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

/** 未知阶段按 CLOSED 处理：横幅宁可少显示，也不猜测窗口开放。 */
function normalizePhase(value: unknown): TimeWindowPhase {
  return value === 'OPEN' || value === 'UPCOMING' ? value : 'CLOSED'
}

export function normalizeTimeWindowState(payload: unknown): TimeWindowState {
  const record = isRecord(payload) ? payload : {}
  const status = normalizePhase(record.status)
  return {
    college: asString(record.college),
    status,
    // 契约固定 is_open = (status == "OPEN")，以后端阶段为准。
    is_open: status === 'OPEN',
    start_at: nullableString(record.start_at),
    end_at: nullableString(record.end_at),
    days_until_start: nullableInt(record.days_until_start),
    days_until_end: nullableInt(record.days_until_end),
    server_time: asString(record.server_time),
  }
}

/** GET /api/timewindow/：本学院窗口阶段与倒计时。 */
export async function fetchTimeWindow(): Promise<TimeWindowState> {
  const { data } = await api.get<unknown>('timewindow/')
  return normalizeTimeWindowState(data)
}
