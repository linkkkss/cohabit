<script setup lang="ts">
import { computed, ref } from 'vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import type { TagOption } from '@/api/profiles'
import { ROOM_TAGS_MAX, ROOM_TITLE_MAX_LENGTH, type RoomDetail } from '@/api/rooms'
import { groupTagOptions } from '@/components/rooms/tagOptions'

/**
 * 房主编辑标题与标签（docs/04 §4.3 PATCH /rooms/:id）。
 * 容量不可改（后端 409 CAPACITY_IMMUTABLE），这里直接不提供输入。
 */
const props = withDefaults(
  defineProps<{
    room: RoomDetail
    tagOptions: TagOption[]
    busy?: boolean
    error?: string
  }>(),
  { busy: false, error: '' },
)

const emit = defineEmits<{
  (event: 'save', payload: { title: string; tags: string[] }): void
  (event: 'cancel'): void
}>()

const title = ref(props.room.title)
const tags = ref<string[]>([...props.room.tags])
const titleError = ref('')

const trimmedTitle = computed(() => title.value.trim())
const titleTooLong = computed(() => trimmedTitle.value.length > ROOM_TITLE_MAX_LENGTH)
const tagsFull = computed(() => tags.value.length >= ROOM_TAGS_MAX)
const grouped = computed(() => groupTagOptions(props.tagOptions))

function isSelected(name: string): boolean {
  return tags.value.includes(name)
}

function toggleTag(name: string): void {
  if (isSelected(name)) {
    tags.value = tags.value.filter((item) => item !== name)
    return
  }
  if (tagsFull.value) {
    return
  }
  tags.value = [...tags.value, name]
}

function save(): void {
  titleError.value = ''
  if (!trimmedTitle.value) {
    titleError.value = '标题不能为空。'
    return
  }
  if (titleTooLong.value) {
    titleError.value = `标题最长 ${ROOM_TITLE_MAX_LENGTH} 字。`
    return
  }
  emit('save', { title: trimmedTitle.value, tags: [...tags.value] })
}
</script>

<template>
  <section class="edit-panel">
    <h2 class="edit-title">编辑寝室信息</h2>

    <NoticeBar v-if="error" tone="error" title="没有保存成功">
      {{ error }}
    </NoticeBar>

    <label class="field edit-field">
      <span>标题</span>
      <input
        v-model="title"
        type="text"
        :maxlength="ROOM_TITLE_MAX_LENGTH"
        placeholder="例如：小算01的寝室"
      />
      <span class="fine counter">{{ trimmedTitle.length }} / {{ ROOM_TITLE_MAX_LENGTH }}</span>
    </label>
    <p v-if="titleError" class="field-error" role="alert">{{ titleError }}</p>

    <div class="edit-tags">
      <div class="edit-tags-head">
        <span class="eyebrow">标签</span>
        <span class="fine">已选 {{ tags.length }} / {{ ROOM_TAGS_MAX }}（可以为空）</span>
      </div>
      <div v-for="group in grouped" :key="group.group" class="edit-tag-group">
        <p class="eyebrow">{{ group.group }}</p>
        <div class="edit-tag-options">
          <button
            v-for="name in group.names"
            :key="name"
            type="button"
            class="edit-tag"
            :class="{ 'edit-tag-selected': isSelected(name) }"
            :aria-pressed="isSelected(name)"
            :disabled="tagsFull && !isSelected(name)"
            @click="toggleTag(name)"
          >
            {{ name }}
          </button>
        </div>
      </div>
    </div>

    <div class="edit-actions">
      <button type="button" class="btn btn-primary btn-small" :disabled="busy" @click="save">
        {{ busy ? '保存中…' : '保存修改' }}
      </button>
      <button type="button" class="btn btn-ghost btn-small" :disabled="busy" @click="emit('cancel')">
        取消
      </button>
    </div>
  </section>
</template>

<style scoped>
.edit-panel {
  display: grid;
  gap: 14px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 20px;
  background: var(--paper);
}

.edit-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.edit-field {
  position: relative;
}

.counter {
  position: absolute;
  right: 12px;
  bottom: 10px;
  color: var(--muted);
}

.edit-tags {
  display: grid;
  gap: 10px;
}

.edit-tags-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
}

.edit-tags-head .eyebrow {
  margin: 0;
}

.edit-tag-group {
  display: grid;
  gap: 6px;
}

.edit-tag-group .eyebrow {
  margin: 0;
  color: var(--muted);
}

.edit-tag-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.edit-tag {
  min-height: 36px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 6px 14px;
  background: var(--paper);
  color: var(--ink);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.edit-tag:hover:not(:disabled) {
  border-color: var(--ink);
}

.edit-tag:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.edit-tag-selected {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 10%, var(--paper));
  color: var(--coral-dark);
}

.edit-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 640px) {
  .edit-panel {
    padding: 18px;
  }

  .edit-tag {
    min-height: 44px;
  }

  .edit-actions .btn {
    flex: 1 1 140px;
    min-height: 44px;
  }
}
</style>
