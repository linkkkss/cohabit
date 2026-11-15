<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { ConnectionStatus, ContactInfo } from '@/api/connections'
import { isContactStage } from '@/api/connections'
import { copyText } from '@/components/rooms/roomFormat'
import { contactRows, maskContactValue, type ContactRow } from './connectionFormat'

/**
 * 联系方式区（docs/05 §4.4 `.contact-panel`）：
 * - 只在 CONTACT_SHARED / CONFIRMING / CONFIRMED 出现，关闭后整块消失；
 * - 后端只返回对方允许公开的字段，这里再做一层默认掩码，复制时使用完整值；
 * - 不出现“暂无联系方式”的占位。
 */
const props = withDefaults(
  defineProps<{
    contact: ContactInfo
    status: ConnectionStatus
    expired?: boolean
  }>(),
  {
    expired: false,
  },
)

const rows = computed(() => contactRows(props.contact))
const active = computed(() => isContactStage(props.status))
const revealed = ref<Record<string, boolean>>({})
const copiedKey = ref('')
const copyError = ref('')
let copyTimer: number | null = null

function displayValue(row: ContactRow): string {
  return revealed.value[row.key] ? row.value : maskContactValue(row.key, row.value)
}

function toggleReveal(row: ContactRow): void {
  revealed.value = { ...revealed.value, [row.key]: !revealed.value[row.key] }
}

async function copyRow(row: ContactRow): Promise<void> {
  copyError.value = ''
  const ok = await copyText(row.value)
  if (!ok) {
    copyError.value = '复制失败，请长按选择后手动复制。'
    return
  }
  copiedKey.value = row.key
  if (copyTimer !== null) {
    window.clearTimeout(copyTimer)
  }
  copyTimer = window.setTimeout(() => {
    copiedKey.value = ''
    copyTimer = null
  }, 2000)
}

onBeforeUnmount(() => {
  if (copyTimer !== null) {
    window.clearTimeout(copyTimer)
    copyTimer = null
  }
})
</script>

<template>
  <aside v-if="active" class="contact-panel" aria-labelledby="contact-panel-title">
    <div class="contact-head">
      <h2 id="contact-panel-title" class="contact-title">联系方式</h2>
      <span class="contact-badge">仅双方可见</span>
    </div>

    <template v-if="rows.length">
      <dl class="contact-list">
        <div v-for="row in rows" :key="row.key" class="contact-row">
          <dt>{{ row.label }}</dt>
          <dd>
            <span class="contact-value">{{ displayValue(row) }}</span>
            <span class="contact-tools">
              <button
                type="button"
                class="contact-tool"
                :aria-label="`${revealed[row.key] ? '隐藏' : '显示'} ${row.label}`"
                @click="toggleReveal(row)"
              >
                {{ revealed[row.key] ? '隐藏' : '显示' }}
              </button>
              <button
                type="button"
                class="contact-tool"
                :aria-label="`复制 ${row.label}`"
                @click="copyRow(row)"
              >
                {{ copiedKey === row.key ? '已复制' : '复制' }}
              </button>
            </span>
          </dd>
        </div>
      </dl>
      <p v-if="copyError" class="contact-copy-error" role="alert">{{ copyError }}</p>
    </template>

    <p v-else-if="expired" class="contact-locked">请求已过期，联系方式已隐藏。</p>
    <p v-else class="contact-locked">
      对方还没有公开联系方式；可以继续在站内把作息和细节说清楚。
    </p>

    <p class="contact-note">只对你们两个人可见；关闭请求后立即隐藏。</p>
  </aside>
</template>

<style scoped>
.contact-panel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px 20px;
  background: var(--paper);
}

.contact-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.contact-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.contact-badge {
  border: 1px solid var(--sand-deep);
  border-radius: 999px;
  padding: 3px 9px;
  background: var(--sand);
  color: var(--muted);
  font-size: 11px;
}

.contact-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.contact-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 12px;
  border-top: 1px dashed var(--line);
  padding-top: 10px;
}

.contact-row:first-child {
  border-top: 0;
  padding-top: 0;
}

.contact-row dt {
  color: var(--muted);
  font-size: 12px;
}

.contact-row dd {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.contact-value {
  font-family: var(--font-mono, monospace);
  font-size: 15px;
  letter-spacing: 0.04em;
  color: var(--ink);
}

.contact-tools {
  display: inline-flex;
  gap: 4px;
}

.contact-tool {
  border: 0;
  border-bottom: 1px solid transparent;
  padding: 2px 4px;
  background: transparent;
  color: var(--muted);
  font-size: 12px;
}

.contact-tool:hover,
.contact-tool:focus-visible {
  border-bottom-color: var(--ink);
  color: var(--ink);
}

.contact-locked {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.contact-copy-error {
  margin: 0;
  color: var(--coral-dark);
  font-size: 12px;
}

.contact-note {
  margin: 0;
  border-top: 1px solid var(--line);
  padding-top: 10px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 640px) {
  .contact-row dd {
    width: 100%;
    justify-content: space-between;
  }

  .contact-tool {
    min-height: 44px;
  }
}
</style>
