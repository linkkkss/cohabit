<script setup lang="ts">
import type { RedLineOption } from '@/api/profiles'

/**
 * 红线选择（docs/03 §5）：9 个红线 + 「以上都不是」，再加一次显式确认。
 * 只有勾了确认框，红线这一块才计入 10 分（服务端 `red_lines_confirmed`）。
 */
const props = defineProps<{
  options: RedLineOption[]
  modelValue: string[]
  confirmed: boolean
  error?: string
  confirmError?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string[]): void
  (event: 'update:confirmed', value: boolean): void
}>()

function toggle(id: string): void {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter((item) => item !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
}

function clearAll(): void {
  emit('update:modelValue', [])
}

function onConfirm(event: Event): void {
  emit('update:confirmed', (event.target as HTMLInputElement).checked)
}
</script>

<template>
  <div class="redline">
    <ul class="redline-list">
      <li v-for="option in options" :key="option.id">
        <label class="redline-item" :class="{ 'redline-checked': modelValue.includes(option.id) }">
          <input
            class="redline-input"
            type="checkbox"
            :value="option.id"
            :checked="modelValue.includes(option.id)"
            @change="toggle(option.id)"
          />
          <span class="redline-text">
            <span class="redline-label">{{ option.label }}</span>
            <span v-if="option.description" class="fine">{{ option.description }}</span>
          </span>
        </label>
      </li>
    </ul>

    <button type="button" class="btn btn-small btn-ghost redline-none" @click="clearAll">
      以上都不是
    </button>
    <p v-if="error" class="field-error">{{ error }}</p>

    <label class="redline-confirm">
      <input
        type="checkbox"
        :checked="confirmed"
        @change="onConfirm"
      />
      <span>我已确认以上红线：同居前会主动和室友沟通这些事。</span>
    </label>
    <p v-if="confirmError" class="field-error">{{ confirmError }}</p>
  </div>
</template>

<style scoped>
.redline {
  display: grid;
  gap: 12px;
}

.redline-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.redline-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 14px;
  cursor: pointer;
}

.redline-item:hover {
  border-color: var(--ink);
}

.redline-checked {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 7%, var(--paper));
}

.redline-input {
  margin: 2px 0 0;
  width: 18px;
  height: 18px;
  accent-color: var(--coral-dark);
}

.redline-text {
  display: grid;
  gap: 2px;
}

.redline-label {
  font-size: 14px;
  line-height: 1.5;
}

.redline-none {
  justify-self: start;
}

.redline-confirm {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  border-top: 1px solid var(--line);
  padding-top: 14px;
  font-size: 13px;
  line-height: 1.7;
  cursor: pointer;
}

.redline-confirm input {
  margin: 3px 0 0;
  width: 18px;
  height: 18px;
  accent-color: var(--coral-dark);
}
</style>
