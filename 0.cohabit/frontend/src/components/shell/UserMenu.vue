<script setup lang="ts">
/**
 * 账户菜单（外壳层）：头像/昵称触发，收起「我的画像 / 设置 / 规则 / 隐私 / 退出登录」。
 *
 * 移动端 375px 下头部只留一个 40px 触发按钮，避免第三行或溢出；
 * 菜单面板 ≤640px 改为 fixed 贴齐视口，复用 --shell-header-h / --shell-notice-h 定位。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const root = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLButtonElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const open = ref(false)
const signingOut = ref(false)
const signOutError = ref('')
const menuId = useId()

const displayName = computed(() => auth.displayName || '我的')
const avatarInitial = computed(() => displayName.value.slice(0, 1).toUpperCase())
const uid = computed(() => auth.user?.uid ?? '')

function close(focusTrigger = false) {
  if (!open.value) return
  open.value = false
  if (focusTrigger) {
    void nextTick(() => triggerRef.value?.focus({ preventScroll: true }))
  }
}

function toggle() {
  if (open.value) close()
  else open.value = true
}

function onDocumentPointerDown(event: Event) {
  if (!open.value) return
  const target = event.target as Node | null
  if (target && root.value?.contains(target)) return
  close()
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (!open.value) return
  if (event.key !== 'Escape') return
  event.preventDefault()
  close(true)
}

async function signOut() {
  if (signingOut.value) return
  signingOut.value = true
  signOutError.value = ''
  try {
    // 必须 await：store 先等 /auth/logout 返回再清本地会话；
    // 不等待会带着登录态跳 /login，被 guestOnly 守卫弹回，形成抖动。
    await auth.logout()
  } catch (error) {
    signOutError.value = apiErrorMessage(error, '退出登录失败，请稍后重试。')
    signingOut.value = false
    return
  }
  signingOut.value = false
  close()
  try {
    await router.push({ name: 'login' })
  } catch {
    // 会话已清空；导航被中断时留在当前页，下一次操作会引导重新登录。
  }
}

watch(open, async (value) => {
  if (!value) return
  await nextTick()
  panelRef.value?.querySelector<HTMLElement>('a, button')?.focus({ preventScroll: true })
})

// 路由变化后自动收起，避免菜单悬浮在新页面上。
watch(
  () => router.currentRoute.value.fullPath,
  () => close(),
)

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointerDown, true)
  document.addEventListener('keydown', onDocumentKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  document.removeEventListener('keydown', onDocumentKeydown)
})
</script>

<template>
  <div ref="root" class="user-menu">
    <button
      ref="triggerRef"
      type="button"
      class="user-trigger"
      :aria-expanded="open ? 'true' : 'false'"
      :aria-controls="menuId"
      aria-haspopup="true"
      :aria-label="`账户菜单，当前账号 ${displayName}`"
      @click="toggle"
    >
      <span class="avatar" aria-hidden="true">{{ avatarInitial }}</span>
      <span class="user-name">{{ displayName }}</span>
      <span class="caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" :id="menuId" ref="panelRef" class="user-panel">
      <div class="user-panel-head">
        <p class="user-panel-name">{{ displayName }}</p>
        <p v-if="uid" class="user-panel-uid">UID {{ uid }}</p>
      </div>
      <nav class="user-panel-nav" aria-label="账户菜单">
        <RouterLink class="user-panel-link" to="/profile">我的画像</RouterLink>
        <RouterLink class="user-panel-link" to="/settings">设置</RouterLink>
        <RouterLink class="user-panel-link" to="/rules">规则说明</RouterLink>
        <RouterLink class="user-panel-link" to="/privacy">隐私说明</RouterLink>
      </nav>
      <div class="user-panel-foot">
        <p v-if="signOutError" class="user-panel-error" role="alert">{{ signOutError }}</p>
        <button type="button" class="user-panel-signout" :disabled="signingOut" @click="signOut">
          {{ signingOut ? '正在退出…' : '退出登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-menu {
  position: relative;
}

.user-trigger {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 4px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  font-weight: 600;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.user-trigger:hover,
.user-trigger[aria-expanded='true'] {
  border-color: var(--line);
  background: color-mix(in srgb, var(--sand) 60%, transparent);
}

.avatar {
  display: grid;
  width: 28px;
  height: 28px;
  flex: none;
  place-items: center;
  border-radius: 999px;
  background: var(--sand-deep);
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 600;
}

.user-name {
  max-width: 8em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.caret {
  color: var(--muted);
  font-size: 10px;
  line-height: 1;
}

.user-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 45;
  min-width: 208px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--paper);
  box-shadow: 0 18px 40px rgb(0 0 0 / 12%);
}

.user-panel-head {
  padding: 8px 12px 10px;
  border-bottom: 1px solid var(--line);
}

.user-panel-name {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
}

.user-panel-uid {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}

.user-panel-nav {
  display: flex;
  flex-direction: column;
  padding: 6px 0;
}

.user-panel-link {
  display: flex;
  min-height: 44px;
  align-items: center;
  padding: 0 12px;
  border-radius: 10px;
  font-size: 14px;
}

.user-panel-link:hover {
  background: var(--sand);
}

.user-panel-foot {
  padding-top: 6px;
  border-top: 1px solid var(--line);
}

.user-panel-error {
  margin: 6px 12px 4px;
  color: var(--coral-dark);
  font-size: 12px;
  line-height: 1.5;
}

.user-panel-signout {
  width: 100%;
  min-height: 44px;
  padding: 0 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--coral-dark);
  font-size: 14px;
  font-weight: 600;
  text-align: left;
}

.user-panel-signout:hover {
  background: color-mix(in srgb, var(--coral) 10%, transparent);
}

.user-panel-signout:disabled {
  cursor: default;
  opacity: 0.6;
}

@media (max-width: 640px) {
  .user-name,
  .caret {
    display: none;
  }

  .user-trigger {
    padding: 4px;
  }

  .user-panel {
    position: fixed;
    top: calc(var(--shell-notice-h, 0px) + var(--shell-header-h, 64px) + 8px);
    right: 12px;
    left: 12px;
    min-width: 0;
    max-height: calc(100vh - var(--shell-header-h, 64px) - 32px);
    overflow-y: auto;
  }
}
</style>
