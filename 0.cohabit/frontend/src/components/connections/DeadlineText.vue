<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { connectionDeadline } from './connectionFormat'

/**
 * 截止时间提示（docs/05 §4.4 `.deadline`）。
 * 每 30s 重算一次即可：老师不需要秒级倒计时，减少列表里的定时器开销。
 */
const props = withDefaults(
  defineProps<{
    expiresAt: string | null
  }>(),
  {},
)

const now = ref(Date.now())
let timer: number | null = null

const text = computed(() => {
  // 显式读取 now，让 30s 的 tick 触发重算。
  void now.value
  return connectionDeadline(props.expiresAt)
})

const expired = computed(() => text.value === '已过期')

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
  <span class="deadline" :class="{ 'is-expired': expired }">{{ text }}</span>
</template>

<style scoped>
.deadline {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.5;
  white-space: nowrap;
}

.deadline.is-expired {
  color: var(--coral-dark);
}
</style>
