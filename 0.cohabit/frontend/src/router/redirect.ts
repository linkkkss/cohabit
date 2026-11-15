import type { useAuthStore } from '@/stores/auth'

/**
 * 只接受站内绝对路径，拒绝 `//evil.com`、`https://…`、反斜杠等开放重定向写法。
 */
export function safeRedirect(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }
  const target = value.trim()
  if (!target.startsWith('/') || target.startsWith('//')) {
    return null
  }
  if (target.includes('://') || target.includes('\\')) {
    return null
  }
  return target
}

/**
 * 登录/注册后的落点：优先回到被拦截的站内页面；
 * 否则画像未完成 → 问卷，已入寝 → 我的寝室，其他 → 匹配页。
 */
export function resolveAuthRedirect(
  auth: ReturnType<typeof useAuthStore>,
  redirect?: unknown,
): string {
  const target = safeRedirect(redirect)
  if (target) {
    return target
  }
  if (!auth.isProfileComplete) {
    return '/onboarding'
  }
  if (auth.hasRoom) {
    return '/rooms'
  }
  return '/match'
}
