<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import { deadlineText, formatDateTime } from '@/components/rooms/roomFormat'
import type { RoomDetail, RoomTransfer } from '@/api/rooms'

/**
 * 房主转让（docs/04 §5.3）：
 * - 房主可以向一位成员发起转让，24 小时内有效；
 * - 被转让的成员可以接受 / 拒绝；房主可以撤销；
 * - 状态变化后由父组件重新拉详情（接受会换 owner）。
 */
const props = withDefaults(
  defineProps<{
    room: RoomDetail
    transfer: RoomTransfer | null
    currentUid: string
    busy?: string
    error?: string
  }>(),
  { busy: '', error: '' },
)

const emit = defineEmits<{
  (event: 'accept', transferId: number): void
  (event: 'decline', transferId: number): void
  (event: 'cancel', transferId: number): void
  (event: 'create', uid: string): void
}>()

const selectedUid = ref('')
const localError = ref('')

const pending = computed<RoomTransfer | null>(() =>
  props.transfer && props.transfer.status === 'PENDING' ? props.transfer : null,
)
const isOwner = computed(() => props.room.my_role === 'OWNER')
const toMe = computed(
  () => Boolean(pending.value?.to_member) && pending.value?.to_member?.uid === props.currentUid,
)
const fromMe = computed(
  () => Boolean(pending.value?.from_owner) && pending.value?.from_owner?.uid === props.currentUid,
)
const candidateMembers = computed(() =>
  props.room.members.filter((member) => member.role !== 'OWNER'),
)
const canCreate = computed(
  () => isOwner.value && props.room.actions.can_transfer && !pending.value,
)
const shownError = computed(() => localError.value || props.error)

watch(
  () => candidateMembers.value.map((member) => member.uid).join(','),
  () => {
    if (!candidateMembers.value.some((member) => member.uid === selectedUid.value)) {
      selectedUid.value = candidateMembers.value[0]?.uid ?? ''
    }
  },
  { immediate: true },
)

function create(): void {
  localError.value = ''
  if (!selectedUid.value) {
    localError.value = '先选一位成员，再把房主转让给 TA。'
    return
  }
  emit('create', selectedUid.value)
}
</script>

<template>
  <section class="transfer-panel">
    <h2 class="transfer-title">房主转让</h2>

    <NoticeBar v-if="shownError" tone="error" title="转让没有完成">
      {{ shownError }}
    </NoticeBar>

    <template v-if="pending">
      <div class="transfer-card">
        <p class="transfer-line">
          <span class="transfer-name">
            {{ pending.from_owner?.nickname ?? '房主' }}
          </span>
          <span aria-hidden="true">→</span>
          <span class="transfer-name">{{ pending.to_member?.nickname ?? '成员' }}</span>
        </p>
        <p class="fine">
          发起于 {{ formatDateTime(pending.created_at) }} · {{ deadlineText(pending.expires_at) }}
        </p>

        <div v-if="toMe" class="transfer-actions">
          <p class="transfer-desc">
            接受后你成为房主，对方变成成员。想先拒绝也可以，寝室状态不会变。
          </p>
          <button
            type="button"
            class="btn btn-primary btn-small"
            :disabled="busy !== ''"
            @click="pending.id && emit('accept', pending.id)"
          >
            {{ busy === 'accept' ? '接受中…' : '接受转让' }}
          </button>
          <button
            type="button"
            class="btn btn-ghost btn-small"
            :disabled="busy !== ''"
            @click="pending.id && emit('decline', pending.id)"
          >
            {{ busy === 'decline' ? '处理中…' : '拒绝' }}
          </button>
        </div>

        <div v-else-if="fromMe" class="transfer-actions">
          <p class="transfer-desc">等对方接受；24 小时没回应会自动过期。</p>
          <button
            type="button"
            class="btn btn-ghost btn-small"
            :disabled="busy !== ''"
            @click="pending.id && emit('cancel', pending.id)"
          >
            {{ busy === 'cancel' ? '撤销中…' : '撤销转让' }}
          </button>
        </div>

        <p v-else class="transfer-desc">房主正在把寝室转让给 {{ pending.to_member?.nickname }}。</p>
      </div>
    </template>

    <template v-else-if="isOwner">
      <template v-if="canCreate">
        <p class="fine">选一位成员：对方接受后成为房主，你变成成员，可以再退出。</p>
        <ul class="transfer-candidates">
          <li v-for="member in candidateMembers" :key="member.uid">
            <label class="transfer-candidate">
              <input v-model="selectedUid" type="radio" name="transfer-target" :value="member.uid" />
              <AvatarBadge :name="member.nickname" size="sm" />
              <span>{{ member.nickname }}</span>
            </label>
          </li>
        </ul>
        <button
          type="button"
          class="btn btn-dark btn-small"
          :disabled="busy !== ''"
          @click="create"
        >
          {{ busy === 'create' ? '发起中…' : '发起转让' }}
        </button>
      </template>
      <p v-else class="fine">
        寝室内还需要至少一位其他成员才能转让房主；先把人请进来，或直接解散。
      </p>
    </template>

    <p v-else class="fine">只有房主可以转让房主身份。</p>
  </section>
</template>

<style scoped>
.transfer-panel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 20px;
  background: var(--paper);
}

.transfer-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.transfer-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
  background: var(--sand);
}

.transfer-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.transfer-name {
  color: var(--ink);
  font-size: 15px;
}

.transfer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.transfer-desc {
  flex: 1 1 100%;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}

.transfer-candidates {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.transfer-candidate {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 8px 12px;
  cursor: pointer;
}

.transfer-candidate:hover {
  border-color: var(--ink);
}

@media (max-width: 640px) {
  .transfer-panel {
    padding: 18px;
  }

  .transfer-actions .btn {
    min-height: 44px;
  }
}
</style>
