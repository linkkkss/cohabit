<script setup lang="ts">
import { computed } from 'vue'
import TagChips from '@/components/common/TagChips.vue'
import { roomDetailPath } from '@/components/rooms/roomFormat'
import {
  roomRoleLabel,
  roomSeatsText,
  roomStatusClass,
  roomStatusLabel,
  type RoomSummary,
} from '@/api/rooms'

/**
 * 寝室卡（docs/05 §4.4）：编号 / 标题 / 人数容量 / 状态 / 标签。
 * 广场与「我的寝室」共用；不显示成员联系方式。
 */
const props = withDefaults(
  defineProps<{
    room: RoomSummary
    variant?: 'square' | 'mine'
  }>(),
  { variant: 'square' },
)

const statusClass = computed(() => roomStatusClass(props.room.status))
const statusLabel = computed(() => roomStatusLabel(props.room.status))
const seats = computed(() => roomSeatsText(props.room))
const subtitle = computed(() =>
  [props.room.college, props.room.major].filter((item) => Boolean(item)).join(' · '),
)
const roleLabel = computed(() => roomRoleLabel(props.room.my_role))
</script>

<template>
  <RouterLink
    class="room-card room-card-link"
    :to="roomDetailPath(room.code)"
    :aria-label="`寝室 ${room.code}：${room.title || '未命名寝室'}`"
  >
    <div class="room-top">
      <span class="room-code">#{{ room.code }}</span>
      <span class="status" :class="statusClass">{{ statusLabel }}</span>
    </div>

    <h3 class="room-title">{{ room.title || '未命名寝室' }}</h3>
    <p class="room-subtitle">
      {{ subtitle || '学院待补充' }} · {{ room.capacity }} 人寝
    </p>

    <div class="room-meta">
      <span>{{ seats }}</span>
      <span v-if="room.owner">房主 {{ room.owner.nickname }}</span>
      <span v-if="roleLabel" class="room-role">{{ roleLabel }}</span>
      <span v-if="room.pending_transfer" class="room-transfer">转让待处理</span>
    </div>

    <TagChips class="room-tags" :tags="room.tags" :max="4" empty-text="还没有标签。" />

    <p v-if="variant === 'square'" class="fine room-hint">
      {{ room.can_apply ? '可以在组寝请求里申请加入。' : '先看成员与作息，再决定要不要发起请求。' }}
    </p>
    <p v-else class="fine room-hint">点开查看成员、标签与房主动作。</p>
  </RouterLink>
</template>

<style scoped>
.room-card-link {
  display: grid;
  gap: 10px;
  color: inherit;
  text-decoration: none;
}

.room-title {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow-wrap: anywhere;
}

.room-subtitle {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.room-tags {
  margin-top: 2px;
}

.room-role,
.room-transfer {
  color: var(--ink);
}

.room-hint {
  margin: 0;
  color: var(--muted);
}
</style>
