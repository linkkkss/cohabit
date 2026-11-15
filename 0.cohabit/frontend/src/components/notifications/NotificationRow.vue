<script setup lang="ts">
import type { AppNotification } from '@/api/notifications'
import {
  notificationGlyph,
  notificationMeta,
  notificationTone,
  notificationTypeLabel,
  relativeTime,
} from './notificationFormat'

/** 单条通知行（通知页与铃铛下拉共用）。 */
const props = defineProps<{
  notification: AppNotification
  busy?: boolean
}>()

const emit = defineEmits<{
  open: [notification: AppNotification]
}>()

function onOpen(): void {
  if (!props.busy) {
    emit('open', props.notification)
  }
}
</script>

<template>
  <button
    type="button"
    class="notification-row"
    :class="[`tone-${notificationTone(notification.type)}`, { 'is-unread': !notification.read_at }]"
    :disabled="busy"
    @click="onOpen"
  >
    <span class="notification-glyph" aria-hidden="true">{{ notificationGlyph(notification.type) }}</span>
    <span class="notification-body">
      <span class="notification-kind">{{ notificationTypeLabel(notification.type) }}</span>
      <span class="notification-title">{{ notification.title }}</span>
      <span v-if="notificationMeta(notification)" class="notification-meta">{{ notificationMeta(notification) }}</span>
      <span class="notification-time">{{ relativeTime(notification.created_at) }}</span>
    </span>
    <span v-if="!notification.read_at" class="notification-dot" aria-label="未读"></span>
  </button>
</template>

<style scoped>
.notification-row {
  display: flex;
  gap: 12px;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--line);
  padding: 12px 6px;
  background: transparent;
  color: var(--ink);
  text-align: left;
  cursor: pointer;
  transition: background 120ms ease;
}

.notification-row:hover,
.notification-row:focus-visible {
  background: color-mix(in srgb, var(--sand) 48%, transparent);
}

.notification-row:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: -2px;
}

.notification-row:disabled {
  cursor: progress;
  opacity: 0.7;
}

.notification-row.is-unread {
  background: color-mix(in srgb, var(--sand) 26%, transparent);
}

.notification-glyph {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: none;
  border-radius: 999px;
  background: var(--sand);
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
}

.tone-coral .notification-glyph {
  background: color-mix(in srgb, var(--coral) 14%, var(--paper));
  color: var(--coral-dark);
}

.tone-ink .notification-glyph {
  background: var(--ink);
  color: var(--paper);
}

.notification-body {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.notification-kind {
  color: var(--muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.notification-title {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.notification-meta {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.notification-time {
  color: var(--muted);
  font-size: 11px;
}

.notification-dot {
  width: 7px;
  height: 7px;
  flex: none;
  align-self: center;
  border-radius: 999px;
  background: var(--coral);
}

@media (max-width: 640px) {
  .notification-row {
    padding: 12px 4px;
  }
}
</style>
