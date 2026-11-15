<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

/**
 * 确认弹层（docs/05 §7.2、§9）：Esc 关闭、焦点困在弹层内、关闭后焦点还给触发按钮。
 * 破坏性操作用 `tone="danger"`（珊瑚色描边，不用纯红）。
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    confirmLabel?: string
    cancelLabel?: string
    tone?: 'default' | 'danger'
    busy?: boolean
    /** 需要输入确认文本时（例如输入寝室编号）传入。 */
    confirmWord?: string
  }>(),
  {
    description: '',
    confirmLabel: '确认',
    cancelLabel: '取消',
    tone: 'default',
    busy: false,
    confirmWord: '',
  },
)

const emit = defineEmits<{
  (event: 'confirm'): void
  (event: 'cancel'): void
}>()

const panel = ref<HTMLElement | null>(null)
const typed = ref('')
let lastFocused: HTMLElement | null = null

const confirmDisabled = computed(
  () => props.busy || (props.confirmWord !== '' && typed.value.trim() !== props.confirmWord),
)

function focusable(): HTMLElement[] {
  const root = panel.value
  if (!root) {
    return []
  }
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  )
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    if (!props.busy) {
      emit('cancel')
    }
    return
  }
  if (event.key !== 'Tab') {
    return
  }
  const items = focusable()
  if (items.length === 0) {
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (event.shiftKey && (active === first || !items.includes(active as HTMLElement))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement as HTMLElement | null
      typed.value = ''
      document.addEventListener('keydown', onKeydown, true)
      await nextTick()
      const items = focusable()
      const target = items.find((item) => !item.hasAttribute('data-autofocus')) ?? items[0]
      ;(target ?? panel.value)?.focus()
    } else {
      document.removeEventListener('keydown', onKeydown, true)
      lastFocused?.focus()
      lastFocused = null
    }
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown, true)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dialog-backdrop" @click.self="!busy && emit('cancel')">
      <div
        ref="panel"
        class="dialog-panel"
        :class="{ 'dialog-danger': tone === 'danger' }"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
      >
        <h2 class="dialog-title">{{ title }}</h2>
        <p v-if="description" class="dialog-desc">{{ description }}</p>
        <slot />
        <label v-if="confirmWord" class="dialog-field">
          <span class="fine">输入 {{ confirmWord }} 确认</span>
          <input v-model="typed" type="text" autocomplete="off" data-autofocus />
        </label>
        <div class="dialog-actions">
          <button type="button" class="btn btn-ghost" :disabled="busy" @click="emit('cancel')">
            {{ cancelLabel }}
          </button>
          <button
            type="button"
            class="btn"
            :class="tone === 'danger' ? 'btn-danger' : 'btn-primary'"
            :disabled="confirmDisabled"
            @click="emit('confirm')"
          >
            {{ busy ? '处理中…' : confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--ink) 32%, transparent);
}

.dialog-panel {
  width: min(440px, 100%);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 22px;
  background: var(--paper);
  box-shadow: 0 30px 60px color-mix(in srgb, var(--ink) 12%, transparent);
}

.dialog-danger {
  border-color: color-mix(in srgb, var(--coral) 40%, var(--paper));
}

.dialog-title {
  margin: 0 0 8px;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
}

.dialog-desc {
  margin: 0 0 14px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.65;
}

.dialog-field {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.dialog-field input {
  width: 100%;
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  font-family: var(--font-mono, monospace);
  font-size: 14px;
  letter-spacing: 0.06em;
  color: var(--ink);
  background: var(--paper);
}

.dialog-field input:focus-visible {
  border-color: var(--ink);
}

.dialog-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.btn-danger {
  border-color: var(--coral);
  background: var(--coral);
  color: #fff;
}

.btn-danger:hover {
  border-color: var(--coral-dark);
  background: var(--coral-dark);
}

@media (max-width: 640px) {
  .dialog-actions .btn {
    flex: 1 1 140px;
    min-height: 44px;
  }
}
</style>
