/**
 * 画像完整度（docs/03 §2.6、docs/05 §2.6）。
 *
 * 完整度由服务端落库并在 `Profile.completeness` 返回，本文件只做「展示用拆解」：
 * 规则逐条镜像 `backend/apps/profiles/completeness.py`，总分 = 六个分块之和，
 * 保存成功后与接口返回的 `completeness` 一致；若哪天规则变了，以接口数字为准。
 */
import {
  MAX_PROMPTS,
  MAX_TAGS,
  MIN_PROMPTS,
  MIN_TAGS,
  PROMPT_MAX_LENGTH,
  type BasicProfile,
  type Profile,
  type Questionnaire,
} from '@/api/profiles'

export interface SectionScore {
  key: 'basic' | 'hard' | 'soft' | 'red_lines' | 'tags' | 'prompts'
  label: string
  score: number
  max: number
  /** 未拿满时给一句「还差什么」，拿满为空。 */
  hint: string
}

export interface CompletenessReport {
  sections: SectionScore[]
  /** 与服务端 `Profile.completeness` 对齐的总分。 */
  total: number
  /** 距离可匹配还差多少（0 表示已可匹配）。 */
  remaining: number
  missing: string[]
}

const GRADE_RANGE = [1, 5] as const

function hasText(value: string | null | undefined): boolean {
  return typeof value === 'string' && value.trim() !== ''
}

/** 镜像 `_basic_score`：五个字段各 4 分。 */
function basicScore(basic: BasicProfile): { score: number; missing: string[] } {
  const missing: string[] = []
  let score = 0
  if (hasText(basic.nickname)) {
    score += 4
  } else {
    missing.push('昵称')
  }
  if (basic.gender === 'MALE' || basic.gender === 'FEMALE') {
    score += 4
  } else {
    missing.push('性别')
  }
  const grade = basic.grade
  if (typeof grade === 'number' && grade >= GRADE_RANGE[0] && grade <= GRADE_RANGE[1]) {
    score += 4
  } else {
    missing.push('年级')
  }
  if (hasText(basic.college)) {
    score += 4
  } else {
    missing.push('学院')
  }
  if (hasText(basic.major)) {
    score += 4
  } else {
    missing.push('专业')
  }
  return { score, missing }
}

/** 镜像 `prompt_is_valid`：去空白后 1–120 字且不超过 3 行。 */
export function promptIsValid(value: string, maxLength = PROMPT_MAX_LENGTH): boolean {
  const text = value.trim()
  if (text.length < 1 || text.length > maxLength) {
    return false
  }
  return text.split(/\r\n|\r|\n/).length <= 3
}

/** 镜像 `_prompts_section_score` 的计数规则，供编辑器实时显示「已填 n/最少 2」。 */
export function filledPromptCount(prompts: Record<string, string>): number {
  return Object.values(prompts).filter((value) => promptIsValid(value)).length
}

export function buildCompletenessReport(
  profile: Profile,
  basic: BasicProfile,
  questionnaire: Questionnaire | null,
): CompletenessReport {
  const hardKeys = questionnaire?.hard.map((item) => item.key) ?? []
  const softKeys = questionnaire?.soft.map((item) => item.key) ?? Object.keys(profile.soft_answers)
  const promptKeys = new Set(questionnaire?.prompts.map((item) => item.key) ?? [])
  const promptMaxLengths = new Map(
    (questionnaire?.prompts ?? []).map((item) => [item.key, item.max_length] as const),
  )

  const basicResult = basicScore(basic)
  // 题库加载失败时退回「已答 key 数量」判断，避免空数组 every() 恒真直接给 20 分。
  const hardAnswered = hardKeys.length
    ? hardKeys.every((key) => hasText(profile.hard_answers[key]))
    : Object.keys(profile.hard_answers).length >= 11
  const softAnswered = softKeys.filter((key) => {
    const value = profile.soft_answers[key]
    return typeof value === 'number' && value >= 1 && value <= 5
  })
  const tagsOk =
    profile.tags.length >= MIN_TAGS && profile.tags.length <= MAX_TAGS
  const promptsFilled = Object.entries(profile.prompts).filter(([key, value]) => {
    if (promptKeys.size && !promptKeys.has(key)) {
      return false
    }
    return promptIsValid(value, promptMaxLengths.get(key) ?? PROMPT_MAX_LENGTH)
  }).length
  const promptsOk = promptsFilled >= MIN_PROMPTS && promptsFilled <= MAX_PROMPTS

  const sections: SectionScore[] = [
    {
      key: 'basic',
      label: '基础资料',
      score: basicResult.score,
      max: 20,
      hint: basicResult.missing.length ? `还缺：${basicResult.missing.join('、')}` : '',
    },
    {
      key: 'hard',
      label: '硬指标',
      score: hardAnswered ? 20 : 0,
      max: 20,
      hint: hardAnswered ? '' : `11 题要全部作答（已答 ${hardKeys.filter((key) => hasText(profile.hard_answers[key])).length} 题）`,
    },
    {
      key: 'soft',
      label: '软指标',
      score: softAnswered.length * 5,
      max: 30,
      hint: softAnswered.length === softKeys.length ? '' : `每答 1 题得 5 分（已答 ${softAnswered.length}/${softKeys.length}）`,
    },
    {
      key: 'red_lines',
      label: '红线确认',
      score: profile.red_lines_confirmed ? 10 : 0,
      max: 10,
      hint: profile.red_lines_confirmed ? '' : '需要点一次「确认红线」',
    },
    {
      key: 'tags',
      label: '标签',
      score: tagsOk ? 10 : 0,
      max: 10,
      hint: tagsOk ? '' : `选 ${MIN_TAGS}–${MAX_TAGS} 个（已选 ${profile.tags.length}）`,
    },
    {
      key: 'prompts',
      label: '自述',
      score: promptsOk ? 10 : 0,
      max: 10,
      hint: promptsOk ? '' : `填 ${MIN_PROMPTS}–${MAX_PROMPTS} 题（已填 ${promptsFilled}）`,
    },
  ]

  const total = Math.max(
    0,
    Math.min(
      100,
      sections.reduce((sum, section) => sum + section.score, 0),
    ),
  )
  const missing: string[] = []
  if (basicResult.missing.length) {
    missing.push(...basicResult.missing)
  }
  if (!hardAnswered) {
    missing.push('硬指标未答全')
  }
  if (softAnswered.length < softKeys.length) {
    missing.push('软指标未答全')
  }
  if (!profile.red_lines_confirmed) {
    missing.push('红线未确认')
  }
  if (!tagsOk) {
    missing.push('标签数量不达标')
  }
  if (!promptsOk) {
    missing.push('自述不足 2 题')
  }

  return {
    sections,
    total,
    remaining: Math.max(0, 100 - total),
    missing,
  }
}
