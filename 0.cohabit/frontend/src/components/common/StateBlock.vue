<script setup lang="ts">
/**
 * 列表三态（docs/05 §4.2、V-07）：加载骨架 / 错误 + 重试 / 空态。
 * 文案由调用方传入，默认值取 docs/05 §8.2 的服务错误口径。
 */
withDefaults(
  defineProps<{
    status: 'loading' | 'error' | 'empty'
    title?: string
    message?: string
    rows?: number
    retryLabel?: string
  }>(),
  {
    title: '',
    message: '',
    rows: 3,
    retryLabel: '重新加载',
  },
)

const emit = defineEmits<{ (event: 'retry'): void }>()
</script>

<template>
  <div v-if="status === 'loading'" class="skeleton-grid" role="status" aria-live="polite">
    <span class="sr-only">正在加载，请稍候。</span>
    <div v-for="index in rows" :key="index" class="skeleton-card" aria-hidden="true">
      <div class="skeleton-line skeleton-line-title"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line skeleton-line-short"></div>
      <div class="skeleton-line skeleton-line-short"></div>
    </div>
  </div>

  <div v-else-if="status === 'error'" class="state-error" role="alert">
    <p class="state-error-text">{{ message || '出了点问题，请稍后重试。' }}</p>
    <button class="btn btn-small btn-ghost" type="button" @click="emit('retry')">
      {{ retryLabel }}
    </button>
  </div>

  <div v-else class="empty">
    <strong>{{ title || '暂时没有内容' }}</strong>
    <p v-if="message" class="state-empty-copy">{{ message }}</p>
    <slot></slot>
  </div>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.skeleton-card {
  display: grid;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 20px;
  background: var(--paper);
}

.skeleton-line {
  height: 12px;
  border-radius: 999px;
  background: var(--sand);
  animation: skeleton-pulse 1.4s ease-in-out infinite;
}

.skeleton-line-title {
  width: 60%;
  height: 20px;
}

.skeleton-line-short {
  width: 42%;
}

@keyframes skeleton-pulse {
  0%,
  100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}

.state-error {
  display: grid;
  gap: 12px;
  justify-items: start;
  border: 1px solid var(--line);
  border-left: 3px solid var(--coral-dark);
  border-radius: 14px;
  background: color-mix(in srgb, var(--coral) 8%, var(--paper));
  padding: 18px 20px;
}

.state-error-text {
  margin: 0;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.6;
}

.state-empty-copy {
  max-width: 46ch;
  margin: 0 auto 14px;
  line-height: 1.7;
}

@media (max-width: 920px) {
  .skeleton-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .skeleton-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-line {
    animation: none;
  }
}
</style>
