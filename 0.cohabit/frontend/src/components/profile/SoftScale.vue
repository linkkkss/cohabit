<script setup lang="ts">
import { computed } from 'vue'
import type { SoftQuestion } from '@/api/profiles'

/**
 * 软指标 1–5 档（docs/03 §4.3）：一行 5 个胶囊按钮，只标 1 和 5 两端的含义。
 * 用 role=radio 的按钮组，键盘 RadioGroup 语义由 aria-checked + 按钮默认 Tab 提供。
 */
const props = defineProps<{
  question: SoftQuestion
  modelValue?: number
  error?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: number): void
}>()

const steps = computed(() => {
  const values: number[] = []
  for (let value = props.question.min; value <= props.question.max; value += 1) {
    values.push(value)
  }
  return values
})

const lowLabel = computed(
  () => props.question.labels[String(props.question.min)] ?? `${props.question.min} 分`,
)
const highLabel = computed(
  () => props.question.labels[String(props.question.max)] ?? `${props.question.max} 分`,
)
</script>

<template>
  <div class="soft-question">
    <p class="soft-title">{{ question.title }}</p>
    <div class="scale" role="radiogroup" :aria-label="question.title">
      <button
        v-for="value in steps"
        :key="value"
        type="button"
        class="scale-btn"
        :class="{ 'scale-btn-selected': modelValue === value }"
        role="radio"
        :aria-checked="modelValue === value"
        :aria-label="`${value} 分`"
        @click="emit('update:modelValue', value)"
      >
        {{ value }}
      </button>
    </div>
    <div class="scale-labels">
      <span class="fine">{{ lowLabel }}</span>
      <span class="fine">{{ highLabel }}</span>
    </div>
    <p v-if="error" class="field-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.soft-question {
  display: grid;
  gap: 8px;
}

.soft-title {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}

.scale {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.scale-btn {
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--paper);
  color: var(--ink);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}

.scale-btn:hover {
  border-color: var(--ink);
}

.scale-btn-selected {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 10%, var(--paper));
  color: var(--coral-dark);
  font-weight: 600;
}

.scale-labels {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted);
}
</style>
