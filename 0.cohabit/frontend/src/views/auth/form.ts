import { apiErrorFields } from '@/api/client'

export const FIELD_LABELS: Record<string, string> = {
  email: '邮箱',
  code: '验证码',
  password: '密码',
  nickname: '昵称',
  gender: '性别',
  grade: '年级',
  college: '学院',
  major: '专业',
  invite_code: '邀请码',
}

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field
}

/** 把后端 `detail.fields` 的数组压成“字段 → 第一条提示”。 */
export function toFieldErrors(error: unknown): Record<string, string> {
  const fields = apiErrorFields(error)
  const result: Record<string, string> = {}
  for (const [field, messages] of Object.entries(fields)) {
    result[field] = messages[0] || '请检查该项'
  }
  return result
}

/** docs/05 §8.3：VALIDATION_ERROR 在顶部汇总字段名。 */
export function validationSummary(errors: Record<string, string>): string {
  const names = Object.keys(errors).map(fieldLabel)
  return names.length ? `有字段需要修改：${names.join('、')}` : '有字段需要修改，请检查后再提交。'
}

export function isEmailLike(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}
