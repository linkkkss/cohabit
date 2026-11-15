<script setup lang="ts">
import { computed } from 'vue'
import type { TagOption } from '@/api/profiles'
import { groupTagOptions } from '@/components/rooms/tagOptions'

/**
 * 广场筛选（docs/04 §4.3、docs/05 §4.4）。
 *
 * 后端只接受 `major` / `capacity` / `tags` 三个筛选；广场本身已经限定在
 * 「本学院 + 同性别」，所以这里不再提供学院下拉，只把范围写清楚。
 */
export interface RoomFilterValue {
  major: string
  capacity: 2 | 4 | 6 | null
  tags: string[]
}

const props = defineProps<{
  modelValue: RoomFilterValue
  /** 本学院可选的专业（docs/03 §1）；为空时只显示「全部专业」。 */
  majorOptions: string[]
  college: string
  tagOptions: TagOption[]
  busy?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: RoomFilterValue): void
  (event: 'submit'): void
  (event: 'reset'): void
}>()

const CAPACITIES: (2 | 4 | 6)[] = [2, 4, 6]

function patch(partial: Partial<RoomFilterValue>): void {
  emit('update:modelValue', { ...props.modelValue, ...partial })
}

function setCapacity(value: 2 | 4 | 6 | null): void {
  patch({ capacity: value })
}

function setMajor(value: string): void {
  patch({ major: value })
}

function toggleTag(name: string): void {
  const tags = props.modelValue.tags.includes(name)
    ? props.modelValue.tags.filter((item) => item !== name)
    : [...props.modelValue.tags, name]
  patch({ tags })
}

const groupedTags = computed(() => groupTagOptions(props.tagOptions))

const activeCount = computed(
  () =>
    (props.modelValue.major ? 1 : 0) +
    (props.modelValue.capacity ? 1 : 0) +
    props.modelValue.tags.length,
)
</script>

<template>
  <form class="room-filters" @submit.prevent="emit('submit')">
    <p class="fine scope">范围：{{ college || '本学院' }} · 同性别 · 招募中且有空位</p>

    <div class="filter-group">
      <span class="eyebrow">容量</span>
      <div class="chip-row">
        <button
          type="button"
          class="chip"
          :class="{ 'chip-coral': modelValue.capacity === null }"
          :aria-pressed="modelValue.capacity === null"
          @click="setCapacity(null)"
        >
          不限
        </button>
        <button
          v-for="capacity in CAPACITIES"
          :key="capacity"
          type="button"
          class="chip"
          :class="{ 'chip-coral': modelValue.capacity === capacity }"
          :aria-pressed="modelValue.capacity === capacity"
          @click="setCapacity(capacity)"
        >
          {{ capacity }} 人寝
        </button>
      </div>
    </div>

    <div class="filter-group">
      <span class="eyebrow">专业</span>
      <div v-if="majorOptions.length" class="chip-row">
        <button
          type="button"
          class="chip"
          :class="{ 'chip-coral': modelValue.major === '' }"
          :aria-pressed="modelValue.major === ''"
          @click="setMajor('')"
        >
          全部专业
        </button>
        <button
          v-for="major in majorOptions"
          :key="major"
          type="button"
          class="chip"
          :class="{ 'chip-coral': modelValue.major === major }"
          :aria-pressed="modelValue.major === major"
          @click="setMajor(major)"
        >
          {{ major }}
        </button>
      </div>
      <p v-else class="fine">资料里还没有学院，暂时只看全部专业。</p>
    </div>

    <div v-if="tagOptions.length" class="filter-group">
      <span class="eyebrow">标签（可多选，需同时命中）</span>
      <details class="tag-panel">
        <summary class="chip">
          选择标签<span v-if="modelValue.tags.length"> · 已选 {{ modelValue.tags.length }}</span>
        </summary>
        <div class="tag-groups">
          <div v-for="group in groupedTags" :key="group.group" class="tag-group">
            <p class="eyebrow">{{ group.group }}</p>
            <div class="chip-row">
              <button
                v-for="name in group.names"
                :key="name"
                type="button"
                class="chip"
                :class="{ 'chip-coral': modelValue.tags.includes(name) }"
                :aria-pressed="modelValue.tags.includes(name)"
                @click="toggleTag(name)"
              >
                {{ name }}
              </button>
            </div>
          </div>
        </div>
      </details>
    </div>

    <div class="filter-actions">
      <button type="submit" class="btn btn-dark btn-small" :disabled="busy">
        {{ busy ? '筛选中…' : '应用筛选' }}
      </button>
      <button
        type="button"
        class="btn btn-ghost btn-small"
        :disabled="busy || activeCount === 0"
        @click="emit('reset')"
      >
        清除筛选
      </button>
    </div>
  </form>
</template>

<style scoped>
.room-filters {
  display: grid;
  gap: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 20px;
  background: var(--paper);
}

.scope {
  margin: 0;
  color: var(--muted);
}

.filter-group {
  display: grid;
  gap: 8px;
}

.filter-group .eyebrow {
  margin: 0;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip-row .chip {
  cursor: pointer;
}

.tag-panel {
  display: grid;
  gap: 10px;
}

.tag-panel summary {
  list-style: none;
  width: fit-content;
  cursor: pointer;
}

.tag-panel summary::-webkit-details-marker {
  display: none;
}

.tag-groups {
  display: grid;
  gap: 12px;
  margin-top: 10px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}

.tag-group {
  display: grid;
  gap: 6px;
}

.tag-group .eyebrow {
  margin: 0;
  color: var(--muted);
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 640px) {
  .room-filters {
    padding: 18px;
  }

  .filter-actions .btn {
    flex: 1 1 140px;
    min-height: 44px;
  }
}
</style>
