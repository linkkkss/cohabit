<script setup lang="ts">
import { computed } from 'vue'

/**
 * 标签展示（docs/05 §6.1）：顺序照后端返回，不重排；超过 `max` 只显示 `+N`。
 * `shared` 里的标签加珊瑚色底，表示和我重合（最多 3 个由调用方控制）。
 */
const props = withDefaults(
  defineProps<{
    tags: string[]
    max?: number
    shared?: string[]
    emptyText?: string
  }>(),
  {
    max: 0,
    shared: () => [],
    emptyText: '',
  },
)

const visible = computed(() => (props.max > 0 ? props.tags.slice(0, props.max) : props.tags))
const hiddenCount = computed(() =>
  props.max > 0 ? Math.max(0, props.tags.length - props.max) : 0,
)

function isShared(tag: string): boolean {
  return props.shared.includes(tag)
}
</script>

<template>
  <p v-if="!tags.length" class="fine tag-empty">{{ emptyText }}</p>
  <div v-else class="tag-list">
    <span
      v-for="tag in visible"
      :key="tag"
      class="tag"
      :class="{ 'tag-shared': isShared(tag) }"
    >
      {{ tag }}
    </span>
    <span v-if="hiddenCount" class="tag tag-more">+{{ hiddenCount }}</span>
  </div>
</template>

<style scoped>
.tag-empty {
  margin: 14px 0 0;
}

.tag-more {
  border-style: dashed;
}

.tag-shared {
  border-color: color-mix(in srgb, var(--coral) 55%, var(--line));
  background: color-mix(in srgb, var(--coral) 9%, var(--paper));
  color: var(--coral-dark);
}
</style>
