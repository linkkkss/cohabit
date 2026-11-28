<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { ConnectionStatus } from '@/api/connections'
import { connectionDeadline, phaseElapsedRatio, phaseWindowLabel } from './connectionFormat'

/**
 * 阶段倒计时进度条（规则页「一次组寝的完整流程」的可视化）。
 *
 * 四步进度说明「走到哪一步」，这条进度条说明「这一步还剩多久」。
 * 服务端每次进入阶段都会把 `expires_at` 写成「现在 + 窗口」，
 * 所以比例可以由 `expires_at` 反推，不需要额外接口。
 */
const props = defineProps<{
  status: ConnectionStatus
  expiresAt: string | null
}>()

const now = ref(Date.now())
let timer: number | null = null

const windowLabel = computed(() => phaseWindowLabel(props.status))
const remaining = computed(() => connectionDeadline(props.expiresAt))
const known = computed(() => remaining.value !== '时间未知')
const expired = computed(() => remaining.value === '已过期')

/** 填充条表示「剩余」，随时间收缩，比「已用」更符合倒计时直觉。 */
const ratio = computed(() => {
  // 显式读取 now，让 30s 的 tick 触发重算。
  void now.value
  if (!known.value || expired.value) {
    return 0
  }
  return 1 - phaseElapsedRatio(props.status, props.expiresAt)
})

/** 最后 1/8（48 小时 → 最后 6 小时）转为警示色。 */
const urgent = computed(() => !expired.value && ratio.value <= 0.125)

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = Date.now()
  }, 30_000)
})

onBeforeUnmount(() => {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <div class="deadline-progress" :class="{ 'is-urgent': urgent, 'is-expired': expired }">
    <div
      class="dp-track"
      role="progressbar"
      aria-label="本阶段剩余时间"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="Math.round(ratio * 100)"
      :aria-valuetext="expired ? '已超时' : remaining"
    >
      <span class="dp-fill" :style="{ width: `${ratio * 100}%` }"></span>
    </div>
    <p class="fine dp-copy">
      <template v-if="expired">已超过截止时间，正在等待系统关闭这条请求。</template>
      <template v-else-if="known">{{ remaining }}关闭</template>
      <template v-else>截止时间待确认</template>
      <RouterLink class="dp-link" :to="{ name: 'rules', hash: '#timeline' }">
        为什么是 {{ windowLabel }}？
      </RouterLink>
    </p>
  </div>
</template>

<style scoped>
.deadline-progress {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}

.dp-track {
  height: 3px;
  border-radius: 999px;
  background: var(--line);
  overflow: hidden;
}

.dp-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--ink);
  transition: width 0.3s ease;
}

.is-urgent .dp-fill {
  background: var(--coral);
}

.is-expired .dp-fill {
  background: var(--coral-dark);
}

.dp-copy {
  margin: 0;
  color: var(--muted);
}

.dp-link {
  margin-left: 8px;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.dp-link:hover {
  color: var(--ink);
}

@media (prefers-reduced-motion: reduce) {
  .dp-fill {
    transition: none;
  }
}
</style>
