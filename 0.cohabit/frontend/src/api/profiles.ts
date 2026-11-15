/**
 * 画像 / 问卷 / 公开用户 API（docs/04 §3.4、§3.5、§4.1、§4.2）。
 *
 * 页面只拿这里归一化后的结构：响应体先按 `unknown` 收窄，缺字段/类型不符时回落默认值，
 * 避免把 JSON 直接当类型用。字段名与契约保持一致（snake_case），不做前端改名。
 */
import { api, apiErrorBody } from '@/api/client'

/** docs/03 §8.3 的六维顺序；与后端 `profiles.constants.DIMENSIONS` 一致。 */
export const DIM_KEYS = ['sleep', 'clean', 'social', 'noise', 'boundary', 'spend'] as const
export type DimKey = (typeof DIM_KEYS)[number]
export type Dims = Record<DimKey, number>

/**
 * 维度中文名：契约（docs/04 §3.4 dims）只给 key，不给 label，故只能固定在前端。
 * 题库本身仍然全部来自 `GET /api/questionnaire`，不在前端硬编码。
 */
export const DIM_LABELS: Record<DimKey, string> = {
  sleep: '作息',
  clean: '整洁',
  social: '社交',
  noise: '声音',
  boundary: '边界',
  spend: '开销',
}

export const QUESTIONNAIRE_VERSION = 'v1'
export const MAX_TAGS = 8
export const MIN_TAGS = 3
export const MAX_PROMPTS = 3
export const MIN_PROMPTS = 2
export const PROMPT_MAX_LENGTH = 120

export interface HardOption {
  value: string
  label: string
  score: number | null
}

export interface HardQuestion {
  key: string
  title: string
  group: string
  options: HardOption[]
}

export interface SoftQuestion {
  key: string
  title: string
  min: number
  max: number
  /** 端点文案，键为 "1"…"5"（后端只给 1/3/5）。 */
  labels: Record<string, string>
}

export interface RedLineOption {
  id: string
  label: string
  description: string
}

export interface TagOption {
  group: string
  name: string
}

export interface PromptQuestion {
  key: string
  title: string
  placeholder: string
  max_length: number
}

export interface Questionnaire {
  version: string
  hard: HardQuestion[]
  soft: SoftQuestion[]
  red_lines: RedLineOption[]
  tags: TagOption[]
  prompts: PromptQuestion[]
}

/** docs/04 §3.4：Profile（dims/completeness 只读，服务端算）。 */
export interface Profile {
  hard_answers: Record<string, string>
  soft_answers: Record<string, number>
  red_lines: string[]
  red_lines_confirmed: boolean
  tags: string[]
  prompts: Record<string, string>
  dims: Dims
  completeness: number
  questionnaire_version: string
}

/** PUT 全量、PATCH 局部；只提交本步涉及的字段（docs/04 §4.1）。 */
export interface ProfilePatch {
  hard_answers?: Record<string, string>
  soft_answers?: Record<string, number>
  red_lines?: string[]
  red_lines_confirmed?: boolean
  tags?: string[]
  prompts?: Record<string, string>
  questionnaire_version?: string
}

/** docs/04 §4.2 GET /api/users/:uid：公开摘要，绝不含 contact/email/dims/red_lines。 */
export interface PublicUser {
  uid: string
  nickname: string
  avatar_key: string
  gender: 'MALE' | 'FEMALE'
  college: string
  major: string
  grade: number
  tags: string[]
  headline: string | null
  prompts: Record<string, string>
  completeness: number
}

/**
 * 基本资料 = `GET /api/me` 里参与完整度的 5 个字段。
 * M1 后端只提供 GET /api/me（docs/04 §4.1 的 PUT /api/me 未实现），所以这些字段只读展示。
 */
export interface BasicProfile {
  nickname: string
  gender: 'MALE' | 'FEMALE'
  grade: number
  college: string
  major: string
}

/** 画像字段级错误（docs/04 §1.6 detail.fields 的对象形态）。 */
export interface ProfileFieldIssue {
  code: string
  message: string
  allowed?: string[]
  max?: number
}

const ISSUE_COPY: Record<string, string> = {
  UNKNOWN_ANSWER_KEY: '题目不存在，请刷新页面后重试。',
  INVALID_OPTION: '不支持的选项。',
  INVALID_SOFT_VALUE: '请选择 1–5 之间的档位。',
  INVALID_RED_LINE: '红线选择不合法。',
  INVALID_BOOLEAN: '确认项不合法。',
  INVALID_TAG: '标签不在词库中。',
  TAG_LIMIT: '标签最多 8 个。',
  INVALID_PROMPT_KEY: '这条 Prompt 不在题库中。',
  PROMPT_TOO_LONG: 'Prompt 最多 120 字。',
  INVALID_TEXT: '文本包含不支持的内容。',
  UNKNOWN_FIELD: '存在未知字段。',
  PAYLOAD_TOO_LARGE: '提交内容过大，请删减后再试。',
  QUESTIONNAIRE_VERSION_UNSUPPORTED: '问卷版本不支持，请刷新页面。',
  VALIDATION_ERROR: '请检查这项内容。',
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

function asInt(value: unknown, fallback = 0): number {
  return Math.round(asNumber(value, fallback))
}

function clampInt(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)))
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string' && item !== '')
}

function stringRecord(value: unknown): Record<string, string> {
  if (!isRecord(value)) {
    return {}
  }
  const result: Record<string, string> = {}
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === 'string' && item !== '') {
      result[key] = item
    }
  }
  return result
}

function numberRecord(value: unknown): Record<string, number> {
  if (!isRecord(value)) {
    return {}
  }
  const result: Record<string, number> = {}
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === 'number' && Number.isFinite(item)) {
      result[key] = Math.round(item)
    }
  }
  return result
}

function normalizeOption(value: unknown): HardOption | null {
  if (!isRecord(value)) {
    return null
  }
  const optionValue = asString(value.value)
  if (!optionValue) {
    return null
  }
  return {
    value: optionValue,
    label: asString(value.label, optionValue),
    score: typeof value.score === 'number' && Number.isFinite(value.score) ? value.score : null,
  }
}

function normalizeHard(value: unknown): HardQuestion | null {
  if (!isRecord(value)) {
    return null
  }
  const key = asString(value.key)
  if (!key) {
    return null
  }
  const options = Array.isArray(value.options)
    ? value.options.map(normalizeOption).filter((item): item is HardOption => item !== null)
    : []
  return {
    key,
    title: asString(value.title, key),
    group: asString(value.group, '硬指标'),
    options,
  }
}

function normalizeSoft(value: unknown): SoftQuestion | null {
  if (!isRecord(value)) {
    return null
  }
  const key = asString(value.key)
  if (!key) {
    return null
  }
  return {
    key,
    title: asString(value.title, key),
    min: clampInt(asInt(value.min, 1), 1, 5),
    max: clampInt(asInt(value.max, 5), 1, 5),
    labels: stringRecord(value.labels),
  }
}

function normalizeRedLine(value: unknown): RedLineOption | null {
  if (!isRecord(value)) {
    return null
  }
  const id = asString(value.id)
  if (!id) {
    return null
  }
  return {
    id,
    label: asString(value.label, id),
    description: asString(value.description),
  }
}

function normalizeTagOption(value: unknown): TagOption | null {
  if (!isRecord(value)) {
    return null
  }
  const name = asString(value.name)
  if (!name) {
    return null
  }
  return { group: asString(value.group, '其他'), name }
}

function normalizePromptQuestion(value: unknown): PromptQuestion | null {
  if (!isRecord(value)) {
    return null
  }
  const key = asString(value.key)
  if (!key) {
    return null
  }
  return {
    key,
    title: asString(value.title, key),
    placeholder: asString(value.placeholder),
    max_length: clampInt(asInt(value.max_length, PROMPT_MAX_LENGTH), 1, PROMPT_MAX_LENGTH),
  }
}

export function normalizeDims(value: unknown): Dims {
  const record = isRecord(value) ? value : {}
  const dims = {} as Dims
  for (const key of DIM_KEYS) {
    dims[key] = clampInt(asInt(record[key], 0), 0, 100)
  }
  return dims
}

export function normalizeProfile(payload: unknown): Profile {
  const record = isRecord(payload) ? payload : {}
  return {
    hard_answers: stringRecord(record.hard_answers),
    soft_answers: numberRecord(record.soft_answers),
    red_lines: stringArray(record.red_lines),
    red_lines_confirmed: record.red_lines_confirmed === true,
    tags: stringArray(record.tags),
    prompts: stringRecord(record.prompts),
    dims: normalizeDims(record.dims),
    completeness: clampInt(asInt(record.completeness, 0), 0, 100),
    questionnaire_version: asString(record.questionnaire_version, QUESTIONNAIRE_VERSION),
  }
}

export function normalizeQuestionnaire(payload: unknown): Questionnaire {
  const record = isRecord(payload) ? payload : {}
  const collect = <T>(value: unknown, normalize: (item: unknown) => T | null): T[] =>
    Array.isArray(value)
      ? value.map(normalize).filter((item): item is T => item !== null)
      : []

  return {
    version: asString(record.version, QUESTIONNAIRE_VERSION),
    hard: collect(record.hard, normalizeHard),
    soft: collect(record.soft, normalizeSoft),
    red_lines: collect(record.red_lines, normalizeRedLine),
    tags: collect(record.tags, normalizeTagOption),
    prompts: collect(record.prompts, normalizePromptQuestion),
  }
}

export function normalizePublicUser(payload: unknown): PublicUser {
  const record = isRecord(payload) ? payload : {}
  const headline = record.headline === null ? null : asString(record.headline) || null
  return {
    uid: asString(record.uid),
    nickname: asString(record.nickname, '同学'),
    avatar_key: asString(record.avatar_key, 'avatar-01'),
    gender: record.gender === 'FEMALE' ? 'FEMALE' : 'MALE',
    college: asString(record.college),
    major: asString(record.major),
    grade: asInt(record.grade, 1),
    tags: stringArray(record.tags),
    headline,
    prompts: stringRecord(record.prompts),
    completeness: clampInt(asInt(record.completeness, 0), 0, 100),
  }
}

/** GET /api/questionnaire（登录即可，v1 题目配置）。 */
export async function fetchQuestionnaire(): Promise<Questionnaire> {
  const { data } = await api.get<unknown>('/questionnaire')
  return normalizeQuestionnaire(data)
}

/** GET /api/me/profile。 */
export async function fetchProfile(): Promise<Profile> {
  const { data } = await api.get<unknown>('/me/profile')
  return normalizeProfile(data)
}

/**
 * PATCH /api/me/profile（局部）或 PUT（全量）。
 * 注意：`red_lines`/`tags`/`prompts` 只要出现就整体替换；dims/completeness 由服务端重算。
 */
export async function saveProfile(
  patch: ProfilePatch,
  options: { full?: boolean } = {},
): Promise<Profile> {
  const { data } = options.full
    ? await api.put<unknown>('/me/profile', patch)
    : await api.patch<unknown>('/me/profile', patch)
  return normalizeProfile(data)
}

/** GET /api/users/:uid（同院同性别、未拉黑才可见；否则 404/403）。 */
export async function fetchPublicUser(uid: string): Promise<PublicUser> {
  const { data } = await api.get<unknown>(`/users/${encodeURIComponent(uid)}`)
  return normalizePublicUser(data)
}

/**
 * 解析画像接口的字段级错误。
 *
 * `client.apiErrorFields()` 只认「字符串/字符串数组」，而画像接口的 `detail.fields.<key>`
 * 是对象 `{code,message,allowed?,max?}`，所以这里单独实现一份。
 */
export function profileFieldIssues(error: unknown): Record<string, ProfileFieldIssue> {
  const detail = apiErrorBody(error)?.detail
  if (!isRecord(detail) || !isRecord(detail.fields)) {
    return {}
  }
  const issues: Record<string, ProfileFieldIssue> = {}
  for (const [key, raw] of Object.entries(detail.fields)) {
    if (typeof raw === 'string') {
      issues[key] = { code: 'VALIDATION_ERROR', message: raw }
      continue
    }
    if (!isRecord(raw)) {
      continue
    }
    const code = asString(raw.code, 'VALIDATION_ERROR')
    const allowed = stringArray(raw.allowed)
    const max = typeof raw.max === 'number' && Number.isFinite(raw.max) ? raw.max : undefined
    const issue: ProfileFieldIssue = {
      code,
      message: asString(raw.message) || ISSUE_COPY[code] || '请检查这项内容。',
    }
    if (allowed.length) {
      issue.allowed = allowed
    }
    if (max !== undefined) {
      issue.max = max
    }
    issues[key] = issue
  }
  return issues
}

/** 取单个字段的提示文案（不存在时为空串）。 */
export function issueText(
  issues: Record<string, ProfileFieldIssue>,
  key: string,
): string {
  return issues[key]?.message ?? ''
}

/** 顶部汇总：按字段 key 列出前几个待修改项。 */
export function issuesSummary(
  issues: Record<string, ProfileFieldIssue>,
  labels: Record<string, string> = {},
): string {
  const keys = Object.keys(issues)
  if (!keys.length) {
    return ''
  }
  const names = keys.slice(0, 4).map((key) => labels[key] ?? key)
  const rest = keys.length - names.length
  return `有 ${keys.length} 项需要修改：${names.join('、')}${rest > 0 ? ` 等 ${keys.length} 项` : ''}`
}

/** 联系方式（`GET/PUT /api/me/contact`，仅本人可见；docs/04 §4.1）。 */
export interface ContactInfo {
  qq: string | null
  wechat: string | null
  phone: string | null
  show_qq: boolean
  show_wechat: boolean
  show_phone: boolean
}

/** 写入用：省略的字段保持原值，显式 `null` 表示清空。 */
export interface ContactPatch {
  qq?: string | null
  wechat?: string | null
  phone?: string | null
  show_qq?: boolean
  show_wechat?: boolean
  show_phone?: boolean
}

function nullableString(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const text = value.trim()
  return text ? text : null
}

function asBool(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

export function normalizeContact(payload: unknown): ContactInfo {
  const source = isRecord(payload) ? payload : {}
  return {
    qq: nullableString(source.qq),
    wechat: nullableString(source.wechat),
    phone: nullableString(source.phone),
    show_qq: asBool(source.show_qq),
    show_wechat: asBool(source.show_wechat),
    show_phone: asBool(source.show_phone),
  }
}

/** GET /api/me/contact：唯一返回本人联系方式的接口。 */
export async function fetchContact(): Promise<ContactInfo> {
  const { data } = await api.get<unknown>('/me/contact')
  return normalizeContact(data)
}

/** PUT /api/me/contact：局部更新，`null` 清空。 */
export async function saveContact(patch: ContactPatch): Promise<ContactInfo> {
  const { data } = await api.put<unknown>('/me/contact', patch)
  return normalizeContact(data)
}
