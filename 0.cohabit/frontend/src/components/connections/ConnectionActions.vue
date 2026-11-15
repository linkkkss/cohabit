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
}>()

const hasActions = computed(
  () => props.actions.can_accept || props.actions.can_decline || props.actions.can_confirm || props.actions.can_cancel,
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
