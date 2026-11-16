<script setup lang="ts">
/**
 * 全局离线提示（外壳层）。
 *
 * - 断网：常驻提示（role=alert），并把 --shell-notice-h 撑高，让 sticky 头部下移。
 * - 恢复：4 秒的轻提示（role=status）后自动收起。
 * - 不写业务状态，只做感知与排版占位；reduced-motion 下无动画。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const NOTICE_HEIGHT = 'calc(44px + env(safe-area-inset-top))'
const RESTORED_VISIBLE_MS = 4000

const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine !== false)
const justRestored = ref(false)
let restoredTimer: number | null = null

const visible = computed(() => !online.value || justRestored.value)

function clearRestoredTimer() {
  if (restoredTimer !== null) {
    window.clearTimeout(restoredTimer)
    restoredTimer = null
  }
}

/** 同步顶部占位高度：头部与 skip-link 都靠它下移，避免遮挡。 */
function syncNoticeHeight() {
  const root = document.documentElement
  if (visible.value) root.style.setProperty('--shell-notice-h', NOTICE_HEIGHT)
  else root.style.removeProperty('--shell-notice-h')
}

function handleOffline() {
  clearRestoredTimer()
  justRestored.value = false
  online.value = false
}

function handleOnline() {
  online.value = true
  justRestored.value = true
  clearRestoredTimer()
  restoredTimer = window.setTimeout(() => {
    justRestored.value = false
    restoredTimer = null
  }, RESTORED_VISIBLE_MS)
}

watch(visible, syncNoticeHeight)

onMounted(() => {
  syncNoticeHeight()
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
})

onBeforeUnmount(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
  clearRestoredTimer()
  document.documentElement.style.removeProperty('--shell-notice-h')
})
</script>

<template>
  <div
    v-if="visible"
    class="network-notice"
    :class="online ? 'is-restored' : 'is-offline'"
    :role="online ? 'status' : 'alert'"
    aria-live="polite"
    aria-atomic="true"
  >
    <div class="container network-inner">
      <span class="network-dot" aria-hidden="true" />
      <span v-if="online">网络已恢复，可以继续操作。</span>
      <span v-else>网络连接已断开，部分内容可能加载不出来；请检查网络后重试。</span>
    </div>
  </div>
</template>

<style scoped>
.network-notice {
  position: fixed;
  inset: 0 0 auto;
  z-index: 50;
  min-height: 44px;
  padding-top: env(safe-area-inset-top);
  border-bottom: 1px solid var(--line);
  font-size: 13px;
}

.is-offline {
  background: #fbf1e6;
  border-bottom-color: #e8c9a8;
  color: #8a5a2b;
}

.is-restored {
  background: var(--sand);
  border-bottom-color: var(--sand-deep);
  color: var(--ink);
}

.network-inner {
  display: flex;
  min-height: 44px;
  align-items: center;
  gap: 8px;
}

.network-dot {
  width: 8px;
  height: 8px;
  flex: none;
  border-radius: 999px;
  background: currentColor;
}

.network-notice span:last-child {
  overflow-wrap: anywhere;
}
</style>
