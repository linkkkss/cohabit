/**
 * 安全入口 API：举报与拉黑（docs/04 §4.6、docs/05 §7）。
 *
 * - 举报：`POST /reports`，每用户每天最多 10 次；429 带 `Retry-After`；
 * - 拉黑：`GET /blocks`（分页）、`POST /blocks`、`DELETE /blocks/{uid}`，均幂等；
 * - 拉黑会关闭双方所有进行中的请求，但**不会**解散已经成立的寝室（S-08）。
 */
import { api, apiErrorBody, apiErrorMessage, retryAfterSeconds } from '@/api/client'

export type ReportTargetType = 'USER' | 'ROOM' | 'CONNECTION'

export interface ReportPayload {
  target_type: ReportTargetType
  target_id: number
  reason: string
}

export interface Report {
  id: number
  target_type: ReportTargetType
  target_id: number
  reason: string
  status: string
  handled_by: string | null
  created_at: string
}

/** GET /api/blocks 的列表项；不包含联系方式。 */
export interface BlockedUser {
  uid: string
  nickname: string
  avatar_key: string
  created_at: string
}

export interface BlockedUserPage {
  count: number
  next: string | null
  previous: string | null
  results: BlockedUser[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asTargetType(value: unknown): ReportTargetType {
  return value === 'ROOM' || value === 'CONNECTION' ? value : 'USER'
}

function normalizeReport(payload: unknown): Report {
  const record = isRecord(payload) ? payload : {}
  return {
    id: asNumber(record.id),
    target_type: asTargetType(record.target_type),
    target_id: asNumber(record.target_id),
    reason: asString(record.reason),
    status: asString(record.status, 'PENDING'),
    handled_by: typeof record.handled_by === 'string' ? record.handled_by : null,
    created_at: asString(record.created_at),
  }
}

function normalizeBlockedUser(payload: unknown): BlockedUser {
  const record = isRecord(payload) ? payload : {}
  return {
    uid: asString(record.uid),
    nickname: asString(record.nickname, '同学'),
    avatar_key: asString(record.avatar_key, 'avatar-01'),
    created_at: asString(record.created_at),
  }
}

function normalizeBlockedPage(payload: unknown): BlockedUserPage {
  const record = isRecord(payload) ? payload : {}
  const results = Array.isArray(record.results)
    ? record.results.map(normalizeBlockedUser).filter((item) => item.uid !== '')
    : []
  return {
    count: Math.max(0, Math.round(asNumber(record.count, results.length))),
    next: typeof record.next === 'string' ? record.next : null,
    previous: typeof record.previous === 'string' ? record.previous : null,
    results,
  }
}

/** POST /api/reports。 */
export async function createReport(payload: ReportPayload): Promise<Report> {
  const { data } = await api.post<unknown>('/reports', {
    target_type: payload.target_type,
    target_id: payload.target_id,
    reason: payload.reason,
  })
  return normalizeReport(data)
}

/** GET /api/blocks（分页，默认每页 20）。 */
export async function fetchBlocks(
  query: { page?: number; pageSize?: number } = {},
): Promise<BlockedUserPage> {
  const { data } = await api.get<unknown>('/blocks', {
    params: {
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20,
    },
  })
  return normalizeBlockedPage(data)
}

/** POST /api/blocks（body `{uid}`，幂等，成功 204）。 */
export async function blockUser(uid: string): Promise<void> {
  await api.post('/blocks', { uid })
}

/** DELETE /api/blocks/{uid}（幂等，成功 204）。 */
export async function unblockUser(uid: string): Promise<void> {
  await api.delete(`/blocks/${encodeURIComponent(uid)}`)
}

/** 举报失败时的给人看的文案：优先字段级 reason，其次限频/通用错误。 */
export function reportErrorMessage(error: unknown): string {
  const detail = apiErrorBody(error)?.detail
  if (isRecord(detail) && isRecord(detail.fields)) {
    const raw = detail.fields.reason
    if (typeof raw === 'string' && raw.trim()) {
      return raw
    }
    if (isRecord(raw) && typeof raw.message === 'string' && raw.message.trim()) {
      return raw.message
    }
  }
  if (apiErrorBody(error)?.code === 'RATE_LIMITED') {
    const seconds = retryAfterSeconds(error) ?? 0
    const hours = seconds > 0 ? Math.ceil(seconds / 3600) : 0
    return hours > 0
      ? `今天的举报次数用完了（每天最多 10 次），约 ${hours} 小时后再试。`
      : '今天的举报次数用完了（每天最多 10 次），明天再来。'
  }
  return apiErrorMessage(error, '举报没有提交成功，请稍后重试。')
}

/** 拉黑失败时的给人看的文案。 */
export function blockErrorMessage(error: unknown, fallback = '拉黑没有完成，请稍后重试。'): string {
  const body = apiErrorBody(error)
  if (body?.code === 'SELF_REQUEST') {
    return '不能拉黑自己。'
  }
  if (body?.code === 'USER_NOT_FOUND') {
    return '没有找到这个用户，可能已注销或被停用。'
  }
  if (body?.code === 'BLOCKED') {
    return '你们之间存在拉黑关系，无法继续这个操作。'
  }
  return apiErrorMessage(error, fallback)
}
