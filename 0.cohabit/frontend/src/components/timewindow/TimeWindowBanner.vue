<script setup lang="ts">
/**
 * 组寝时间窗横幅（WK-03 / P2-1；docs/04 §1.8、§3.13）。
 *
 * 由 AppShell 在 header 与 main 之间按登录态挂载，组件自己拉 `GET /api/timewindow/`：
 * - CLOSED：组寝窗口已关闭；
 * - UPCOMING：组寝窗口将在 N 天后开放；
 * - OPEN 且 days_until_end ≤ 7：组寝窗口将在 N 天后关闭；
 * - OPEN 且 > 7：不渲染，避免大半个学期都挂着一条横幅。
 *
 * 横幅只是辅助提示：加载中不占位，请求失败静默隐藏，绝不阻塞页面或弹错误。
 */
import { computed, onMounted, ref } from 'vue'
import { fetchTimeWindow, type TimeWindowState } from '@/api/timewindow'
import { useAuthStore } from '@/stores/auth'

/** 临近截止才提示，给同学留出最后一周的组寝时间。 */
const DAYS_LEFT_THRESHOLD = 7

const auth = useAuthStore()
const state = ref<TimeWindowState | null>(null)

/** 目前已知的三种阶段都按服务端阶段渲染，不在前端推导窗口是否开放。 */
const visible = computed(() => {
  if (!auth.isAuthenticated) {
    return false
  }
  const value = state.value
  if (!value) {
    return false
  }
  if (value.status === 'CLOSED') {
    return true
  }
  if (value.status === 'UPCOMING') {
    return value.days_until_start !== null
  }
  return value.days_until_end !== null && value.days_until_end <= DAYS_LEFT_THRESHOLD
})

const message = computed(() => {
  const value = state.value
  if (!value) {
    return ''
  }
  if (value.status === 'CLOSED') {
    return '组寝窗口已关闭'
  }
  if (value.status === 'UPCOMING' && value.days_until_start !== null) {
    return `组寝窗口将在 ${value.days_until_start} 天后开放`
  }
  if (value.status === 'OPEN' && value.days_until_end !== null) {
    return `组寝窗口将在 ${value.days_until_end} 天后关闭`
  }
  return ''
})

/** 本地时区 `M月D日 HH:mm`；无值或非法时间返回空串（整段日期就省略）。 */
function formatMonthDayTime(value: string | null): string {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  const pad = (part: number) => (part < 10 ? `0${part}` : String(part))
  return `${date.getMonth() + 1}月${date.getDate()}日 ${pad(date.getHours())}:${pad(
    date.getMinutes(),
  )}`
}

const dateText = computed(() => {
  const value = state.value
  if (!value) {
    return ''
  }
  if (value.status === 'UPCOMING') {
    const start = formatMonthDayTime(value.start_at)
    return start ? `开放时间 ${start}` : ''
  }
  if (value.status === 'OPEN') {
    const end = formatMonthDayTime(value.end_at)
    return end ? `截止时间 ${end}` : ''
  }
  if (value.status === 'CLOSED') {
    const end = formatMonthDayTime(value.end_at)
    return end ? `已于 ${end} 结束` : ''
  }
  return ''
})

const toneClass = computed(() => {
  if (state.value?.status === 'OPEN') {
    return 'is-closing'
  }
  return state.value?.status === 'UPCOMING' ? 'is-upcoming' : 'is-closed'
})

async function load(): Promise<void> {
  try {
    state.value = await fetchTimeWindow()
  } catch {
    // 横幅是锦上添花：失败就隐藏，不写 console、不弹提示、不影响页面其余部分。
    state.value = null
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div
    v-if="visible"
    class="timewindow-banner"
    :class="toneClass"
    role="status"
    aria-live="polite"
    aria-atomic="true"
  >
    <div class="container timewindow-inner">
      <span class="timewindow-dot" aria-hidden="true" />
      <p class="timewindow-text">
        <span class="timewindow-message">{{ message }}</span>
        <span v-if="dateText" class="timewindow-date">{{ dateText }}</span>
      </p>
    </div>
  </div>
</template>

<style scoped>
.timewindow-banner {
  border-bottom: 1px solid var(--sand-deep);
  background: var(--sand);
  color: var(--ink);
  font-size: 13px;
  line-height: 1.6;
}

.timewindow-inner {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding-block: 9px;
}

.timewindow-dot {
  width: 8px;
  height: 8px;
  flex: none;
  margin-top: 0.45em;
  border-radius: 999px;
  background: var(--muted);
}

.timewindow-text {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 10px;
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.timewindow-message {
  font-weight: 600;
}

.timewindow-date {
  color: var(--muted);
}

.is-upcoming {
  border-bottom-color: var(--sand-deep);
  background: var(--sand);
}

.is-upcoming .timewindow-dot {
  background: var(--coral);
}

.is-closing {
  border-bottom-color: #e8c9a8;
  background: #fbf1e6;
  color: #8a5a2b;
}

.is-closing .timewindow-dot {
  background: var(--coral-dark);
}

.is-closing .timewindow-date {
  color: #8a5a2b;
}

.is-closed {
  border-bottom-color: var(--line);
  background: color-mix(in srgb, var(--sand) 65%, var(--paper));
}
</style>
