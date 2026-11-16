<script setup lang="ts">
import { nextTick, ref, useId, watch } from 'vue'
import { createReport, reportErrorMessage, type Report, type ReportTargetType } from '@/api/security'
import NoticeBar from '@/components/common/NoticeBar.vue'

/**
 * 通用举报弹层（docs/04 §4.6）：用户 / 寝室 / 请求共用。
 *
 * - reason 1–200 字，实时字数提示；失败保留输入，不关闭弹层；
 * - 使用原生 `<dialog>`，Esc 关闭，打开时焦点进入原因输入框；
 * - 举报内容只提交给管理员，对方不会收到通知，界面也不回显给被举报人。
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    targetType: ReportTargetType
    targetId: number
    targetName?: string
  }>(),
  { targetName: '' },
)

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'submitted', report: Report): void
}>()

const REASON_MAX_LENGTH = 200
const fieldId = useId()

const dialogRef = ref<HTMLDialogElement | null>(null)
const reason = ref('')
const submitting = ref(false)
const error = ref('')
const reasonInput = ref<HTMLTextAreaElement | null>(null)

const TARGET_LABELS: Record<ReportTargetType, string> = {
  USER: '用户',
  ROOM: '寝室',
  CONNECTION: '组寝请求',
}

function reset(): void {
  reason.value = ''
  submitting.value = false
  error.value = ''
}

function openDialog(): void {
  const element = dialogRef.value
  if (!element) {
    return
  }
  if (!element.open) {
    element.showModal()
  }
  void nextTick(() => {
    reasonInput.value?.focus()
  })
}

function closeDialog(): void {
  if (submitting.value) {
    return
  }
  dialogRef.value?.close()
}

function onCancel(event: Event): void {
  if (submitting.value) {
    event.preventDefault()
  }
}

function onClose(): void {
  if (submitting.value) {
    return
  }
  emit('update:open', false)
  reset()
}

async function submit(): Promise<void> {
  if (submitting.value) {
    return
  }
  const text = reason.value.trim()
  if (!text) {
    error.value = '请先写清楚发生了什么，再提交举报。'
    reasonInput.value?.focus()
    return
  }
  if (text.length > REASON_MAX_LENGTH) {
    error.value = `举报原因最多 ${REASON_MAX_LENGTH} 字，请删减后再提交。`
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const report = await createReport({
      target_type: props.targetType,
      target_id: props.targetId,
      reason: text,
    })
    emit('submitted', report)
    emit('update:open', false)
    reset()
    dialogRef.value?.close()
  } catch (caught) {
    error.value = reportErrorMessage(caught)
    reasonInput.value?.focus()
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.open,
  (value) => {
    if (value) {
      reset()
      openDialog()
    } else if (dialogRef.value?.open) {
      dialogRef.value.close()
    }
  },
  { immediate: true },
)
</script>

<template>
  <dialog
    ref="dialogRef"
    class="report-dialog"
    aria-label="提交举报"
    @cancel="onCancel"
    @close="onClose"
  >
    <form class="report-body" @submit.prevent="submit">
      <header class="report-head">
        <div>
          <p class="eyebrow">Report</p>
          <h2 class="report-title">举报{{ TARGET_LABELS[targetType] }}</h2>
        </div>
        <button
          type="button"
          class="report-close"
          aria-label="关闭举报弹层"
          :disabled="submitting"
          @click="closeDialog"
        >
          ×
        </button>
      </header>

      <p v-if="targetName" class="fine report-target">
        对象：{{ targetName }}
      </p>

      <NoticeBar tone="info">
        举报会提交给管理员，对方不会收到通知。请写清发生了什么，方便我们核实。
      </NoticeBar>

      <NoticeBar v-if="error" tone="error" title="举报没有提交成功">
        {{ error }}
      </NoticeBar>

      <label class="field" :for="`${fieldId}-reason`">
        <span>举报原因</span>
        <textarea
          :id="`${fieldId}-reason`"
          ref="reasonInput"
          v-model="reason"
          rows="5"
          :maxlength="REASON_MAX_LENGTH"
          placeholder="例如：对方在留言里索要微信，或发送了与组寝无关的广告。"
          :aria-describedby="`${fieldId}-count ${fieldId}-hint`"
          :disabled="submitting"
        ></textarea>
      </label>
      <div class="report-meta">
        <p :id="`${fieldId}-hint`" class="fine">只写与这次组寝有关的事实，不要填写联系方式。</p>
        <p :id="`${fieldId}-count`" class="fine report-count">
          {{ reason.length }} / {{ REASON_MAX_LENGTH }}
        </p>
      </div>

      <div class="report-actions">
        <button type="button" class="btn btn-ghost" :disabled="submitting" @click="closeDialog">
          取消
        </button>
        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? '提交中…' : '提交举报' }}
        </button>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.report-dialog {
  width: min(540px, calc(100% - 32px));
  max-height: min(90vh, 760px);
  margin: auto;
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 0;
  background: var(--paper);
  color: var(--ink);
}

.report-dialog::backdrop {
  background: color-mix(in srgb, var(--ink) 45%, transparent);
}

.report-body {
  display: grid;
  gap: 14px;
  max-height: inherit;
  overflow: auto;
  padding: 22px;
}

.report-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.report-title {
  margin: 2px 0 0;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 500;
}

.report-close {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: none;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--paper);
  color: var(--muted);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.report-close:hover:not(:disabled) {
  border-color: var(--ink);
  color: var(--ink);
}

.report-target {
  margin: 0;
  overflow-wrap: anywhere;
}

.report-body .field textarea {
  min-height: 132px;
  line-height: 1.65;
  resize: vertical;
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 12px;
}

.report-meta .fine {
  margin: 0;
}

.report-count {
  flex: none;
  font-variant-numeric: tabular-nums;
}

.report-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}

.report-actions .btn {
  min-height: 44px;
}

@media (max-width: 640px) {
  .report-body {
    padding: 18px 16px;
  }

  .report-actions {
    flex-direction: column-reverse;
  }

  .report-actions .btn {
    width: 100%;
  }
}
</style>
