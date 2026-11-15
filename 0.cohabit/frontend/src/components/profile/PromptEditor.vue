<script setup lang="ts">
import { computed } from 'vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import { MIN_PROMPTS, type PromptQuestion } from '@/api/profiles'

/**
 * 自述 Prompt 编辑（docs/03 §7）：6 题里填 2–3 题，每题 ≤120 字、≤3 行。
 * 自述是公开内容，所以固定展示隐私提醒。
 */
const props = defineProps<{
  questions: PromptQuestion[]
  modelValue: Record<string, string>
  errors?: Record<string, string>
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: Record<string, string>): void
}>()

const filledCount = computed(
  () => props.questions.filter((question) => (props.modelValue[question.key] ?? '').trim() !== '').length,
)

function valueOf(key: string): string {
  return props.modelValue[key] ?? ''
}

function onInput(key: string, event: Event): void {
  const value = (event.target as HTMLTextAreaElement).value
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function lineCount(value: string): number {
  return value.trim() === '' ? 0 : value.trim().split(/\r\n|\r|\n/).length
}

function errorOf(key: string): string {
  return props.errors?.[key] ?? ''
}
</script>

<template>
  <div class="prompts">
    <p class="prompts-count" :class="{ 'prompts-count-warn': filledCount < MIN_PROMPTS }">
      已填 {{ filledCount }} / {{ questions.length }} 题，至少填 {{ MIN_PROMPTS }} 题
    </p>

    <NoticeBar tone="warn">
      请勿填写 QQ、微信、手机号；联系方式只在双方同意后可见。
    </NoticeBar>

    <div v-for="question in questions" :key="question.key" class="field">
      <label :for="`prompt-${question.key}`">{{ question.title }}</label>
      <textarea
        :id="`prompt-${question.key}`"
        rows="3"
        :maxlength="question.max_length"
        :placeholder="question.placeholder"
        :value="valueOf(question.key)"
        :aria-invalid="Boolean(errorOf(question.key))"
        @input="onInput(question.key, $event)"
      ></textarea>
      <div class="prompts-meta">
        <span class="fine">{{ valueOf(question.key).length }} / {{ question.max_length }} 字</span>
        <span class="fine" :class="{ 'prompts-line-warn': lineCount(valueOf(question.key)) > 3 }">
          {{ lineCount(valueOf(question.key)) }} / 3 行
        </span>
      </div>
      <p v-if="errorOf(question.key)" class="field-error">{{ errorOf(question.key) }}</p>
    </div>
  </div>
</template>

<style scoped>
.prompts {
  display: grid;
  gap: 16px;
}

.prompts-count {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.prompts-count-warn {
  color: var(--coral-dark);
}

.prompts-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted);
}

.prompts-line-warn {
  color: var(--coral-dark);
}
</style>
