<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { apiErrorStatus } from '@/api/client'
import {
  acceptConnection,
  cancelConnection,
  connectionErrorMessage,
  declineConnection,
  fetchConnections,
  preApproveConnection,
  type ConnectionStatus,
  type ConnectionSummary,
} from '@/api/connections'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import ConfirmDialog from '@/components/rooms/ConfirmDialog.vue'
import ConnectionCard from '@/components/connections/ConnectionCard.vue'
import ConnectionDetailPanel from '@/components/connections/ConnectionDetailPanel.vue'
import { connectionCounterpart, connectionPath } from '@/components/connections/connectionFormat'
import SecurityActions from '@/components/security/SecurityActions.vue'

/**
 * 请求列表（docs/04 §4.4；docs/05 §7.2）：收到的 / 发出的两个 tab，
 * 状态筛选只作为查询条件，动作完全按每张卡的 `actions` 渲染。
 * `/connections/:id` 复用本组件，直接渲染详情。
 */
type Role = 'inbox' | 'sent'
type StatusFilter = 'all' | 'PENDING' | 'awaiting' | 'CONFIRMED' | 'closed'
type ViewState = 'loading' | 'ready' | 'error'
type DialogKind = 'decline' | 'cancel' | 'pre-approve'

const role = ref<Role>('inbox')
const status = ref<StatusFilter>('all')
const state = ref<ViewState>('loading')
const items = ref<ConnectionSummary[]>([])
const total = ref(0)
const page = ref(1)
const error = ref('')
const notice = ref('')
const actionError = ref('')
const loadingMore = ref(false)
const busyId = ref<number | null>(null)
const dialogTarget = ref<ConnectionSummary | null>(null)
const dialogKind = ref<DialogKind | ''>('')

const route = useRoute()
const router = useRouter()

// 深链 /connections?role=sent 直接打开发出的请求（列表 tab 与路由同步）。
if (route.query.role === 'sent') {
  role.value = 'sent'
}

const STATUS_FILTERS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'PENDING', label: '待处理' },
  { value: 'awaiting', label: '待确认' },
  { value: 'CONFIRMED', label: '已成立' },
  { value: 'closed', label: '已结束' },
]

const detailId = computed<number | null>(() => {
  const raw = route.params.id
  if (typeof raw !== 'string' || !raw) {
    return null
  }
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
})

const invalidDetail = computed(() => route.params.id !== undefined && detailId.value === null)
const statusQuery = computed<ConnectionStatus[]>(() => {
  if (status.value === 'all') {
    return []
  }
  if (status.value === 'awaiting') {
    return ['CONTACT_SHARED', 'CONFIRMING']
  }
  if (status.value === 'closed') {
    return ['DECLINED', 'CANCELLED', 'EXPIRED']
  }
  return [status.value]
})
const hasMore = computed(() => items.value.length < total.value)
const emptyTitle = computed(() => {
  if (status.value !== 'all') {
    return '这个筛选下没有请求。'
  }
  return role.value === 'inbox'
    ? '还没有请求。去匹配页看看，或者等别人来邀请你。'
    : '还没有发出的请求。去匹配页看看，主动邀请一个合适的室友。'
})

async function load(reset: boolean): Promise<void> {
  if (reset) {
    state.value = 'loading'
    error.value = ''
    notice.value = ''
  }
  const nextPage = reset ? 1 : page.value + 1
  loadingMore.value = !reset
  try {
    const data = await fetchConnections({
      role: role.value,
      statuses: statusQuery.value,
      page: nextPage,
      pageSize: 20,
    })
    items.value = reset ? data.results : [...items.value, ...data.results]
    page.value = nextPage
    total.value = data.count
    state.value = 'ready'
  } catch (caught) {
    if (reset) {
      error.value = connectionErrorMessage(caught)
      state.value = 'error'
    } else {
      notice.value = connectionErrorMessage(caught, '加载更多失败，请稍后重试。')
    }
  } finally {
    loadingMore.value = false
  }
}

function setRole(next: Role): void {
  if (role.value === next) {
    return
  }
  role.value = next
  void load(true)
}

function setStatus(next: StatusFilter): void {
  if (status.value === next) {
    return
  }
  status.value = next
  void load(true)
}

async function accept(connection: ConnectionSummary): Promise<void> {
  if (busyId.value !== null) {
    return
  }
  busyId.value = connection.id
  actionError.value = ''
  notice.value = ''
  try {
    await acceptConnection(connection.id)
    notice.value = '已同意，联系方式只对你们两个人可见。'
    await router.push(connectionPath(connection.id))
  } catch (caught) {
    actionError.value = connectionErrorMessage(caught)
    const statusCode = apiErrorStatus(caught)
    if (statusCode === 404 || statusCode === 409) {
      void load(true)
    }
  } finally {
    busyId.value = null
  }
}

function openDialog(connection: ConnectionSummary, kind: DialogKind): void {
  if (busyId.value !== null) {
    return
  }
  actionError.value = ''
  dialogTarget.value = connection
  dialogKind.value = kind
}

function closeDialog(): void {
  if (busyId.value === null) {
    dialogTarget.value = null
    dialogKind.value = ''
  }
}

async function runDialog(): Promise<void> {
  const target = dialogTarget.value
  const kind = dialogKind.value
  if (!target || !kind || busyId.value !== null) {
    return
  }
  dialogTarget.value = null
  dialogKind.value = ''
  busyId.value = target.id
  actionError.value = ''
  notice.value = ''
  try {
    if (kind === 'decline') {
      await declineConnection(target.id)
      notice.value = '已拒绝这个请求。'
    } else if (kind === 'pre-approve') {
      await preApproveConnection(target.id)
      notice.value = '已先同意。对方上线后点一次“同意”，组寝就会直接成立。'
    } else {
      await cancelConnection(target.id)
      notice.value = '请求已关闭，联系方式已立即隐藏。'
    }
    await load(true)
  } catch (caught) {
    actionError.value = connectionErrorMessage(caught)
    const statusCode = apiErrorStatus(caught)
    if (statusCode === 404 || statusCode === 409) {
      void load(true)
    }
  } finally {
    busyId.value = null
  }
}

const dialogTitle = computed(() => {
  if (!dialogTarget.value) {
    return ''
  }
  if (dialogKind.value === 'decline') {
    return '拒绝这个请求？'
  }
  if (dialogKind.value === 'pre-approve') {
    return '先记下你的同意？'
  }
  return dialogTarget.value.status === 'PENDING' ? '撤回这个请求？' : '结束这段了解？'
})
const dialogDescription = computed(() => {
  if (dialogKind.value === 'decline') {
    return '拒绝后请求会关闭，对方会收到通知。你们之后仍可以重新发起。'
  }
  if (dialogKind.value === 'pre-approve') {
    return '先把“同意”记下来：对方上线后点一次“同意”，组寝就直接成立，不必同时在线。在此之前你仍可以撤回。'
  }
  if (dialogTarget.value?.status === 'PENDING') {
    return '撤回后对方会收到一条系统通知，你们之后仍然可以重新发起。'
  }
  return '关闭后联系方式会立即隐藏，对方会收到一条系统通知。'
})
const dialogConfirmLabel = computed(() => {
  if (dialogKind.value === 'decline') {
    return '拒绝请求'
  }
  if (dialogKind.value === 'pre-approve') {
    return '好，我先同意'
  }
  return dialogTarget.value?.status === 'PENDING' ? '撤回请求' : '结束了解'
})

function onVisibilityChange(): void {
  if (!document.hidden && !detailId.value) {
    void load(true)
  }
}

/** 列表里的安全入口：拉黑会由后端关闭进行中的请求，所以重新拉取列表。 */
function onReported(): void {
  notice.value = '举报已提交，管理员会核实。对方不会收到你举报的通知。'
}

async function onBlocked(_uid: string): Promise<void> {
  actionError.value = ''
  // load(true) 会清空提示，所以先重新拉取列表，再显示拉黑结果。
  await load(true)
  notice.value = '已拉黑。双方进行中的请求已关闭，对方不能再邀请你。'
}

watch(
  () => route.params.id,
  (value) => {
    if (value === undefined) {
      void load(true)
    }
  },
)

onMounted(() => {
  document.addEventListener('visibilitychange', onVisibilityChange)
  if (!detailId.value && !invalidDetail.value) {
    void load(true)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <ConnectionDetailPanel v-if="detailId !== null" :connection-id="detailId" />

  <div v-else-if="invalidDetail" class="container connection-invalid">
    <div class="empty">
      <strong>这个页面不存在，或者你没有权限查看。</strong>
      <p class="fine">请求链接可能不完整，也可能已经被撤回。</p>
      <RouterLink class="btn btn-small btn-ghost" to="/connections">返回请求列表</RouterLink>
    </div>
  </div>

  <div v-else class="container connections-page">
    <header class="page-head connections-head">
      <div>
        <p class="eyebrow">Connections</p>
        <h1>请求</h1>
        <p class="lede">收到和发出的组寝请求都在这里。双方的回应都会留在这里。</p>
      </div>
      <RouterLink class="btn btn-small btn-ghost" to="/match">去匹配页看看</RouterLink>
    </header>

    <NoticeBar v-if="actionError" tone="error" title="这次操作没有完成">
      <p>{{ actionError }}</p>
    </NoticeBar>
    <NoticeBar v-if="notice" tone="info">
      <p>{{ notice }}</p>
    </NoticeBar>

    <div class="toolbar connections-toolbar">
      <div class="tabs" role="tablist" aria-label="请求方向">
        <button
          type="button"
          class="tab"
          :class="{ active: role === 'inbox' }"
          role="tab"
          :aria-selected="role === 'inbox'"
          @click="setRole('inbox')"
        >
          收到的
        </button>
        <button
          type="button"
          class="tab"
          :class="{ active: role === 'sent' }"
          role="tab"
          :aria-selected="role === 'sent'"
          @click="setRole('sent')"
        >
          发出的
        </button>
      </div>
      <p class="connection-count fine">{{ total }} 个请求</p>
    </div>

    <div class="status-filters" role="group" aria-label="按状态筛选">
      <button
        v-for="item in STATUS_FILTERS"
        :key="item.value"
        type="button"
        class="chip status-filter"
        :class="{ active: status === item.value }"
        :aria-pressed="status === item.value"
        @click="setStatus(item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <StateBlock
      v-if="state === 'loading'"
      status="loading"
      :rows="3"
      title="正在加载请求"
    />

    <StateBlock
      v-else-if="state === 'error'"
      status="error"
      :message="error"
      @retry="load(true)"
    />

    <div v-else-if="!items.length" class="empty connections-empty">
      <strong>{{ emptyTitle }}</strong>
      <p v-if="status === 'all'" class="fine">
        联系方式只在双方同意后可见。
      </p>
      <button
        v-if="status !== 'all'"
        type="button"
        class="btn btn-small btn-ghost"
        @click="setStatus('all')"
      >
        查看全部请求
      </button>
      <RouterLink v-else class="btn btn-small btn-ghost" to="/match">去匹配页看看</RouterLink>
    </div>

    <div v-else class="connection-list">
      <div v-for="connection in items" :key="connection.id" class="connection-item">
        <ConnectionCard
          :connection="connection"
          :busy="busyId === connection.id"
          @accept="accept(connection)"
          @decline="openDialog(connection, 'decline')"
          @confirm="router.push(connectionPath(connection.id))"
          @cancel="openDialog(connection, 'cancel')"
          @pre-approve="openDialog(connection, 'pre-approve')"
        />
        <div class="connection-security">
          <SecurityActions
            target-type="CONNECTION"
            :target-id="connection.id"
            :target-name="connectionCounterpart(connection)?.nickname ?? ''"
            :block-uid="connectionCounterpart(connection)?.uid ?? ''"
            @reported="onReported"
            @blocked="onBlocked"
          />
        </div>
      </div>
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
  </div>

  <ConfirmDialog
    :open="dialogTarget !== null"
    :title="dialogTitle"
    :description="dialogDescription"
    :confirm-label="dialogConfirmLabel"
    tone="danger"
    :busy="busyId !== null"
    @confirm="runDialog"
    @cancel="closeDialog"
  />
</template>

<style scoped>
.connections-page {
  display: grid;
  gap: 16px;
  padding-top: 36px;
  padding-bottom: 56px;
}

.connections-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.connections-head h1 {
  margin: 4px 0 6px;
  font-family: var(--font-serif);
  font-size: clamp(30px, 3.6vw, 42px);
  font-weight: 500;
  letter-spacing: -0.015em;
}

.connections-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--line);
}

.connection-count {
  margin: 0;
}

.status-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-filter {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.status-filter:hover {
  border-color: var(--ink);
  color: var(--ink);
}

.status-filter.active {
  border-color: var(--ink);
  background: var(--ink);
  color: var(--paper);
}

.status-filter:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 2px;
}

.connection-list {
  display: grid;
  gap: 12px;
}

.connection-item {
  display: grid;
  gap: 6px;
}

.connection-security {
  justify-self: end;
  padding-right: 4px;
}

.connections-empty {
  display: grid;
  justify-items: center;
  gap: 10px;
  border: 1px dashed var(--line);
  border-radius: 18px;
  padding: 48px 20px;
  text-align: center;
}

.connections-empty strong {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.connections-empty .fine {
  margin: 0;
}

.connection-invalid {
  padding-top: 48px;
  padding-bottom: 64px;
}

.connection-invalid .empty {
  display: grid;
  justify-items: center;
  gap: 10px;
  text-align: center;
}

.load-more {
  justify-self: center;
  margin-top: 4px;
}

@media (max-width: 640px) {
  .connections-page {
    padding-top: 24px;
  }

  .connections-head {
    align-items: flex-start;
  }

  .connections-head .btn {
    width: 100%;
  }

  .connections-toolbar {
    align-items: flex-end;
  }

  .status-filter {
    min-height: 44px;
  }
}
</style>
