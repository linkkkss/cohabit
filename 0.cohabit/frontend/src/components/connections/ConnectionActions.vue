<script setup lang="ts">
import { computed } from 'vue'
import type { ConnectionActions, ConnectionStatus } from '@/api/connections'
import { cancelLabel, confirmLabel } from './connectionFormat'

/**
 * 请求动作区（docs/05 §4.4 `.request-actions`）。
 * 只渲染服务端 `actions` 允许的按钮：不可执行的动作隐藏，不置灰。
 */
const props = withDefaults(
  defineProps<{
    actions: ConnectionActions
    status: ConnectionStatus
    busy?: boolean
    size?: 'sm' | 'md'
  }>(),
  {
    busy: false,
    size: 'sm',
  },
)

const emit = defineEmits<{
  (event: 'accept'): void
  (event: 'decline'): void
  (event: 'confirm'): void
  (event: 'cancel'): void
  (event: 'pre-approve'): void
}>()

const hasActions = computed(
  () =>
    props.actions.can_accept ||
    props.actions.can_decline ||
    props.actions.can_confirm ||
    props.actions.can_cancel ||
    props.actions.can_pre_approve,
)

const buttonClass = computed(() => (props.size === 'md' ? 'btn' : 'btn btn-small'))
</script>

<template>
  <div v-if="hasActions" class="request-actions connection-actions" :class="{ 'is-busy': busy }">
    <button
      v-if="actions.can_accept"
      type="button"
      :class="[buttonClass, 'btn-primary']"
      :disabled="busy"
      @click="emit('accept')"
    >
      同意
    </button>
    <button
      v-if="actions.can_decline"
      type="button"
      :class="[buttonClass, 'btn-ghost']"
      :disabled="busy"
      @click="emit('decline')"
    >
      拒绝
    </button>
    <button
      v-if="actions.can_confirm"
      type="button"
      :class="[buttonClass, 'btn-primary']"
      :disabled="busy"
      @click="emit('confirm')"
    >
      {{ confirmLabel(status) }}
    </button>
    <button
      v-if="actions.can_pre_approve"
      type="button"
      :class="[buttonClass, 'btn-ghost', 'btn-pre']"
      :disabled="busy"
      title="先记下你的同意；对方上线后点一次“同意”就直接成立组寝，不必同时在线"
      @click="emit('pre-approve')"
    >
      我先同意
    </button>
    <button
      v-if="actions.can_cancel"
      type="button"
      :class="[buttonClass, 'btn-ghost', 'btn-end']"
      :disabled="busy"
      @click="emit('cancel')"
    >
      {{ cancelLabel(status) }}
    </button>
  </div>
</template>

<style scoped>
.connection-actions {
  justify-content: flex-end;
}

.btn-end {
  border-color: color-mix(in srgb, var(--coral) 45%, var(--line));
  color: var(--coral-dark);
}

.btn-end:hover {
  border-color: var(--coral-dark);
}

/* “我先同意”是主动作的前置一步，用低饱和强调色区别于撤回/拒绝。 */
.btn-pre {
  border-color: color-mix(in srgb, var(--sage, #4f8a6d) 40%, var(--line));
  color: var(--sage-dark, #2f6149);
}

.btn-pre:hover {
  border-color: var(--sage-dark, #2f6149);
}

@media (max-width: 640px) {
  .connection-actions {
    width: 100%;
  }

  .connection-actions .btn {
    flex: 1 1 140px;
    min-height: 44px;
  }
}
</style>
