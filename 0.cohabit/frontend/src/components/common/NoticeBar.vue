<script setup lang="ts">
/**
 * 提示条（docs/05 §4.2 `.notice`）：左侧 3px 色条 + 浅色底，不抢主强调。
 * tone=error 用 role="alert"，其余用 role="status"，读屏只在内容变化时播报。
 */
withDefaults(
  defineProps<{
    tone?: 'info' | 'warn' | 'error'
    title?: string
  }>(),
  {
    tone: 'info',
    title: '',
  },
)
</script>

<template>
  <div
    class="notice"
    :class="`notice-${tone}`"
    :role="tone === 'error' ? 'alert' : 'status'"
  >
    <strong v-if="title" class="notice-title">{{ title }}</strong>
    <div class="notice-body"><slot></slot></div>
  </div>
</template>

<style scoped>
.notice {
  display: grid;
  gap: 6px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--sand);
  color: var(--ink);
  font-size: 13px;
  line-height: 1.7;
}

.notice-title {
  font-size: 13px;
  font-weight: 700;
}

.notice-body :deep(p) {
  margin: 0;
}

.notice-body :deep(p + p) {
  margin-top: 6px;
}

.notice-warn {
  border-left-color: color-mix(in srgb, var(--coral) 55%, var(--ink));
  background: color-mix(in srgb, var(--coral) 9%, var(--paper));
}

.notice-error {
  border-left-color: var(--coral-dark);
  background: color-mix(in srgb, var(--coral) 13%, var(--paper));
}

.notice-error .notice-title {
  color: var(--coral-dark);
}
</style>
