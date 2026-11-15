<script setup lang="ts">
import { computed } from 'vue'
import { MAX_TAGS, MIN_TAGS, type TagOption } from '@/api/profiles'

/**
 * 标签选择（docs/03 §6）：按组展示，最多 8 个、至少 3 个。
 * 顺序永远照后端返回，不在前端重排。
 */
const props = defineProps<{
  groups: TagOption[]
  modelValue: string[]
  error?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string[]): void
}>()

const grouped = computed(() => {
  const order: string[] = []
  const map = new Map<string, string[]>()
  for (const tag of props.groups) {
    if (!map.has(tag.group)) {
      map.set(tag.group, [])
      order.push(tag.group)
    }
    map.get(tag.group)?.push(tag.name)
  }
  return order.map((group) => ({ group, names: map.get(group) ?? [] }))
})

const isFull = computed(() => props.modelValue.length >= MAX_TAGS)

function isSelected(name: string): boolean {
  return props.modelValue.includes(name)
}

function toggle(name: string): void {
  if (isSelected(name)) {
    emit('update:modelValue', props.modelValue.filter((item) => item !== name))
    return
  }
  if (isFull.value) {
    return
  }
  emit('update:modelValue', [...props.modelValue, name])
}

function isDisabled(name: string): boolean {
  return isFull.value && !isSelected(name)
}
</script>

<template>
  <div class="tag-picker">
    <p class="tag-counter" :class="{ 'tag-counter-warn': modelValue.length < MIN_TAGS }">
      已选 {{ modelValue.length }} / {{ MAX_TAGS }}，至少选 {{ MIN_TAGS }} 个
    </p>

    <div v-for="group in grouped" :key="group.group" class="tag-group">
      <p class="eyebrow">{{ group.group }}</p>
      <div class="tag-options">
        <button
          v-for="name in group.names"
          :key="name"
          type="button"
          class="tag-option"
          :class="{ 'tag-option-selected': isSelected(name) }"
          :aria-pressed="isSelected(name)"
          :disabled="isDisabled(name)"
          @click="toggle(name)"
        >
          {{ name }}
        </button>
      </div>
    </div>

    <p v-if="error" class="field-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.tag-picker {
  display: grid;
  gap: 16px;
}

.tag-counter {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.tag-counter-warn {
  color: var(--coral-dark);
}

.tag-group {
  display: grid;
  gap: 8px;
}

.tag-group .eyebrow {
  margin: 0;
}

.tag-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-option {
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 16px;
  background: var(--paper);
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.tag-option:hover:not(:disabled) {
  border-color: var(--ink);
}

.tag-option:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.tag-option-selected {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 10%, var(--paper));
  color: var(--coral-dark);
}
</style>
