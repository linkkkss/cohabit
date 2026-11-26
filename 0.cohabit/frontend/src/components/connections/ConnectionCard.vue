<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { ConnectionSummary } from '@/api/connections'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import { formatDateTime } from '@/components/rooms/roomFormat'
import ConnectionActions from './ConnectionActions.vue'
import DeadlineText from './DeadlineText.vue'
import {
  closeReasonText,
  connectionCounterpart,
  connectionPath,
  connectionStatusClass,
  connectionStatusLabel,
  connectionSummaryLine,
  connectionTypeLabel,
  counterpartLastActive,
  counterpartMeta,
  isTerminalStatus,
  lastActiveText,
} from './connectionFormat'

/**
 * 请求卡（docs/05 §4.4 `.request-card`）：
 * 左：头像 + 昵称 + 类型/状态；右：动作。终态卡片置灰但整卡仍可点开详情。
 */
const props = withDefaults(
  defineProps<{
    connection: ConnectionSummary
    busy?: boolean
  }>(),
  {
    busy: false,
  },
)

const emit = defineEmits<{
  (event: 'accept'): void
  (event: 'decline'): void
  (event: 'confirm'): void
  (event: 'cancel'): void
  (event: 'pre-approve'): void
}>()

const counterpart = computed(() => connectionCounterpart(props.connection))
const name = computed(() => counterpart.value?.nickname || '对方')
const meta = computed(() => counterpartMeta(counterpart.value))
const statusLabel = computed(() =>
  connectionStatusLabel(props.connection.status, props.connection.direction),
)
const statusClass = computed(() => connectionStatusClass(props.connection.status))
const typeLabel = computed(() => connectionTypeLabel(props.connection.type))
const summaryLine = computed(() => connectionSummaryLine(props.connection))
const closed = computed(() => isTerminalStatus(props.connection.status))
const open = computed(() => !closed.value)
const roomCode = computed(() => props.connection.room?.code || '')
const contactSharedAt = computed(() =>
  props.connection.contact_shared_at ? formatDateTime(props.connection.contact_shared_at) : '',
)
const showContactHint = computed(
  () =>
    props.connection.status === 'CONTACT_SHARED' ||
    props.connection.status === 'CONFIRMING' ||
    props.connection.status === 'CONFIRMED',
)
const cardLabel = computed(
  () => `${name.value} 的${typeLabel.value}，${statusLabel.value}，打开详情`,
)
/** 关闭原因：只在终态出现，让列表也能回答“这次为什么没成”。 */
const closeText = computed(() =>
  closed.value ? closeReasonText(props.connection.close_reason) : '',
)
/** 发起人已经先确认时，提示“点一下就成”。 */
const preApproveHint = computed(() => {
  if (!open.value || !props.connection.initiator_pre_approved) {
    return ''
  }
  return props.connection.direction === 'sent' ? '你已先同意' : '对方已先同意'
})
const otherActive = computed(() =>
  open.value ? lastActiveText(counterpartLastActive(props.connection)) : '',
)
</script>

<template>
  <article class="request-card connection-card" :class="{ 'is-closed': closed }">
    <RouterLink class="request-main connection-main" :to="connectionPath(connection.id)" :aria-label="cardLabel">
      <AvatarBadge :name="name" size="md" />
      <div class="request-copy">
        <div class="request-head">
          <span class="request-name">{{ name }}</span>
          <span class="chip connection-type">{{ typeLabel }}</span>
          <span class="status connection-status" :class="statusClass">{{ statusLabel }}</span>
        </div>
        <p class="request-line">{{ summaryLine }}</p>
        <p v-if="connection.message" class="request-message">{{ connection.message }}</p>
        <div class="request-meta">
          <span v-if="meta">{{ meta }}</span>
          <span v-if="roomCode" class="room-code">#{{ roomCode }}</span>
          <DeadlineText v-if="open" :expires-at="connection.expires_at" />
          <span v-else-if="contactSharedAt" class="request-time">互见于 {{ contactSharedAt }}</span>
          <span v-if="showContactHint" class="request-contact-hint">联系方式已解锁</span>
          <span v-if="preApproveHint" class="request-contact-hint pre-hint">{{ preApproveHint }}</span>
          <span v-if="closeText" class="request-close-reason">{{ closeText }}</span>
          <span v-else-if="otherActive" class="request-time">{{ otherActive }}</span>
        </div>
      </div>
    </RouterLink>

    <ConnectionActions
      :actions="connection.actions"
      :status="connection.status"
      :busy="busy"
      @accept="emit('accept')"
      @decline="emit('decline')"
      @confirm="emit('confirm')"
      @cancel="emit('cancel')"
      @pre-approve="emit('pre-approve')"
    />
  </article>
</template>

<style scoped>
.connection-card {
  align-items: flex-start;
}

.connection-card.is-closed {
  background: color-mix(in srgb, var(--sand) 45%, var(--paper));
}

.connection-card.is-closed .connection-main {
  opacity: 0.78;
}

.connection-main {
  min-width: 0;
  flex: 1 1 320px;
  align-items: flex-start;
}

.request-copy {
  min-width: 0;
}

.request-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.request-name {
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 500;
  line-height: 1.3;
}

.connection-type {
  background: var(--paper);
  color: var(--muted);
  font-size: 11px;
}

.connection-status {
  font-size: 11px;
}

.status-pending {
  background: #fbf1e6;
  color: #8a5a2b;
}

.status-shared {
  background: #ecf4ec;
  color: #356b3b;
}

.status-confirmed {
  background: var(--ink);
  color: var(--paper);
}

.status-closed {
  background: #f1f1ef;
  color: #555;
}

.request-line {
  margin: 6px 0 0;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.6;
}

.request-message {
  display: -webkit-box;
  overflow: hidden;
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.request-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 12px;
}

.request-contact-hint {
  border: 1px solid color-mix(in srgb, var(--coral) 35%, var(--line));
  border-radius: 999px;
  padding: 2px 8px;
  color: var(--coral-dark);
  font-size: 11px;
}

.pre-hint {
  border-color: color-mix(in srgb, var(--sage, #4f8a6d) 40%, var(--line));
  color: var(--sage-dark, #2f6149);
}

.request-close-reason {
  border-radius: 999px;
  padding: 2px 8px;
  background: #f1f1ef;
  color: #555;
  font-size: 11px;
}

@media (max-width: 640px) {
  .connection-card {
    flex-direction: column;
    align-items: stretch;
  }

  .connection-main {
    width: 100%;
    flex: 0 0 auto;
  }

  .connection-card :deep(.request-actions) {
    width: 100%;
  }
}
</style>
