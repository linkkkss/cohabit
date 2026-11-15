<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
  NOTIFICATIONS_CHANGED_EVENT,
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
  notificationErrorMessage,
  notifyNotificationsChanged,
  type AppNotification,
} from '@/api/notifications'
import { useAuthStore } from '@/stores/auth'
import NotificationRow from './NotificationRow.vue'
import { badgeText, notificationPath } from './notificationFormat'

/**
 * 通知铃铛（docs/05 §4.4）：20–30s 轮询未读数，页面隐藏时暂停；
 * 下拉只放最近几条，所有通知在 /notifications。
 */
const POLL_MS = 25_000
const RECENT_LIMIT = 6

const auth = useAuthStore()
const router = useRouter()
const root = ref<HTMLElement | null>(null)
const open = ref(false)
const count = ref(auth.unreadCount)
const items = ref<AppNotification[]>([])
const loading = ref(false)
const error = ref('')
const busy = ref(false)

let pollTimer: number | null = null
let requestSeq = 0

const badge = computed(() => badgeText(count.value))
const buttonLabel = computed(() =>
  count.value > 0 ? `通知，${count.value} 条未读` : '通知，没有未读消息',
)
const disableMarkAll = computed(() => busy.value || count.value === 0)

watch(
  () => auth.unreadCount,
  (value) => {
    count.value = value
  },
)

watch(
  () => auth.isAuthenticated,
  (authenticated) => {
    if (!authenticated) {
      open.value = false
      stopPolling()
      count.value = 0
      items.value = []
      return
    }
    startPolling()
    void refreshCount()
  },
)

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(): void {
  stopPolling()
  if (!auth.isAuthenticated) {
    return
  }
  pollTimer = window.setInterval(() => {
    if (!document.hidden) {
      void refreshCount()
    }
  }, POLL_MS)
}

async function refreshCount(): Promise<void> {
  if (!auth.isAuthenticated) {
    return
  }
  try {
    count.value = await fetchUnreadCount()
  } catch {
    /* 铃铛轮询失败不打断页面，下一页再试。 */
  }
}

async function loadRecent(): Promise<void> {
  if (!auth.isAuthenticated) {
    return
  }
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const page = await fetchNotifications({ pageSize: RECENT_LIMIT })
    if (seq === requestSeq) {
      items.value = page.results
    }
  } catch (caught) {
    if (seq === requestSeq) {
      error.value = notificationErrorMessage(caught)
    }
  } finally {
    if (seq === requestSeq) {
      loading.value = false
    }
  }
}

function toggle(): void {
  open.value = !open.value
  if (open.value) {
    void refreshCount()
    void loadRecent()
  }
}

function close(): void {
  open.value = false
}

function onDocumentClick(event: MouseEvent): void {
  if (!open.value) {
    return
  }
  const target = event.target
  if (target instanceof Node && root.value && !root.value.contains(target)) {
    close()
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && open.value) {
    close()
  }
}

function onVisibilityChange(): void {
  if (document.hidden) {
    stopPolling()
    return
  }
  void refreshCount()
  startPolling()
  if (open.value) {
    void loadRecent()
  }
}

function onNotificationsChanged(): void {
  void refreshCount()
  if (open.value) {
    void loadRecent()
  }
}

async function markAll(): Promise<void> {
  if (disableMarkAll.value) {
    return
  }
  busy.value = true
  error.value = ''
  try {
    await markAllNotificationsRead()
    const now = new Date().toISOString()
    items.value = items.value.map((item) =>
      item.read_at ? item : { ...item, read_at: now },
    )
    count.value = 0
    notifyNotificationsChanged()
    await auth.fetchMe().catch(() => undefined)
  } catch (caught) {
    error.value = notificationErrorMessage(caught)
  } finally {
    busy.value = false
  }
}

async function openNotification(notification: AppNotification): Promise<void> {
  if (busy.value) {
    return
  }
  const target = notificationPath(notification)
  if (!notification.read_at) {
    busy.value = true
    try {
      const updated = await markNotificationRead(notification.id)
      items.value = items.value.map((item) => (item.id === updated.id ? updated : item))
      count.value = Math.max(0, count.value - 1)
      notifyNotificationsChanged()
      await auth.fetchMe().catch(() => undefined)
    } catch {
      /* 已读失败不阻止跳转。 */
    } finally {
      busy.value = false
    }
  }
  close()
  if (target) {
    void router.push(target)
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, onNotificationsChanged)
  startPolling()
  void refreshCount()
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, onNotificationsChanged)
})
</script>

<template>
  <div v-if="auth.isAuthenticated" ref="root" class="bell">
    <button
      type="button"
      class="bell-button"
      :class="{ 'is-open': open }"
      :aria-expanded="open"
      aria-haspopup="true"
      :aria-label="buttonLabel"
      :title="buttonLabel"
      @click="toggle"
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
        <path d="M10 21h4" />
      </svg>
      <span v-if="badge" class="badge-count bell-badge" aria-hidden="true">{{ badge }}</span>
    </button>

    <div v-if="open" class="bell-panel" role="dialog" aria-label="通知">
      <header class="bell-head">
        <div>
          <p class="eyebrow">Notifications</p>
          <h2 class="bell-title">通知</h2>
        </div>
        <button
          type="button"
          class="btn btn-small btn-ghost"
          :disabled="disableMarkAll"
          @click="markAll"
        >
          全部已读
        </button>
      </header>

      <p v-if="error" class="bell-error" role="alert">
        {{ error }}
        <button type="button" class="bell-retry" @click="loadRecent">重试</button>
      </p>

      <div v-if="loading && items.length === 0" class="bell-loading" aria-hidden="true">
        <span v-for="index in 3" :key="index" class="bell-skeleton"></span>
      </div>
      <p v-else-if="!items.length" class="bell-empty">
        还没有通知，新的动静会出现在这里。
      </p>
      <div v-else class="bell-list">
        <NotificationRow
          v-for="notification in items"
          :key="notification.id"
          :notification="notification"
          :busy="busy"
          @open="openNotification"
        />
      </div>

      <RouterLink class="bell-all" to="/notifications" @click="close">
        查看全部通知
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.bell {
  position: relative;
  display: flex;
  align-items: center;
}

.bell-button {
  position: relative;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}

.bell-button:hover,
.bell-button.is-open {
  border-color: var(--line);
  background: var(--sand);
}

.bell-button:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}

.bell-badge {
  position: absolute;
  top: -3px;
  right: -5px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 10px;
  line-height: 1;
}

.bell-panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 40;
  width: min(360px, calc(100vw - 24px));
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 16px;
  background: var(--paper);
  box-shadow: 0 24px 60px color-mix(in srgb, var(--ink) 14%, transparent);
}

.bell-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 8px;
}

.bell-title {
  margin: 2px 0 0;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
}

.bell-error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
  border: 1px solid color-mix(in srgb, var(--coral) 45%, var(--line));
  border-radius: 12px;
  padding: 10px 12px;
  color: var(--coral-dark);
  font-size: 12px;
}

.bell-retry {
  border: 0;
  padding: 0;
  background: none;
  color: inherit;
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}

.bell-loading {
  display: grid;
  gap: 8px;
  padding: 8px 0;
}

.bell-skeleton {
  height: 48px;
  border-radius: 10px;
  background: linear-gradient(90deg, var(--sand) 0%, #faf6f0 50%, var(--sand) 100%);
}

.bell-empty {
  margin: 0;
  padding: 24px 8px;
  color: var(--muted);
  font-size: 13px;
  text-align: center;
}

.bell-list {
  display: grid;
  max-height: min(380px, 60vh);
  overflow-y: auto;
  margin: 0 -6px;
  padding: 0 6px;
}

.bell-all {
  display: block;
  border-top: 1px solid var(--line);
  margin-top: 8px;
  padding-top: 12px;
  color: var(--ink);
  font-size: 13px;
  text-align: center;
}

.bell-all:hover {
  color: var(--coral-dark);
}

@media (max-width: 640px) {
  .bell-panel {
    position: fixed;
    top: 64px;
    right: 12px;
    left: 12px;
    width: auto;
    max-height: calc(100vh - 80px);
    overflow-y: auto;
  }

  .bell-button {
    width: 44px;
    height: 44px;
  }
}
</style>
