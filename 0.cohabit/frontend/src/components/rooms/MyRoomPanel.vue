<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import RoomCard from '@/components/rooms/RoomCard.vue'
import RoomTransferPanel from '@/components/rooms/RoomTransferPanel.vue'
import { formatDateTime } from '@/components/rooms/roomFormat'
import { roomErrorMessage, roomStatusClass, roomStatusLabel } from '@/api/rooms'
import {
  acceptRoomTransfer,
  cancelRoomTransfer,
  declineRoomTransfer,
  fetchMyRoom,
  type RoomDetail,
  type RoomMine,
} from '@/api/rooms'

/**
 * 我的寝室（docs/04 §4.3 `GET /api/rooms/mine`）：
 * 当前寝室 + 待处理转让 + 待处理组寝请求的入口；没有寝室时说明原因与下一步。
 */
const auth = useAuthStore()

const state = ref<'loading' | 'ready' | 'error'>('loading')
const mine = ref<RoomMine | null>(null)
const errorMessage = ref('')
const transferError = ref('')
const transferBusy = ref('')

const room = computed<RoomDetail | null>(() => mine.value?.room ?? null)
const meUid = computed(() => auth.user?.uid ?? '')
const pendingApplications = computed(() => mine.value?.pending_applications ?? [])
const otherPendingApplications = computed(() =>
  pendingApplications.value.filter((item) => item.type === 'APPLY'),
)

async function load(): Promise<void> {
  state.value = 'loading'
  errorMessage.value = ''
  try {
    mine.value = await fetchMyRoom()
    state.value = 'ready'
  } catch (error) {
    errorMessage.value = roomErrorMessage(error, '寝室信息没有加载出来，请稍后重试。')
    state.value = 'error'
  }
}

async function runTransfer(
  key: string,
  action: (transferId: number) => Promise<unknown>,
): Promise<void> {
  const transferId = mine.value?.pending_transfer?.id
  if (!transferId) {
    transferError.value = '这条转让已经不在待处理状态，刷新页面后再试。'
    return
  }
  transferBusy.value = key
  transferError.value = ''
  try {
    await action(transferId)
    await load()
  } catch (error) {
    transferError.value = roomErrorMessage(error, '转让没有完成，请稍后再试。')
  } finally {
    transferBusy.value = ''
  }
}

function acceptTransfer(id: number): void {
  void runTransfer('accept', () => acceptRoomTransfer(id))
}

function declineTransfer(id: number): void {
  void runTransfer('decline', () => declineRoomTransfer(id))
}

function cancelTransfer(id: number): void {
  void runTransfer('cancel', () => cancelRoomTransfer(id))
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="mine">
    <StateBlock v-if="state === 'loading'" status="loading" title="正在加载你的寝室…" :rows="2" />

    <StateBlock
      v-else-if="state === 'error'"
      status="error"
      title="寝室信息没有加载出来"
      :message="errorMessage"
      @retry="load"
    />

    <div v-else-if="!room" class="empty">
      <strong>还没有加入寝室</strong>
      <p>
        组寝要双方在连接请求里各确认一次才会建寝。可以先看看广场，或者等匹配到的同学发起邀请。
      </p>
      <div class="empty-actions">
        <RouterLink class="btn btn-primary btn-small" :to="{ path: '/rooms', query: { tab: 'square' } }">
          去广场看看
        </RouterLink>
        <RouterLink class="btn btn-ghost btn-small" :to="{ name: 'match' }">回到匹配</RouterLink>
      </div>
    </div>

    <template v-else>
      <header class="mine-head">
        <div>
          <p class="eyebrow">My room</p>
          <h2 class="mine-title">{{ room.title || '未命名寝室' }}</h2>
        </div>
        <span class="status" :class="roomStatusClass(room.status)">
          {{ roomStatusLabel(room.status) }}
        </span>
      </header>

      <RoomCard :room="room" variant="mine" />

      <section class="mine-facts">
        <dl class="fact-grid">
          <div>
            <dt>编号</dt>
            <dd class="mono">{{ room.code }}</dd>
          </div>
          <div>
            <dt>人数 / 容量</dt>
            <dd>{{ room.member_count }} / {{ room.capacity }} 人</dd>
          </div>
          <div>
            <dt>我的身份</dt>
            <dd>{{ room.my_role === 'OWNER' ? '房主' : '成员' }}</dd>
          </div>
          <div>
            <dt>建寝时间</dt>
            <dd>{{ formatDateTime(room.created_at) }}</dd>
          </div>
        </dl>
        <RouterLink class="btn btn-dark btn-small" :to="`/rooms/${room.code}`">
          进入寝室详情
        </RouterLink>
      </section>

      <NoticeBar v-if="room.status === 'LOCKED'" tone="warn" title="寝室已锁定">
        锁定期间不接收新成员；需要继续招募时，在寝室详情里解锁。
      </NoticeBar>
      <NoticeBar v-else-if="room.status === 'FULL'" tone="info" title="寝室已满员">
        满员后不能再加入；如果之后有人退出，名额会重新打开。
      </NoticeBar>

      <section v-if="otherPendingApplications.length" class="mine-requests">
        <p>
          有 {{ otherPendingApplications.length }} 条待处理的入寝申请。
        </p>
        <RouterLink class="btn btn-ghost btn-small" :to="{ name: 'connections' }">
          去组寝请求处理
        </RouterLink>
      </section>

      <NoticeBar v-if="transferError" tone="error" title="转让没有完成">
        {{ transferError }}
      </NoticeBar>

      <RoomTransferPanel
        :room="room"
        :transfer="mine?.pending_transfer ?? null"
        :current-uid="meUid"
        :busy="transferBusy"
        @accept="acceptTransfer"
        @decline="declineTransfer"
        @cancel="cancelTransfer"
      />
    </template>
  </section>
</template>

<style scoped>
.mine {
  display: grid;
  gap: 20px;
}

.mine-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mine-head .eyebrow {
  margin: 0 0 6px;
}

.mine-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(24px, 3vw, 32px);
  font-weight: 500;
}

.mine-facts {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 16px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}

.fact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px 20px;
  margin: 0;
}

.fact-grid div {
  display: grid;
  gap: 2px;
}

.fact-grid dt {
  color: var(--muted);
  font-size: 12px;
}

.fact-grid dd {
  margin: 0;
  font-size: 15px;
}

.mono {
  font-family: var(--font-mono, monospace);
  letter-spacing: 0.04em;
}

.mine-requests {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
}

.mine-requests p {
  margin: 0;
  font-size: 14px;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

@media (max-width: 920px) {
  .fact-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .mine-facts {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .mine-facts .btn,
  .empty-actions .btn,
  .mine-requests .btn {
    min-height: 44px;
  }
}
</style>
