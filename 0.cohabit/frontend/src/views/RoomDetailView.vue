<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import TagChips from '@/components/common/TagChips.vue'
import ConfirmDialog from '@/components/rooms/ConfirmDialog.vue'
import RoomEditForm from '@/components/rooms/RoomEditForm.vue'
import RoomMemberList from '@/components/rooms/RoomMemberList.vue'
import SecurityActions from '@/components/security/SecurityActions.vue'
import RoomTransferPanel from '@/components/rooms/RoomTransferPanel.vue'
import { copyText, formatDateTime, publicRoomPath } from '@/components/rooms/roomFormat'
import { loadRoomTagOptions } from '@/components/rooms/tagOptions'
import type { TagOption } from '@/api/profiles'
import {
  acceptRoomTransfer,
  cancelRoomTransfer,
  createRoomTransfer,
  declineRoomTransfer,
  dissolveRoom,
  fetchRoomByCode,
  isRoomReadOnly,
  leaveRoom,
  lockRoom,
  removeRoomMember,
  roomErrorMessage,
  roomSeatsText,
  roomStatusClass,
  roomStatusLabel,
  unlockRoom,
  updateRoom,
  type RoomDetail,
} from '@/api/rooms'

/**
 * 寝室详情（docs/05 §7.1/§7.2）：左成员与标签，右动作。
 *
 * - 动作可见性完全听后端 `actions`（房主 / 成员 / 只读三态），前端不自己推断权限；
 * - 房主「退出」不能静默失败：弹层解释「需先转让或解散」，并把焦点带到转让区；
 * - 归档 / 解散只读，隐藏所有写按钮，只展示时间；
 * - 这里没有「加入」按钮：组寝只能走连接确认（docs/04 §4.3 只有 GET/PATCH/动作）。
 */
type ViewState = 'loading' | 'gate' | 'ready' | 'error'
type DialogKind = 'dissolve' | 'remove' | 'leave' | 'owner-leave' | null

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const code = computed(() => String(route.params.code ?? ''))
const state = ref<ViewState>('loading')
const room = ref<RoomDetail | null>(null)
const errorMessage = ref('')

const actionError = ref('')
const actionInfo = ref('')
const busy = ref('')
const editOpen = ref(false)
const tagOptions = ref<TagOption[]>([])

const transferBusy = ref('')
const transferError = ref('')
const transferAnchor = ref<HTMLElement | null>(null)

const dialog = ref<DialogKind>(null)
const dialogTarget = ref<{ uid: string; nickname: string } | null>(null)

const shareState = ref<'idle' | 'copied' | 'failed'>('idle')
const shareUrl = ref('')

const meUid = computed(() => auth.user?.uid ?? '')
const isOwner = computed(() => room.value?.my_role === 'OWNER')
const readOnly = computed(() => (room.value ? isRoomReadOnly(room.value.status) : false))
const writeBlocked = computed(() => !room.value?.id)
const seats = computed(() => (room.value ? roomSeatsText(room.value) : ''))
const memberBusyUid = computed(() => (busy.value === 'remove' ? (dialogTarget.value?.uid ?? '') : ''))

/** 转让区只在「房主发起」或「当前用户是转让的一方」时出现，避免无关成员看到灰色动作。 */
const transfer = computed(() => room.value?.pending_transfer ?? null)
const ownsTransfer = computed(() => {
  const pending = transfer.value
  if (!pending) {
    return false
  }
  return pending.from_owner?.uid === meUid.value || pending.to_member?.uid === meUid.value
})
const showTransferPanel = computed(
  () => Boolean(room.value) && !readOnly.value && !writeBlocked.value && (isOwner.value || ownsTransfer.value),
)

const readOnlyNotice = computed(() => {
  const current = room.value
  if (!current) {
    return ''
  }
  if (current.status === 'ARCHIVED') {
    return `寝室已于 ${formatDateTime(current.archived_at)} 归档，成员、标签和编号只能查看。`
  }
  return `寝室已于 ${formatDateTime(current.dissolved_at)} 解散，编号不再可用。`
})

const ACTIONS_DONE: Record<string, string> = {
  lock: '已锁定寝室：广场上暂时不再展示，也收不到新的组寝确认。',
  unlock: '已解锁寝室：重新开始接收成员。',
  dissolve: '寝室已解散，所有人都已离开，编号失效。',
  edit: '寝室信息已更新。',
}

async function load(): Promise<void> {
  if (!auth.isAuthenticated) {
    // 详情路由允许未登录访问；后台恢复会话完成前先保持加载态。
    if (!auth.initialized) {
      state.value = 'loading'
      return
    }
    state.value = 'gate'
    room.value = null
    return
  }
  state.value = 'loading'
  errorMessage.value = ''
  try {
    room.value = await fetchRoomByCode(code.value)
    state.value = 'ready'
  } catch (error) {
    errorMessage.value = roomErrorMessage(error, '寝室没有加载出来，请稍后重试。')
    state.value = 'error'
  }
}

async function refreshRoom(): Promise<void> {
  try {
    room.value = await fetchRoomByCode(code.value)
  } catch (error) {
    transferError.value = roomErrorMessage(error, '寝室状态没有刷新出来，请刷新页面。')
  }
}

function onReported(): void {
  actionError.value = ''
  actionInfo.value = '举报已提交，管理员会核实。对方不会收到你举报的通知。'
}

async function onMemberBlocked(_uid: string): Promise<void> {
  actionError.value = ''
  actionInfo.value = '已拉黑这位成员。进行中的请求已关闭，已成立的寝室不受影响。'
  await refreshRoom()
}

async function runAction(key: string, run: (id: number) => Promise<RoomDetail>): Promise<void> {
  const id = room.value?.id
  if (!id) {
    actionError.value = '这间寝室暂时不能执行操作：缺少寝室编号，刷新页面后再试。'
    return
  }
  busy.value = key
  actionError.value = ''
  actionInfo.value = ''
  try {
    room.value = await run(id)
    actionInfo.value = ACTIONS_DONE[key] ?? '已更新。'
  } catch (error) {
    actionError.value = roomErrorMessage(error, '操作没有完成，请稍后再试。')
  } finally {
    busy.value = ''
    dialog.value = null
  }
}

async function saveEdit(payload: { title: string; tags: string[] }): Promise<void> {
  await runAction('edit', (id) => updateRoom(id, payload))
  if (!actionError.value) {
    editOpen.value = false
  }
}

async function confirmRemove(): Promise<void> {
  const id = room.value?.id
  const target = dialogTarget.value
  if (!id || !target) {
    return
  }
  busy.value = 'remove'
  actionError.value = ''
  actionInfo.value = ''
  try {
    room.value = await removeRoomMember(id, target.uid)
    actionInfo.value = `已把 ${target.nickname} 移出寝室，名额已释放。`
  } catch (error) {
    actionError.value = roomErrorMessage(error, '移除没有完成，请稍后重试。')
  } finally {
    busy.value = ''
    dialog.value = null
    dialogTarget.value = null
  }
}

async function confirmLeave(): Promise<void> {
  const id = room.value?.id
  if (!id) {
    return
  }
  busy.value = 'leave'
  actionError.value = ''
  try {
    await leaveRoom(id)
    dialog.value = null
    await router.push({ path: '/rooms' })
  } catch (error) {
    actionError.value = roomErrorMessage(error, '退出没有完成，请稍后重试。')
    dialog.value = null
  } finally {
    busy.value = ''
  }
}

function askRemove(payload: { uid: string; nickname: string }): void {
  dialogTarget.value = payload
  dialog.value = 'remove'
}

function guideOwnerExit(): void {
  dialog.value = null
  void nextTick(() => {
    transferAnchor.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

async function createTransfer(uid: string): Promise<void> {
  const id = room.value?.id
  if (!id) {
    transferError.value = '这间寝室暂时不能发起转让，刷新页面后再试。'
    return
  }
  transferBusy.value = 'create'
  transferError.value = ''
  try {
    await createRoomTransfer(id, uid)
    await refreshRoom()
  } catch (error) {
    transferError.value = roomErrorMessage(error, '转让没有发起成功，请稍后重试。')
  } finally {
    transferBusy.value = ''
  }
}

async function actTransfer(kind: 'accept' | 'decline' | 'cancel', transferId: number): Promise<void> {
  transferBusy.value = kind
  transferError.value = ''
  try {
    if (kind === 'accept') {
      await acceptRoomTransfer(transferId)
    } else if (kind === 'decline') {
      await declineRoomTransfer(transferId)
    } else {
      await cancelRoomTransfer(transferId)
    }
    await refreshRoom()
  } catch (error) {
    transferError.value = roomErrorMessage(error, '转让没有处理成功，请刷新页面后再试。')
  } finally {
    transferBusy.value = ''
  }
}

async function share(): Promise<void> {
  const current = room.value
  if (!current) {
    return
  }
  const url = `${window.location.origin}${publicRoomPath(current.code)}`
  shareUrl.value = url
  const copied = await copyText(url)
  shareState.value = copied ? 'copied' : 'failed'
}

function selectShareLink(event: Event): void {
  const input = event.target as HTMLInputElement | null
  input?.select()
}

watch(
  () => auth.initialized,
  (initialized) => {
    if (initialized) {
      void load()
    }
  },
)

watch(code, () => {
  void load()
})

onMounted(() => {
  void load()
  loadRoomTagOptions()
    .then((options) => {
      tagOptions.value = options
    })
    .catch(() => {
      tagOptions.value = []
    })
})
</script>

<template>
  <div class="room-detail container">
    <RouterLink class="back-link fine" :to="{ name: 'rooms' }">← 返回我的寝室</RouterLink>

    <StateBlock
      v-if="state === 'loading'"
      status="loading"
      title="正在加载寝室…"
      :rows="2"
    />

    <div v-else-if="state === 'gate'" class="gate">
      <NoticeBar tone="info" title="登录后查看这间寝室">
        寝室详情包含成员、标签和房主动作，需要登录才能查看。公开分享页只展示寝室概况。
      </NoticeBar>
      <div class="gate-actions">
        <RouterLink
          class="btn btn-primary btn-small"
          :to="{ name: 'login', query: { redirect: route.fullPath } }"
        >
          去登录
        </RouterLink>
        <RouterLink class="btn btn-ghost btn-small" :to="{ name: 'plaza' }">去广场</RouterLink>
      </div>
    </div>

    <div v-else-if="state === 'error'" class="load-error">
      <StateBlock
        status="error"
        title="寝室没有加载出来"
        :message="errorMessage"
        @retry="load()"
      />
      <RouterLink class="btn btn-ghost btn-small" :to="{ name: 'rooms' }">回到我的寝室</RouterLink>
    </div>

    <template v-else-if="room">
      <header class="page-head detail-head">
        <div class="detail-head-main">
          <p class="eyebrow">Room {{ room.code }}</p>
          <h1>{{ room.title || '未命名寝室' }}</h1>
        </div>
        <p class="detail-meta">
          <span class="status" :class="roomStatusClass(room.status)">{{ roomStatusLabel(room.status) }}</span>
          <span>{{ seats }}</span>
          <span>{{ room.college }}</span>
          <span v-if="room.major">{{ room.major }}</span>
          <span v-if="room.owner">房主 {{ room.owner.nickname }}</span>
        </p>
      </header>

      <NoticeBar v-if="readOnly" tone="info" :title="room.status === 'ARCHIVED' ? '只读：已归档' : '只读：已解散'">
        {{ readOnlyNotice }}
      </NoticeBar>
      <NoticeBar v-else-if="writeBlocked" tone="warn" title="房主动作暂时不可用">
        这间寝室没有返回数字编号，刷新页面后再试；成员与标签仍可查看。
      </NoticeBar>

      <NoticeBar v-if="actionError" tone="error" title="操作没有完成">{{ actionError }}</NoticeBar>
      <NoticeBar v-else-if="actionInfo" tone="info">{{ actionInfo }}</NoticeBar>

      <div class="detail-layout">
        <div class="detail-main">
          <section class="panel detail-panel">
            <h2 class="panel-title">标签</h2>
            <TagChips :tags="room.tags" :max="0" empty-text="这间寝室还没有标签。" />
          </section>

          <section class="panel detail-panel">
            <div class="panel-head">
              <h2 class="panel-title">成员</h2>
              <span class="fine">{{ seats }}</span>
            </div>
            <RoomMemberList
              :members="room.members"
              :current-uid="meUid"
              :can-remove="!readOnly && !writeBlocked && room.actions.can_remove"
              :busy-uid="memberBusyUid"
              @remove="askRemove"
              @reported="onReported"
              @blocked="onMemberBlocked"
            />
          </section>

          <p class="fine detail-fine">
            寝室容量建立后不可修改；满员或锁定后，广场上不再展示，也收不到新的组寝确认。
          </p>
        </div>

        <aside class="detail-aside">
          <section class="panel detail-panel actions-panel">
            <h2 class="panel-title">
              {{ isOwner ? '房主动作' : room.my_role === 'MEMBER' ? '成员动作' : '这间寝室' }}
            </h2>

            <div class="actions-stack">
              <template v-if="!readOnly">
                <button
                  v-if="room.actions.can_edit"
                  type="button"
                  class="btn btn-ghost btn-small"
                  :disabled="busy !== '' || writeBlocked"
                  @click="editOpen = !editOpen"
                >
                  {{ editOpen ? '收起编辑' : '编辑标题与标签' }}
                </button>
                <button
                  v-if="room.actions.can_lock"
                  type="button"
                  class="btn btn-ghost btn-small"
                  :disabled="busy !== '' || writeBlocked"
                  @click="runAction('lock', lockRoom)"
                >
                  {{ busy === 'lock' ? '锁定中…' : '锁定寝室' }}
                </button>
                <button
                  v-if="room.actions.can_unlock"
                  type="button"
                  class="btn btn-ghost btn-small"
                  :disabled="busy !== '' || writeBlocked"
                  @click="runAction('unlock', unlockRoom)"
                >
                  {{ busy === 'unlock' ? '解锁中…' : '解锁寝室' }}
                </button>
                <button
                  v-if="isOwner"
                  type="button"
                  class="btn btn-ghost btn-small"
                  @click="dialog = 'owner-leave'"
                >
                  退出寝室
                </button>
                <button
                  v-else-if="room.actions.can_leave"
                  type="button"
                  class="btn btn-ghost btn-small"
                  :disabled="busy !== '' || writeBlocked"
                  @click="dialog = 'leave'"
                >
                  退出寝室
                </button>
                <button
                  v-if="room.actions.can_dissolve"
                  type="button"
                  class="btn btn-small danger-btn"
                  :disabled="busy !== '' || writeBlocked"
                  @click="dialog = 'dissolve'"
                >
                  解散寝室
                </button>
              </template>

              <button type="button" class="btn btn-ghost btn-small" @click="share">
                {{ shareState === 'copied' ? '已复制公开链接' : '复制公开链接' }}
              </button>
            </div>

            <div v-if="shareState === 'failed' && shareUrl" class="share-fallback">
              <p class="fine">浏览器没让写入剪贴板，手动复制这个链接：</p>
              <input
                class="share-link"
                :value="shareUrl"
                readonly
                aria-label="公开分享链接"
                @focus="selectShareLink"
              />
            </div>

            <p v-if="isOwner && !readOnly" class="fine actions-hint">
              房主不能直接退出：把房主转让给一位成员，或直接解散寝室。
            </p>
            <p v-else-if="room.my_role === 'MEMBER' && !readOnly" class="fine actions-hint">
              退出后名额立即释放；想再回来需要重新组寝并双方确认。
            </p>
            <p v-else-if="!readOnly" class="fine actions-hint">
              你还不是这间寝室的成员。想住进来，去组寝请求里发起申请。
            </p>
            <p v-else class="fine actions-hint">只读状态下不提供写动作。</p>

            <div v-if="!writeBlocked" class="room-security">
              <SecurityActions
                target-type="ROOM"
                :target-id="room.id ?? 0"
                :target-name="room.title || '未命名寝室'"
                @reported="onReported"
              />
            </div>
          </section>

          <div ref="transferAnchor">
            <RoomTransferPanel
              v-if="showTransferPanel"
              :room="room"
              :transfer="transfer"
              :current-uid="meUid"
              :busy="transferBusy"
              :error="transferError"
              @accept="(id: number) => actTransfer('accept', id)"
              @decline="(id: number) => actTransfer('decline', id)"
              @cancel="(id: number) => actTransfer('cancel', id)"
              @create="createTransfer"
            />
          </div>

          <RoomEditForm
            v-if="editOpen && !readOnly && !writeBlocked"
            :room="room"
            :tag-options="tagOptions"
            :busy="busy === 'edit'"
            :error="actionError"
            @save="saveEdit"
            @cancel="editOpen = false"
          />
        </aside>
      </div>

      <ConfirmDialog
        :open="dialog === 'dissolve'"
        title="解散寝室"
        :description="`解散后全部 ${room.member_count} 位成员都会离开，编号 ${room.code} 失效，广场上也不再展示。这个操作不能撤销。`"
        confirm-label="解散寝室"
        tone="danger"
        :confirm-word="room.code"
        :busy="busy === 'dissolve'"
        @confirm="runAction('dissolve', dissolveRoom)"
        @cancel="dialog = null"
      />

      <ConfirmDialog
        :open="dialog === 'remove'"
        title="移除成员"
        :description="`把 ${dialogTarget?.nickname ?? '这位成员'} 移出寝室？移出后名额释放，对方会收到通知。`"
        confirm-label="移除成员"
        :busy="busy === 'remove'"
        @confirm="confirmRemove"
        @cancel="dialog = null"
      />

      <ConfirmDialog
        :open="dialog === 'leave'"
        title="退出寝室"
        description="退出后名额立即释放；想再回来需要重新组寝并双方确认。"
        confirm-label="退出寝室"
        :busy="busy === 'leave'"
        @confirm="confirmLeave"
        @cancel="dialog = null"
      />

      <ConfirmDialog
        :open="dialog === 'owner-leave'"
        title="房主不能直接退出"
        description="寝室需要一个房主。你可以把房主转让给一位成员，转让完成后就能退出；或者直接解散寝室。"
        confirm-label="去转让房主"
        cancel-label="知道了"
        @confirm="guideOwnerExit"
        @cancel="dialog = null"
      />
    </template>
  </div>
</template>

<style scoped>
.room-detail {
  display: grid;
  gap: 18px;
}

.back-link {
  width: fit-content;
  color: var(--muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--ink);
}

.gate,
.load-error {
  display: grid;
  gap: 12px;
  justify-items: start;
}

.gate-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-head {
  padding-bottom: 0;
}

.detail-head-main {
  display: grid;
  gap: 0;
  min-width: 0;
}

.detail-head-main .eyebrow {
  margin-bottom: 10px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0 0 6px;
  color: var(--muted);
  font-size: 13px;
}

.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  align-items: start;
  gap: 24px;
}

.detail-main,
.detail-aside {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.detail-panel {
  display: grid;
  gap: 12px;
  padding: 20px;
}

.panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
}

.panel-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.detail-fine {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.actions-stack {
  display: grid;
  gap: 8px;
}

.actions-stack .btn {
  justify-content: center;
  width: 100%;
}

.danger-btn {
  border-color: color-mix(in srgb, var(--coral) 45%, var(--line));
  color: var(--coral-dark);
  background: var(--paper);
}

.danger-btn:hover:not(:disabled) {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 8%, var(--paper));
}

.actions-hint {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.room-security {
  margin-top: 4px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}

.share-fallback {
  display: grid;
  gap: 6px;
  margin-top: 4px;
}

.share-fallback .fine {
  margin: 0;
}

.share-link {
  width: 100%;
  min-height: 40px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 8px 10px;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: var(--ink);
  background: var(--sand);
}

.share-link:focus-visible {
  border-color: var(--ink);
}

@media (max-width: 640px) {
  .detail-layout {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .detail-panel {
    padding: 18px;
  }

  .actions-stack .btn {
    min-height: 44px;
  }
}
</style>
