/**
 * 匹配 API（docs/04 §3.11、§4.2）。
 *
 * 匹配结果是纯计算结果，不落库；列表与单查返回同一形状，故共用一套归一化。
 */
import { api } from '@/api/client'
import { normalizeDims as normalizeProfileDims, type Dims } from '@/api/profiles'

export interface MatchTarget {
  uid: string
  nickname: string
  avatar_key: string
  gender: 'MALE' | 'FEMALE'
  college: string
  major: string
  grade: number
  completeness: number
  tags: string[]
  headline: string | null
}

/**
 * docs/04 §3.11 的六维对比，形状与后端一致：
 * `dims.a[key]` 是我、`dims.b[key]` 是对方、`dims.dim_score[key] = 100 - |a - b|`。
 */
export interface MatchDims {
  a: Dims
  b: Dims
  dim_score: Dims
}

/** 双向红线冲突：`owner` 是「谁的红线被对方触发」的 uid。 */
export interface RedLineConflict {
  owner: string
  red_line: string
  label: string
  other_value: string | null
  message: string
}

export interface MatchScore {
  target: MatchTarget
  score: number
  base: number
  tag_bonus: number
  red_penalty: number
  dims: MatchDims
  reasons: string[]
  conflicts: RedLineConflict[]
  version_warning: string | null
}

/** docs/04 §1.4 的分页信封。 */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface MatchQuery {
  page?: number
  pageSize?: number
  /** 精确匹配（v1）。 */
  major?: string
  /** 候选需同时包含全部标签（AND）。 */
  tags?: string[]
  minScore?: number
}

const DEFAULT_PAGE_SIZE = 20

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asInt(value: unknown, fallback = 0): number {
  return Math.round(asNumber(value, fallback))
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string' && item !== '')
}

function normalizeTarget(value: unknown): MatchTarget {
  const record = isRecord(value) ? value : {}
  return {
    uid: asString(record.uid),
    nickname: asString(record.nickname, '同学'),
    avatar_key: asString(record.avatar_key, 'avatar-01'),
    gender: record.gender === 'FEMALE' ? 'FEMALE' : 'MALE',
    college: asString(record.college),
    major: asString(record.major),
    grade: asInt(record.grade, 1),
    completeness: clamp(asInt(record.completeness, 0), 0, 100),
    tags: stringArray(record.tags),
    headline: record.headline === null ? null : asString(record.headline) || null,
  }
}

function normalizeMatchDims(value: unknown): MatchDims {
  const record = isRecord(value) ? value : {}
  return {
    a: normalizeProfileDims(record.a),
    b: normalizeProfileDims(record.b),
    dim_score: normalizeProfileDims(record.dim_score),
  }
}

function normalizeConflict(value: unknown): RedLineConflict | null {
  if (!isRecord(value)) {
    return null
  }
  const label = asString(value.label)
  const message = asString(value.message)
  if (!label && !message) {
    return null
  }
  return {
    owner: asString(value.owner),
    red_line: asString(value.red_line),
    label,
    other_value: typeof value.other_value === 'string' ? value.other_value : null,
    message,
  }
}

export function normalizeMatchScore(payload: unknown): MatchScore {
  const record = isRecord(payload) ? payload : {}
  return {
    target: normalizeTarget(record.target),
    score: clamp(asInt(record.score, 0), 0, 100),
    base: Math.round(asNumber(record.base, 0) * 10) / 10,
    tag_bonus: clamp(asInt(record.tag_bonus, 0), 0, 6),
    red_penalty: clamp(asInt(record.red_penalty, 0), 0, 30),
    dims: normalizeMatchDims(record.dims),
    reasons: stringArray(record.reasons),
    conflicts: Array.isArray(record.conflicts)
      ? record.conflicts
          .map(normalizeConflict)
          .filter((item): item is RedLineConflict => item !== null)
      : [],
    version_warning:
      record.version_warning === null ? null : asString(record.version_warning) || null,
  }
}

export function normalizeMatchPage(
  payload: unknown,
): Paginated<MatchScore> {
  const record = isRecord(payload) ? payload : {}
  const results = Array.isArray(record.results)
    ? record.results.map(normalizeMatchScore)
    : []
  return {
    count: Math.max(0, asInt(record.count, results.length)),
    next: typeof record.next === 'string' ? record.next : null,
    previous: typeof record.previous === 'string' ? record.previous : null,
    results,
  }
}

/** GET /api/match：同院同性别、画像 100、无在途请求；按 score 排序。 */
export async function fetchMatches(query: MatchQuery = {}): Promise<Paginated<MatchScore>> {
  const params: Record<string, string | number> = {
    page: query.page && query.page > 1 ? query.page : 1,
    page_size: query.pageSize ?? DEFAULT_PAGE_SIZE,
  }
  if (query.major) {
    params.major = query.major
  }
  if (query.tags?.length) {
    params.tags = query.tags.join(',')
  }
  if (typeof query.minScore === 'number') {
    params.min_score = query.minScore
  }
  const { data } = await api.get<unknown>('/match', { params })
  return normalizeMatchPage(data)
}

/** GET /api/match/:uid：单人详情（含六维双方分值、理由、红线冲突）。 */
export async function fetchMatch(uid: string): Promise<MatchScore> {
  const { data } = await api.get<unknown>(`/match/${encodeURIComponent(uid)}`)
  return normalizeMatchScore(data)
}

/** POST /api/match/:uid/score：只计算不落库；限频 60/h。 */
export async function recalculateMatch(uid: string): Promise<MatchScore> {
  const { data } = await api.post<unknown>(`/match/${encodeURIComponent(uid)}/score`)
  return normalizeMatchScore(data)
}
