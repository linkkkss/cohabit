<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import { useAuthStore } from '@/stores/auth'
import NotificationRow from '@/components/notifications/NotificationRow.vue'
import {
  notificationEmptyCopy,
  notificationPath,
} from '@/components/notifications/notificationFormat'

/**
 * 通知中心（docs/04 §4.5）：全部 / 未读筛选、单条与全部已读、加载更多。
 * 点击通知先标记已读再按 payload 跳转；页面隐藏时暂停可见性刷新。
 */
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

type Filter = 'all' | 'unread'
type ViewState = 'loading' | 'ready' | 'error'

const filter = ref<Filter>(route.query.unread === '1' ? 'unread' : 'all')
const state = ref<ViewState>('loading')
const items = ref<AppNotification[]>([])
const total = ref(0)
const page = ref(1)
const unreadCount = ref(auth.unreadCount)
const error = ref('')
const notice = ref('')
const loadingMore = ref(false)
const busyId = ref<number | null>(null)
const markingAll = ref(false)

const hasMore = computed(() => items.value.length < total.value)
const unreadOnly = computed(() => filter.value === 'unread')
const disableMarkAll = computed(() => markingAll.value || unreadCount.value === 0)

async function refreshUnread(): Promise<void> {
  try {
    unreadCount.value = await fetchUnreadCount()
  } catch {
    /* 未读数失败不打断列表。 */
  }
}

async function load(reset: boolean): Promise<void> {
  if (reset) {
    state.value = 'loading'
    error.value = ''
    notice.value = ''
  }
  const nextPage = reset ? 1 : page.value + 1
  loadingMore.value = !reset
  try {
    const data = await fetchNotifications({
      unread: unreadOnly.value,
      page: nextPage,
      pageSize: 20,
    })
    items.value = reset ? data.results : [...items.value, ...data.results]
    page.value = nextPage
    total.value = data.count
    state.value = 'ready'
  } catch (caught) {
    if (reset) {
      error.value = notificationErrorMessage(caught)
      state.value = 'error'
    } else {
      notice.value = notificationErrorMessage(caught, '加载更多失败，请稍后重试。')
    }
  } finally {
    loadingMore.value = false
  }
}

function setFilter(next: Filter): void {
  if (filter.value === next) {
    return
  }
  filter.value = next
  void router.replace({ query: next === 'unread' ? { unread: '1' } : {} })
  void load(true)
}

async function markAll(): Promise<void> {
  if (disableMarkAll.value) {
    return
  }
  markingAll.value = true
  notice.value = ''
  try {
    await markAllNotificationsRead()
    const now = new Date().toISOString()
    if (unreadOnly.value) {
      items.value = []
      total.value = 0
    } else {
      items.value = items.value.map((item) =>
        item.read_at ? item : { ...item, read_at: now },
      )
    }
    unreadCount.value = 0
    notifyNotificationsChanged()
    notice.value = '所有通知已标记为已读。'
    await auth.fetchMe().catch(() => undefined)
  } catch (caught) {
    notice.value = notificationErrorMessage(caught, '没有标记成功，请稍后再试。')
  } finally {
    markingAll.value = false
  }
}

async function openNotification(notification: AppNotification): Promise<void> {
  if (busyId.value !== null) {
    return
  }
  const target = notificationPath(notification)
  if (!notification.read_at) {
    busyId.value = notification.id
    try {
      const updated = await markNotificationRead(notification.id)
      items.value = items.value.map((item) => (item.id === updated.id ? updated : item))
      unreadCount.value = Math.max(0, unreadCount.value - 1)
      notifyNotificationsChanged()
      await auth.fetchMe().catch(() => undefined)
    } catch (caught) {
      notice.value = notificationErrorMessage(caught, '标记已读失败，但可以先查看内容。')
    } finally {
      busyId.value = null
    }
  }
  if (target) {
    void router.push(target)
  }
}

function onNotificationsChanged(): void {
  void refreshUnread()
  if (!document.hidden) {
    void load(true)
  }
}

function onVisibilityChange(): void {
  if (document.hidden) {
    return
  }
  void refreshUnread()
  void load(true)
}

onMounted(() => {
  window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, onNotificationsChanged)
  document.addEventListener('visibilitychange', onVisibilityChange)
  void Promise.all([load(true), refreshUnread()])
})

onBeforeUnmount(() => {
  window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, onNotificationsChanged)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="container notifications-page">
    <header class="page-head notifications-head">
      <div>
        <p class="eyebrow">Messages</p>
        <h1>通知</h1>
        <p class="lede">组寝请求、联系方式和寝室的动静都在这里。</p>
      </div>
      <button
        type="button"
        class="btn btn-small btn-ghost"
        :disabled="disableMarkAll"
        @click="markAll"
      >
        {{ markingAll ? '正在标记…' : '全部已读' }}
      </button>
    </header>

    <NoticeBar v-if="notice" tone="info">
      <p>{{ notice }}</p>
    </NoticeBar>

    <div class="toolbar notification-toolbar">
      <div class="tabs" role="tablist" aria-label="通知筛选">
        <button
          type="button"
          class="tab"
          :class="{ active: filter === 'all' }"
          role="tab"
          :aria-selected="filter === 'all'"
          @click="setFilter('all')"
        >
          全部
          <span v-if="!unreadOnly && total" class="tab-count">{{ total }}</span>
        </button>
        <button
          type="button"
          class="tab"
          :class="{ active: filter === 'unread' }"
          role="tab"
          :aria-selected="filter === 'unread'"
          @click="setFilter('unread')"
        >
          未读
          <span v-if="unreadCount" class="tab-count">{{ unreadCount }}</span>
        </button>
      </div>
    </div>

    <StateBlock
      v-if="state === 'loading'"
      status="loading"
      :rows="1"
      title="正在加载通知"
    />

    <StateBlock
      v-else-if="state === 'error'"
      status="error"
      :message="error"
      @retry="load(true)"
    />

    <div v-else-if="!items.length" class="empty notification-empty">
      <strong>{{ notificationEmptyCopy(unreadOnly) }}</strong>
      <p class="fine">
        {{ unreadOnly
          ? '查看全部通知，或者去匹配页看看新的组寝请求。'
          : '组寝请求、联系方式和寝室的动静会出现在这里。' }}
      </p>
      <RouterLink class="btn btn-small btn-ghost" to="/match">去匹配页看看</RouterLink>
    </div>

    <div v-else class="notification-list">
      <NotificationRow
        v-for="notification in items"
        :key="notification.id"
        :notification="notification"
        :busy="busyId === notification.id"
        @open="openNotification"
      />
      <button
        v-if="hasMore"
        type="button"
        class="btn btn-small btn-ghost load-more"
        :disabled="loadingMore"
        @click="load(false)"
      >
        {{ loadingMore ? '正在加载…' : `加载更多（${items.length} / ${total}）` }}
      </button>
    </div>

    <p class="fine notification-privacy">
      通知只包含必要的昵称、房间号和原因，不会包含联系方式。
    </p>
  </div>
</template>

<style scoped>
.notifications-page {
  display: grid;
  gap: 16px;
  padding-top: 36px;
  padding-bottom: 56px;
}

.notifications-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.notifications-head h1 {
  margin: 4px 0 6px;
  font-family: var(--font-serif);
  font-size: clamp(30px, 3.6vw, 42px);
  font-weight: 500;
  letter-spacing: -0.015em;
}

.notification-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  margin-left: 4px;
  border-radius: 999px;
  padding: 0 6px;
  background: var(--sand);
  color: var(--muted);
  font-size: 10px;
  line-height: 1;
}

.tab.active .tab-count {
  background: var(--ink);
  color: var(--paper);
}

.notification-list {
  display: grid;
  border: 1px solid var(--line);
  border-radius: 18px;
  overflow: hidden;
  background: var(--paper);
}

.notification-empty {
  display: grid;
  justify-items: center;
  gap: 10px;
  border: 1px dashed var(--line);
  border-radius: 18px;
  padding: 48px 20px;
}

.notification-empty strong {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.notification-empty .fine {
  margin: 0;
  text-align: center;
}

.load-more {
  margin: 10px 12px 14px;
}

.notification-privacy {
  margin: 0;
  text-align: center;
}

@media (max-width: 640px) {
  .notifications-page {
    padding-top: 24px;
  }

  .notifications-head {
    align-items: flex-start;
  }

  .notifications-head .btn {
    width: 100%;
  }
}
</style>
