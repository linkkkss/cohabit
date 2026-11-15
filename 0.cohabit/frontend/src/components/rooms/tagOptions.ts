/**
 * 寝室标签词库（docs/03 §6.2）。
 *
 * 前端不硬编码 42 个标签，统一从问卷接口的 `tags` 字段取，并按后端顺序展示
 * （`fetchQuestionnaire()` 是幂等的只读接口，这里做一次进程内缓存）。
 */
import { fetchQuestionnaire, type TagOption } from '@/api/profiles'

let cache: Promise<TagOption[]> | null = null

export function loadRoomTagOptions(): Promise<TagOption[]> {
  if (!cache) {
    cache = fetchQuestionnaire()
      .then((questionnaire) => questionnaire.tags)
      .catch((error: unknown) => {
        // 失败不缓存，下次进入页面可以重试。
        cache = null
        throw error
      })
  }
  return cache
}

export function groupTagOptions(options: TagOption[]): { group: string; names: string[] }[] {
  const order: string[] = []
  const map = new Map<string, string[]>()
  for (const option of options) {
    if (!map.has(option.group)) {
      map.set(option.group, [])
      order.push(option.group)
    }
    map.get(option.group)?.push(option.name)
  }
  return order.map((group) => ({ group, names: map.get(group) ?? [] }))
}
