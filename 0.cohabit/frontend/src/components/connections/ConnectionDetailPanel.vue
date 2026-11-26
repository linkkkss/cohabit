<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { apiErrorStatus } from '@/api/client'
import {
  acceptConnection,
  cancelConnection,
  confirmConnection,
  declineConnection,
  connectionErrorMessage,
  fetchConnection,
  isConnectionOpen,
  preApproveConnection,
  type ConnectionDetail,
} from '@/api/connections'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import ConfirmDialog from '@/components/rooms/ConfirmDialog.vue'
import { formatDateTime, roomDetailPath } from '@/components/rooms/roomFormat'
import ConnectionActions from './ConnectionActions.vue'
import ContactPanel from './ContactPanel.vue'
import DeadlineText from './DeadlineText.vue'
import SecurityActions from '@/components/security/SecurityActions.vue'
import {
  CONNECTION_PHASES,
  closeReasonAdvice,
  closeReasonText,
  connectionCounterpart,
  connectionDeadline,
  connectionPhase,
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
 * 请求详情（docs/04 §4.4；docs/05 §7.2 `/connections/:id`）。
 *
 * - 联系方式只从这里读取；`contact` 为空对象时视为未解锁；
 * - 动作完全按 `actions` 渲染；confirm 是两步，第一次之后轮询等对方；
 * - 409/过期等状态冲突保留错误提示并静默重拉，避免页面停在旧状态。
 */
const props = defineProps<{
  connectionId: number
}>()

type ViewState = 'loading' | 'ready' | 'error' | 'missing'
type ActionKind = 'accept' | 'decline' | 'cancel' | 'confirm' | 'pre-approve'
type DialogKind = 'confirm' | 'cancel' | 'decline' | 'pre-approve'

const router = useRouter()
const state = ref<ViewState>('loading')
const connection = ref<ConnectionDetail | null>(null)
const loadError = ref('')
const actionError = ref('')
const actionInfo = ref('')
const busyAction = ref<ActionKind | ''>('')
const dialog = ref<DialogKind | ''>('')

let pollTimer: number | null = null

const open = computed(() => Boolean(connection.value && isConnectionOpen(connection.value.status)))
const closed = computed(() => Boolean(connection.value && isTerminalStatus(connection.value.status)))
const other = computed(() => (connection.value ? connectionCounterpart(connection.value) : null))
const otherName = computed(() => other.value?.nickname || '对方')
const otherMeta = computed(() => counterpartMeta(other.value))
const statusLabel = computed(() =>
  connection.value
    ? connectionStatusLabel(connection.value.status, connection.value.direction)
    : '',
)
const statusClass = computed(() =>
  connection.value ? connectionStatusClass(connection.value.status) : '',
)
const typeLabel = computed(() =>
  connection.value ? connectionTypeLabel(connection.value.type) : '',
)
const summaryLine = computed(() =>
  connection.value ? connectionSummaryLine(connection.value) : '',
)
const phase = computed(() => (connection.value ? connectionPhase(connection.value.status) : 0))
const showPhase = computed(() => Boolean(connection.value && !isTerminalStatus(connection.value.status)))
const expired = computed(() =>
  connection.value ? connectionDeadline(connection.value.expires_at) === '已过期' : false,
)
const closeText = computed(() =>
  connection.value ? closeReasonText(connection.value.close_reason) : '',
)
const closedByText = computed(() => connection.value?.closed_by?.nickname || '系统')

/** 关闭态的原因卡：CONFIRMED 不算失败，只在没成的时候出现。 */
const showFailCard = computed(
  () => Boolean(connection.value && closed.value && connection.value.status !== 'CONFIRMED'),
)
const failAdvice = computed(() =>
  connection.value ? closeReasonAdvice(connection.value.close_reason) : '',
)
const otherLastActiveText = computed(() => {
  const current = connection.value
  if (!current) {
    return ''
  }
  return lastActiveText(counterpartLastActive(current))
})
const otherPreApproved = computed(() => Boolean(connection.value?.initiator_pre_approved))
const preApproveBadge = computed(() =>
  connection.value?.direction === 'sent' ? '你已先同意' : '对方已先同意',
)

const isSent = computed(() => connection.value?.direction === 'sent')
const myConfirmAt = computed(() => {
  const current = connection.value
  if (!current) {
    return null
  }
  return current.direction === 'sent' ? current.initiator_confirm_at : current.target_confirm_at
})
const otherConfirmAt = computed(() => {
  const current = connection.value
  if (!current) {
    return null
  }
  return current.direction === 'sent' ? current.target_confirm_at : current.initiator_confirm_at
})
const showConfirmTimes = computed(() => {
  const current = connection.value
  if (!current) {
    return false
  }
  return (
    Boolean(myConfirmAt.value || otherConfirmAt.value) ||
    current.status === 'CONTACT_SHARED' ||
    current.status === 'CONFIRMING' ||
    current.status === 'CONFIRMED'
  )
})

const hasActions = computed(() => {
  const actions = connection.value?.actions
  if (!actions) {
    return false
  }
  return (
    actions.can_accept ||
    actions.can_decline ||
    actions.can_confirm ||
    actions.can_cancel ||
    actions.can_pre_approve
  )
})

const statusHint = computed(() => {
  const current = connection.value
  if (!current) {
    return ''
  }
  if (current.status === 'PENDING') {
    if (otherPreApproved.value) {
      return current.direction === 'inbox'
        ? '对方已经先同意了。你点一次“同意”就会直接成立组寝，不用等对方在线。'
        : '你已经先同意了。对方上线后点一次“同意”就会直接成立组寝。'
    }
    return current.direction === 'inbox'
      ? '对方在等你的回应。同意后双方才会看到联系方式；也可以先“我先同意”，等对方上线再说。'
      : '已发出，等对方回应。你也可以先“同意”，对方上线后点一次就能直接成立组寝。'
  }
  if (current.status === 'CONTACT_SHARED') {
    return otherPreApproved.value
      ? '对方已经先确认过了，你这一下确认就会直接成立组寝。'
      : '联系方式已互见。确认要一起住后，双方各确认一次即组寝成立。'
  }
  if (current.status === 'CONFIRMING') {
    return '一方已确认，另一方还需要确认；在最终确认前，任何一方仍可结束了解。'
  }
  if (current.status === 'CONFIRMED') {
    return '组寝已成立，接下来可以一起把寝室细节补齐。'
  }
  return '这个请求已经结束，联系方式已隐藏。'
})

const dialogTitle = computed(() => {
  if (dialog.value === 'confirm') {
    return connection.value?.status === 'CONFIRMING' ? '对方已经确认，你也要一起住吗？' : '确认要一起住吗？'
  }
  if (dialog.value === 'cancel') {
    return connection.value?.status === 'PENDING' ? '撤回这个请求？' : '结束这段了解？'
  }
  if (dialog.value === 'pre-approve') {
    return '先记下你的同意？'
  }
  return '拒绝这个请求？'
})

const dialogDescription = computed(() => {
  if (dialog.value === 'confirm') {
    return connection.value?.status === 'CONFIRMING'
      ? '这是最后一步：确认后会立即建立或加入寝室，并关闭你们其他进行中的请求。'
      : '确认后对方会收到提醒；双方都确认后才会建立寝室。在最终确认前，你们仍可以结束了解。'
  }
  if (dialog.value === 'cancel') {
    return connection.value?.status === 'PENDING'
      ? '撤回后对方会收到一条系统通知，你们之后仍然可以重新发起。'
      : '关闭后联系方式会立即隐藏，对方会收到一条系统通知。'
  }
  if (dialog.value === 'pre-approve') {
    return '你不需要等对方在线：先把“同意”记下来，对方上线后点一次“同意”，组寝就直接成立。在此之前你仍可以撤回。'
  }
  return '拒绝后请求会关闭，对方会收到通知。你们之后仍可以重新发起。'
})

const dialogConfirmLabel = computed(() => {
  if (dialog.value === 'confirm') {
    return connection.value?.status === 'CONFIRMING' ? '确认并组寝' : '确认组寝'
  }
  if (dialog.value === 'cancel') {
    return connection.value?.status === 'PENDING' ? '撤回请求' : '结束了解'
  }
  if (dialog.value === 'pre-approve') {
    return '好，我先同意'
  }
  return '拒绝请求'
})

const dialogTone = computed(() => (dialog.value === 'confirm' ? 'default' : 'danger'))

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function syncPolling(): void {
  stopPolling()
  if (state.value !== 'ready' || !open.value) {
    return
  }
  pollTimer = window.setInterval(() => {
    if (!document.hidden && !busyAction.value && dialog.value === '') {
      void load(true)
    }
  }, 25_000)
}

async function load(silent = false): Promise<void> {
  if (!silent) {
    state.value = 'loading'
    loadError.value = ''
  }
  try {
    connection.value = await fetchConnection(props.connectionId)
    state.value = 'ready'
    syncPolling()
  } catch (caught) {
    if (silent) {
      return
    }
    loadError.value = connectionErrorMessage(caught)
    state.value = apiErrorStatus(caught) === 404 ? 'missing' : 'error'
  }
}

function onVisibilityChange(): void {
  if (document.hidden) {
    stopPolling()
    return
  }
  if (open.value && state.value === 'ready') {
    void load(true)
  }
  syncPolling()
}

async function runAction(kind: ActionKind): Promise<void> {
  const current = connection.value
  if (!current || busyAction.value) {
    return
  }
  busyAction.value = kind
  actionError.value = ''
  actionInfo.value = ''
  try {
    if (kind === 'accept') {
      connection.value = await acceptConnection(current.id)
      actionInfo.value = '已同意，联系方式只对你们两个人可见。'
    } else if (kind === 'decline') {
      connection.value = await declineConnection(current.id)
      actionInfo.value = '已拒绝这个请求。'
    } else if (kind === 'cancel') {
      connection.value = await cancelConnection(current.id)
      actionInfo.value = '请求已关闭，联系方式已立即隐藏。'
    } else if (kind === 'pre-approve') {
      connection.value = await preApproveConnection(current.id)
      actionInfo.value = '已先同意。对方上线后点一次“同意”，组寝就会直接成立。'
    } else {
      const updated = await confirmConnection(current.id)
      connection.value = updated
      if (updated.status === 'CONFIRMED' && updated.room?.code) {
        actionInfo.value = '组寝成立，正在打开寝室…'
        await router.push(roomDetailPath(updated.room.code))
      } else {
        actionInfo.value = '已确认，等待对方确认。双方都确认后就会组成寝室。'
      }
    }
  } catch (caught) {
    actionError.value = connectionErrorMessage(caught)
    const status = apiErrorStatus(caught)
    if (status === 404 || status === 409) {
      await load(true)
    }
  } finally {
    busyAction.value = ''
    syncPolling()
  }
}

/** 举报/拉黑：拉黑会关闭进行中的请求，静默重拉让页面回到真实状态。 */
function onReported(): void {
  actionError.value = ''
  actionInfo.value = '举报已提交，管理员会核实。对方不会收到你举报的通知。'
}

async function onBlocked(_uid: string): Promise<void> {
  actionError.value = ''
  actionInfo.value = '已拉黑。对方不能再邀请你，进行中的请求已关闭。'
  await load(true)
}

function onAction(kind: ActionKind): void {
  actionError.value = ''
  if (kind === 'accept') {
    void runAction('accept')
    return
  }
  dialog.value = kind
}
function closeDialog(): void {
  if (!busyAction.value) {
    dialog.value = ''
  }
}

function confirmDialog(): void {
  const kind = dialog.value
  dialog.value = ''
  if (
    kind === 'confirm' ||
    kind === 'decline' ||
    kind === 'cancel' ||
    kind === 'pre-approve'
  ) {
    void runAction(kind)
  }
}

watch(
  () => props.connectionId,
  () => {
    connection.value = null
    actionError.value = ''
    actionInfo.value = ''
    dialog.value = ''
    state.value = 'loading'
    stopPolling()
    void load()
  },
  { immediate: true },
)

onMounted(() => {
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="container connection-detail">
    <div v-if="state === 'loading'" class="detail-loading">
      <StateBlock status="loading" :rows="2" />
    </div>

    <StateBlock
      v-else-if="state === 'error'"
      status="error"
      :message="loadError"
      @retry="load()"
    />

    <div v-else-if="state === 'missing'" class="empty detail-missing">
      <strong>这个请求不存在，或者你没有权限查看。</strong>
      <p class="state-empty-copy">它可能已经被撤回、过期，或者链接不属于你。</p>
      <RouterLink class="btn btn-small btn-ghost" to="/connections">返回请求列表</RouterLink>
    </div>

    <template v-else-if="connection">
      <header class="detail-head">
        <div>
          <RouterLink class="back-link" to="/connections">← 返回请求列表</RouterLink>
          <p class="eyebrow">Connection</p>
          <h1>{{ isSent ? `你与 ${otherName} 的请求` : `${otherName} 的组寝请求` }}</h1>
          <p class="detail-sub">{{ typeLabel }} · {{ summaryLine }}</p>
          <div class="detail-badges">
            <span class="status detail-status" :class="statusClass">{{ statusLabel }}</span>
            <span v-if="otherPreApproved && open" class="status detail-status status-pre">
              {{ preApproveBadge }}
            </span>
            <DeadlineText v-if="open" :expires-at="connection.expires_at" />
          </div>
        </div>
      </header>

      <NoticeBar v-if="actionError" tone="error" title="这次操作没有完成">
        <p>{{ actionError }}</p>
      </NoticeBar>
      <NoticeBar v-if="actionInfo" tone="info">
        <p>{{ actionInfo }}</p>
      </NoticeBar>

      <div class="detail-grid">
        <div class="detail-main">
          <section class="detail-card">
            <div class="person-row">
              <AvatarBadge :name="otherName" size="lg" />
              <div>
                <p class="eyebrow">{{ isSent ? '你邀请的人' : '发来请求的人' }}</p>
                <h2 class="person-name">{{ otherName }}</h2>
                <p v-if="otherMeta" class="fine">{{ otherMeta }}</p>
                <p v-if="open" class="fine active-line">最近活跃：{{ otherLastActiveText }}</p>
              </div>
            </div>

            <div class="person-security">
              <SecurityActions
                target-type="CONNECTION"
                :target-id="connection.id"
                :target-name="otherName"
                :block-uid="other?.uid ?? ''"
                @reported="onReported"
                @blocked="onBlocked"
              />
            </div>

            <div v-if="connection.message" class="message-block">
              <p class="eyebrow">留言</p>
              <p class="message-text">{{ connection.message }}</p>
            </div>

            <ol v-if="showPhase" class="phase-list" aria-label="请求进度">
              <li
                v-for="(label, index) in CONNECTION_PHASES"
                :key="label"
                class="phase-item"
                :class="{ done: phase >= index + 1, current: phase === index + 1 }"
              >
                <span class="phase-dot" aria-hidden="true"></span>
                <span>{{ label }}</span>
              </li>
            </ol>
          </section>

          <section class="detail-card">
            <h2 class="section-title">请求信息</h2>
            <dl class="meta-list">
              <div>
                <dt>类型</dt>
                <dd>{{ typeLabel }}</dd>
              </div>
              <div>
                <dt>状态</dt>
                <dd>{{ statusLabel }}</dd>
              </div>
              <div>
                <dt>联系方式解锁</dt>
                <dd>{{ formatDateTime(connection.contact_shared_at) }}</dd>
              </div>
              <div v-if="open">
                <dt>当前截止</dt>
                <dd class="meta-deadline">
                  <DeadlineText :expires-at="connection.expires_at" />
                  <span class="meta-absolute">{{ formatDateTime(connection.expires_at) }}</span>
                </dd>
              </div>
              <div v-if="showConfirmTimes">
                <dt>你的确认</dt>
                <dd>{{ myConfirmAt ? formatDateTime(myConfirmAt) : '尚未确认' }}</dd>
              </div>
              <div v-if="showConfirmTimes">
                <dt>对方确认</dt>
                <dd>{{ otherConfirmAt ? formatDateTime(otherConfirmAt) : '尚未确认' }}</dd>
              </div>
              <div v-if="closed && closeText">
                <dt>关闭原因</dt>
                <dd>{{ closeText }}</dd>
              </div>
              <div v-if="closed && connection.closed_by">
                <dt>关闭人</dt>
                <dd>{{ closedByText }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="showFailCard" class="detail-card fail-card">
            <p class="eyebrow">Retry</p>
            <h2 class="section-title">这次为什么没成</h2>
            <p class="fail-reason">{{ closeText || '请求已关闭' }}</p>
            <p class="fail-advice">{{ failAdvice }}</p>
            <div class="fail-actions">
              <RouterLink class="btn btn-small btn-primary" to="/match">重新匹配</RouterLink>
              <RouterLink class="btn btn-small btn-ghost" to="/connections">
                看看其他请求
              </RouterLink>
            </div>
          </section>

          <section v-if="connection.room" class="detail-card room-summary">
            <p class="eyebrow">Room</p>
            <h2 class="section-title">{{ connection.room.title || '寝室' }}</h2>
            <p class="room-meta-line">
              <span class="room-code">#{{ connection.room.code }}</span>
              <span>{{ connection.room.member_count }} / {{ connection.room.capacity }} 人</span>
              <span v-if="connection.room.college">{{ connection.room.college }}</span>
            </p>
            <RouterLink
              v-if="connection.room.code"
              class="btn btn-small btn-primary"
              :to="roomDetailPath(connection.room.code)"
            >
              查看寝室
            </RouterLink>
          </section>
        </div>

        <aside class="detail-aside">
          <section class="aside-card">
            <p class="eyebrow">Next</p>
            <h2 class="aside-title">下一步</h2>
            <p class="aside-hint">{{ statusHint }}</p>
            <ConnectionActions
              v-if="hasActions"
              :actions="connection.actions"
              :status="connection.status"
              :busy="busyAction !== ''"
              size="md"
              @accept="onAction('accept')"
              @decline="onAction('decline')"
              @confirm="onAction('confirm')"
              @cancel="onAction('cancel')"
              @pre-approve="onAction('pre-approve')"
            />
            <RouterLink
              v-if="showFailCard"
              class="btn btn-small btn-primary aside-retry"
              to="/match"
            >
              重新匹配
            </RouterLink>
            <p v-else class="fine aside-done">
              {{ closed ? '请求已结束，没有可执行的操作。' : '暂时没有需要你操作的动作。' }}
            </p>
            <p class="aside-privacy">联系方式只在双方同意后可见。</p>
          </section>

          <ContactPanel
            :contact="connection.contact"
            :status="connection.status"
            :expired="expired"
          />
          <p
            v-if="connection.status === 'PENDING'"
            class="contact-hint panel-like"
          >
            双方都同意后，这里会显示彼此的联系方式。
          </p>
        </aside>
      </div>
    </template>

    <ConfirmDialog
      :open="dialog !== ''"
      :title="dialogTitle"
      :description="dialogDescription"
      :confirm-label="dialogConfirmLabel"
      :tone="dialogTone"
      :busy="busyAction !== ''"
      @confirm="confirmDialog"
      @cancel="closeDialog"
    />
  </div>
</template>

<style scoped>
.connection-detail {
  display: grid;
  gap: 18px;
  padding-top: 36px;
  padding-bottom: 56px;
}

.detail-loading {
  display: grid;
  gap: 16px;
}

.detail-missing {
  display: grid;
  justify-items: center;
  gap: 12px;
}

.detail-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 20px;
}

.back-link {
  display: inline-block;
  margin-bottom: 18px;
  color: var(--muted);
  font-size: 13px;
}

.back-link:hover {
  color: var(--ink);
}

.detail-head h1 {
  margin: 4px 0 6px;
  font-family: var(--font-serif);
  font-size: clamp(28px, 3.4vw, 40px);
  font-weight: 500;
  letter-spacing: -0.015em;
  line-height: 1.12;
}

.detail-sub {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.detail-badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.detail-status {
  font-size: 12px;
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

.status-pre {
  background: #ecf4ec;
  color: #356b3b;
}

.active-line {
  margin-top: 4px;
  color: var(--muted);
}

.fail-card {
  display: grid;
  gap: 6px;
  justify-items: start;
  border-color: color-mix(in srgb, var(--coral) 35%, var(--line));
  background: color-mix(in srgb, var(--sand) 30%, var(--paper));
}

.fail-reason {
  margin: 0;
  color: var(--ink);
  font-size: 15px;
  font-weight: 600;
}

.fail-advice {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.fail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 6px;
}

.aside-retry {
  width: 100%;
  justify-content: center;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.8fr);
  gap: 18px;
  align-items: start;
}

.detail-main {
  display: grid;
  gap: 16px;
}

.detail-card,
.aside-card {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 22px;
  background: var(--paper);
}

.person-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.person-name {
  margin: 2px 0 2px;
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 500;
}

.message-block {
  border-top: 1px solid var(--line);
  margin-top: 18px;
  padding-top: 16px;
}

.message-text {
  margin: 0;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.phase-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  border-top: 1px solid var(--line);
  margin: 20px 0 0;
  padding: 18px 0 0;
  list-style: none;
}

.phase-item {
  display: grid;
  gap: 8px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}

.phase-dot {
  width: 100%;
  height: 3px;
  border-radius: 999px;
  background: var(--line);
}

.phase-item.done .phase-dot {
  background: var(--ink);
}

.phase-item.current {
  color: var(--ink);
  font-weight: 600;
}

.phase-item.current .phase-dot {
  background: var(--coral);
}

.section-title,
.aside-title {
  margin: 0 0 14px;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
}

.meta-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.meta-list > div {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 4px 16px;
  border-top: 1px dashed var(--line);
  padding-top: 10px;
  font-size: 13px;
}

.meta-list > div:first-child {
  border-top: 0;
  padding-top: 0;
}

.meta-list dt {
  color: var(--muted);
}

.meta-list dd {
  margin: 0;
  color: var(--ink);
  text-align: right;
}

.meta-deadline {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 8px;
}

.meta-absolute {
  color: var(--muted);
  font-size: 12px;
}

.room-summary {
  display: grid;
  gap: 6px;
  justify-items: start;
}

.room-summary .section-title {
  margin: 0;
}

.room-meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 12px;
}

.detail-aside {
  display: grid;
  gap: 16px;
  position: sticky;
  top: 92px;
}

.aside-hint {
  margin: 0 0 16px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.aside-done {
  margin: 0;
}

.aside-privacy {
  border-top: 1px solid var(--line);
  margin: 16px 0 0;
  padding-top: 10px;
  color: var(--muted);
  font-size: 12px;
}

.contact-hint {
  margin: 0;
  border: 1px dashed var(--line);
  border-radius: 18px;
  padding: 18px 20px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.panel-like {
  background: color-mix(in srgb, var(--sand) 40%, var(--paper));
}

@media (max-width: 920px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .detail-aside {
    position: static;
  }
}

@media (max-width: 640px) {
  .connection-detail {
    padding-top: 24px;
  }

  .detail-card,
  .aside-card {
    padding: 18px;
  }

  .phase-list {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .phase-item {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .phase-dot {
    width: 14px;
    height: 14px;
    flex: none;
    border-radius: 999px;
  }

  .detail-aside .aside-card {
    position: sticky;
    bottom: 10px;
    z-index: 5;
    box-shadow: 0 -12px 30px color-mix(in srgb, var(--ink) 8%, transparent);
  }
}

.person-security {
  margin-top: 10px;
}
</style>
