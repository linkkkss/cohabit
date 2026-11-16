<script setup lang="ts">
import { computed, ref } from 'vue'
import { blockErrorMessage, blockUser, type Report, type ReportTargetType } from '@/api/security'
import ConfirmDialog from '@/components/rooms/ConfirmDialog.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import ReportDialog from '@/components/security/ReportDialog.vue'

/**
 * 举报 / 拉黑入口（docs/05 §7、S-07/S-08）。
 *
 * 用于匹配详情、请求卡片/详情、寝室成员列表。拉黑会关闭双方进行中的请求，
 * 但不会解散已经成立的寝室；成功后只向上抛出事件，由父组件刷新列表并提示。
 */
const props = withDefaults(
  defineProps<{
    targetType: ReportTargetType
    targetId: number
    targetName?: string
    /** 要拉黑的用户 uid；不传则不展示拉黑按钮（例如举报寝室本身）。 */
    blockUid?: string
    /** 拉黑按钮文案，默认「拉黑」。 */
    blockLabel?: string
  }>(),
  { targetName: '', blockUid: '', blockLabel: '拉黑' },
)

const emit = defineEmits<{
  (event: 'reported', report: Report): void
  (event: 'blocked', uid: string): void
}>()

const reportOpen = ref(false)
const blockOpen = ref(false)
const blocking = ref(false)
const blockError = ref('')

const canBlock = computed(() => props.blockUid.trim() !== '')
const blockDescription = computed(() =>
  `拉黑后，${props.targetName ? `「${props.targetName}」` : '对方'}将无法再邀请你，双方进行中的组寝请求会立即关闭。已经同住的寝室不会受影响。`,
)

function openReport(): void {
  blockError.value = ''
  reportOpen.value = true
}

function openBlock(): void {
  blockError.value = ''
  blockOpen.value = true
}

function onReported(report: Report): void {
  reportOpen.value = false
  emit('reported', report)
}

async function confirmBlock(): Promise<void> {
  if (blocking.value || !canBlock.value) {
    return
  }
  blocking.value = true
  blockError.value = ''
  try {
    await blockUser(props.blockUid)
    blockOpen.value = false
    emit('blocked', props.blockUid)
  } catch (caught) {
    blockError.value = blockErrorMessage(caught)
  } finally {
    blocking.value = false
  }
}
</script>

<template>
  <div class="security-actions">
    <div class="security-buttons">
      <button type="button" class="btn btn-ghost btn-small security-btn" @click="openReport">
        举报
      </button>
      <button
        v-if="canBlock"
        type="button"
        class="btn btn-ghost btn-small security-btn security-btn-danger"
        @click="openBlock"
      >
        {{ blockLabel }}
      </button>
    </div>

    <NoticeBar v-if="blockError" tone="error" title="拉黑没有完成">
      {{ blockError }}
    </NoticeBar>

    <ReportDialog
      v-model:open="reportOpen"
      :target-type="targetType"
      :target-id="targetId"
      :target-name="targetName"
      @submitted="onReported"
    />

    <ConfirmDialog
      :open="blockOpen"
      title="确认拉黑"
      :description="blockDescription"
      confirm-label="确认拉黑"
      tone="danger"
      :busy="blocking"
      inline
      @confirm="confirmBlock"
      @cancel="blockOpen = false"
    />
  </div>
</template>

<style scoped>
.security-actions {
  display: grid;
  gap: 8px;
}

.security-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.security-btn {
  min-height: 36px;
  padding: 0 12px;
  font-size: 13px;
  color: var(--muted);
}

.security-btn:hover:not(:disabled) {
  border-color: var(--ink);
  color: var(--ink);
}

.security-btn-danger:hover:not(:disabled) {
  border-color: var(--coral-dark);
  color: var(--coral-dark);
}

@media (max-width: 640px) {
  .security-btn {
    min-height: 44px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .security-btn {
    transition: none;
  }
}
</style>
