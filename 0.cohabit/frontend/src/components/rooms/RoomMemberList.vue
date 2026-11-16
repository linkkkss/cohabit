<script setup lang="ts">
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import SecurityActions from '@/components/security/SecurityActions.vue'
import { formatDate } from '@/components/rooms/roomFormat'
import type { RoomMember } from '@/api/rooms'

/**
 * 成员列表（docs/05 §4.4 `.member-row`）：头像 / 昵称 / 角色 / 加入时间。
 * 房主可以移除成员；房主本人不可被移除，也不能移除自己。
 * 除自己外的成员都带举报/拉黑入口：拉黑只关闭进行中的请求，不会解散已成立的寝室。
 */
const props = withDefaults(
  defineProps<{
    members: RoomMember[]
    currentUid: string
    canRemove?: boolean
    busyUid?: string
  }>(),
  { canRemove: false, busyUid: '' },
)

const emit = defineEmits<{
  (event: 'remove', payload: { uid: string; nickname: string }): void
  (event: 'reported'): void
  (event: 'blocked', uid: string): void
}>()

function removable(member: RoomMember): boolean {
  return (
    props.canRemove &&
    member.role !== 'OWNER' &&
    member.uid !== props.currentUid &&
    member.status === 'ACTIVE'
  )
}

function uidNumber(uid: string): number {
  const value = Number(uid)
  return Number.isInteger(value) && value > 0 ? value : 0
}
</script>

<template>
  <ul v-if="members.length" class="member-list">
    <li v-for="member in members" :key="member.uid" class="member-row">
      <AvatarBadge :name="member.nickname" size="sm" />
      <div class="member-main">
        <p class="member-name">{{ member.nickname }}</p>
        <p class="fine member-meta">
          {{ member.role === 'OWNER' ? '房主' : '成员' }} · 加入于 {{ formatDate(member.created_at) }}
        </p>
      </div>
      <button
        v-if="removable(member)"
        type="button"
        class="btn btn-ghost btn-small member-remove"
        :disabled="busyUid === member.uid"
        :aria-label="`移除成员 ${member.nickname}`"
        @click="emit('remove', { uid: member.uid, nickname: member.nickname })"
      >
        {{ busyUid === member.uid ? '移除中…' : '移除' }}
      </button>
      <div v-if="member.uid !== currentUid" class="member-security">
        <SecurityActions
          target-type="USER"
          :target-id="uidNumber(member.uid)"
          :target-name="member.nickname"
          :block-uid="member.uid"
          @reported="emit('reported')"
          @blocked="emit('blocked', $event)"
        />
      </div>
    </li>
  </ul>
  <p v-else class="fine">这间寝室还没有成员。</p>
</template>

<style scoped>
.member-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.member-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  border-top: 1px solid var(--line);
  padding: 14px 0;
}

.member-row:first-child {
  border-top: 0;
  padding-top: 0;
}

.member-main {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1 1 auto;
}

.member-name {
  margin: 0;
  overflow: hidden;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-meta {
  margin: 0;
  color: var(--muted);
}

.member-remove {
  flex: 0 0 auto;
}

.member-security {
  flex: 1 0 100%;
  padding-left: 44px;
}

@media (max-width: 640px) {
  .member-remove {
    min-height: 44px;
  }

  .member-security {
    padding-left: 0;
  }
}
</style>
