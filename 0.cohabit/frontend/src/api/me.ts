/**
 * 当前账号写操作（docs/04 §4.1、docs/05 §7）。
 *
 * - `PUT /me` 只允许改 nickname/grade/college/major；gender/email 只读；
 * - `DELETE /me` 是逻辑注销：后端会关闭在途请求、退出/解散寝室、清理联系方式并吊销会话；
 * - 前端不在本地推断结果，成功后统一用 `auth.fetchMe()` 重新拉取。
 */
import { api, apiErrorBody } from '@/api/client'

/** docs/04 §4.1：可写字段只有这四个；`gender`/`email` 由后端拒绝。 */
export interface MeUpdatePatch {
  nickname?: string
  grade?: number
  college?: string
  major?: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** PUT /api/me：只提交用户真正改过的字段，避免把只读字段带上去。 */
export async function updateMe(patch: MeUpdatePatch): Promise<void> {
  const payload: MeUpdatePatch = {}
  if (patch.nickname !== undefined) {
    payload.nickname = patch.nickname
  }
  if (patch.grade !== undefined) {
    payload.grade = patch.grade
  }
  if (patch.college !== undefined) {
    payload.college = patch.college
  }
  if (patch.major !== undefined) {
    payload.major = patch.major
  }
  await api.put('/me', payload)
}

/**
 * DELETE /api/me：账号注销（logic delete）。
 *
 * 成功后服务端同时清除 refresh Cookie，调用方只需清理内存会话并跳转登录页。
 */
export async function deleteMe(): Promise<void> {
  await api.delete('/me')
}

/**
 * 解析 `PUT /me` 的字段级错误。
 *
 * 后端的 `detail.fields.<key>` 既可能是字符串，也可能是 `{code, message}`；
 * 这里统一收成“字段 → 给人看的一句话”，页面直接显示在对应输入下方。
 */
export function meFieldErrors(error: unknown): Record<string, string> {
  const detail = apiErrorBody(error)?.detail
  if (!isRecord(detail) || !isRecord(detail.fields)) {
    return {}
  }
  const result: Record<string, string> = {}
  for (const [field, raw] of Object.entries(detail.fields)) {
    if (typeof raw === 'string' && raw.trim()) {
      result[field] = raw
      continue
    }
    if (!isRecord(raw)) {
      continue
    }
    const message = typeof raw.message === 'string' ? raw.message.trim() : ''
    if (message) {
      result[field] = message
    }
  }
  return result
}
