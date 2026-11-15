<script setup lang="ts">
import type { HardQuestion } from '@/api/profiles'

/**
 * 硬指标单选题（docs/03 §4.2）：整行可点的选项卡，移动端 ≥44px。
 * 用原生 radio 承载键盘与读屏，视觉上隐藏控件、只画卡片。
 */
const props = defineProps<{
  question: HardQuestion
  modelValue: string
  error?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const groupName = `hard-${props.question.key}`

function select(value: string): void {
  emit('update:modelValue', value)
}
</script>

<template>
  <fieldset class="question">
    <legend class="question-title">{{ question.title }}</legend>
    <div class="options">
      <label
        v-for="option in question.options"
        :key="option.value"
        class="option"
        :class="{ 'option-selected': modelValue === option.value }"
      >
        <input
          class="option-input"
          type="radio"
          :name="groupName"
          :value="option.value"
          :checked="modelValue === option.value"
          @change="select(option.value)"
        />
        <span class="option-text">{{ option.label }}</span>
      </label>
    </div>
    <p v-if="error" class="field-error">{{ error }}</p>
  </fieldset>
</template>

<style scoped>
.question {
  margin: 0;
  padding: 0;
  border: 0;
}

.question-title {
  display: block;
  margin-bottom: 10px;
  padding: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.options {
  display: grid;
  gap: 8px;
}

.option {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 14px;
  background: var(--paper);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.option:hover {
  border-color: var(--ink);
}

.option-selected {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 7%, var(--paper));
}

.option-input {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.option:has(.option-input:focus-visible) {
  outline: 2px solid var(--coral-dark);
  outline-offset: 3px;
}

.option-text {
  font-size: 14px;
  line-height: 1.5;
}

@media (prefers-reduced-motion: reduce) {
  .option {
    transition: none;
  }
}
</style>
