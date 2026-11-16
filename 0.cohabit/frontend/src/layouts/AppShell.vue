<script setup lang="ts">
/**
 * 应用外壳（docs/05 §4.1）：skip-link、sticky 头部、主导航、账户菜单、页脚。
 *
 * 外壳层统一承担：
 * - 导航进度（>160ms 才显示，避免本地跳转闪烁）
 * - 页面级错误兜底（router.onError + onErrorCaptured）与重试
 * - 路由变化后的主区域焦点转移（键盘/读屏用户）
 * - 头部高度实测写入 --shell-header-h，供锚点滚动与移动端弹层定位
 */
import { computed, nextTick, onBeforeUnmount, onErrorCaptured, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import NotificationBell from '@/components/notifications/NotificationBell.vue'
import NetworkNotice from '@/components/shell/NetworkNotice.vue'
import UserMenu from '@/components/shell/UserMenu.vue'
import TimeWindowBanner from '@/components/timewindow/TimeWindowBanner.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const navItems = [
  { to: '/plaza', label: '广场' },
  { to: '/match', label: '匹配' },
  { to: '/connections', label: '请求' },
  { to: '/rooms', label: '寝室' },
] as const

const isDev = import.meta.env.DEV
const headerRef = ref<HTMLElement | null>(null)
const mainRef = ref<HTMLElement | null>(null)

/* ---------------- 导航进度 ---------------- */
const routeBusy = ref(false)
let revealTimer: number | null = null
let pendingTarget: string | null = null

function clearRevealTimer() {
  if (revealTimer !== null) {
    window.clearTimeout(revealTimer)
    revealTimer = null
  }
}

function beginRouteProgress() {
  clearRevealTimer()
  revealTimer = window.setTimeout(() => {
    routeBusy.value = true
    revealTimer = null
  }, 160)
}

function endRouteProgress() {
  clearRevealTimer()
  routeBusy.value = false
}

router.beforeEach((to) => {
  pendingTarget = to.fullPath
  beginRouteProgress()
})

router.afterEach(() => {
  endRouteProgress()
})

/* ---------------- 统一错误态 ---------------- */
const shellError = ref('')

function describeError(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return '未知错误'
}

router.onError((error) => {
  endRouteProgress()
  shellError.value = describeError(error)
})

onErrorCaptured((error) => {
  endRouteProgress()
  shellError.value = describeError(error)
  // 外壳已经给出可操作的错误卡片，阻止继续向 app.config.errorHandler 冒泡。
  return false
})

function retryRoute() {
  const target = pendingTarget
  shellError.value = ''
  if (target && target !== router.currentRoute.value.fullPath) {
    void router.push(target).catch(() => {
      shellError.value = '页面仍然没有加载出来，请稍后重试。'
    })
  }
}

function goHome() {
  shellError.value = ''
  void router.push({ name: 'home' })
}

/* ---------------- 头部高度实测 ---------------- */
let headerObserver: ResizeObserver | null = null

function syncHeaderHeight() {
  const el = headerRef.value
  if (!el) return
  const height = Math.round(el.getBoundingClientRect().height)
  if (height > 0) document.documentElement.style.setProperty('--shell-header-h', `${height}px`)
}

/* ---------------- 焦点管理 ---------------- */
watch(
  () => router.currentRoute.value.fullPath,
  async (_to, from) => {
    if (!from) return
    await nextTick()
    // 锚点跳转交给浏览器，别抢焦点与滚动位置。
    if (window.location.hash) return
    if (shellError.value) return
    const main = mainRef.value
    if (!main) return
    const active = document.activeElement
    // 焦点仍在主区域内（页内操作）时不打断。
    if (active && active !== document.body && main.contains(active)) return
    main.focus({ preventScroll: true })
  },
)

const footerYear = computed(() => new Date().getFullYear())

onMounted(() => {
  syncHeaderHeight()
  if (typeof ResizeObserver !== 'undefined' && headerRef.value) {
    headerObserver = new ResizeObserver(syncHeaderHeight)
    headerObserver.observe(headerRef.value)
  }
  window.addEventListener('resize', syncHeaderHeight)
})

onBeforeUnmount(() => {
  headerObserver?.disconnect()
  headerObserver = null
  window.removeEventListener('resize', syncHeaderHeight)
  clearRevealTimer()
  document.documentElement.style.removeProperty('--shell-header-h')
})
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main">跳到主要内容</a>

    <NetworkNotice />

    <header ref="headerRef" class="site-header">
      <div class="container header-inner">
        <RouterLink class="brand" to="/" aria-label="Cohabit 首页">
          <span class="brand-mark" aria-hidden="true">C</span>
          <span class="brand-name">Cohabit</span>
        </RouterLink>

        <nav class="primary-nav" aria-label="主导航">
          <RouterLink v-for="item in navItems" :key="item.to" class="nav-link" :to="item.to">
            <span>{{ item.label }}</span>
            <span
              v-if="item.to === '/connections' && auth.unreadCount > 0"
              class="nav-badge"
              :aria-label="`${auth.unreadCount} 条未读`"
            >
              {{ auth.unreadCount > 9 ? '9+' : auth.unreadCount }}
            </span>
          </RouterLink>
        </nav>

        <div class="header-actions">
          <template v-if="auth.isAuthenticated">
            <span v-if="auth.isPreview" class="chip chip-warn">预览模式</span>
            <RouterLink
              v-else-if="!auth.isProfileComplete"
              class="chip profile-chip"
              to="/onboarding"
              title="画像还没完成，去补充"
            >
              画像待完成
            </RouterLink>
            <NotificationBell />
            <UserMenu />
          </template>
          <RouterLink v-else class="btn btn-small btn-primary" to="/login">登录</RouterLink>
        </div>
      </div>

      <div v-if="routeBusy" class="route-progress" aria-hidden="true" />
      <p class="sr-only" role="status" aria-live="polite">{{ routeBusy ? '正在加载页面' : '' }}</p>
    </header>

    <!-- 时间窗横幅（WK-03）：登录后挂载、登出即卸载，组件自行拉取状态。 -->
    <TimeWindowBanner v-if="auth.isAuthenticated" />

    <main id="main" ref="mainRef" class="site-main" tabindex="-1">
      <section v-if="shellError" class="container shell-error" role="alert">
        <p class="eyebrow">出错了</p>
        <h1 class="shell-error-title">这个页面没有加载出来</h1>
        <p class="lede">
          可能是网络抖动，也可能是页面临时出错。可以重试，或者回到首页重新开始。
        </p>
        <p v-if="isDev" class="fine shell-error-detail">{{ shellError }}</p>
        <div class="shell-error-actions">
          <button type="button" class="btn btn-primary" @click="retryRoute">重试</button>
          <button type="button" class="btn btn-ghost" @click="goHome">回到首页</button>
        </div>
      </section>
      <RouterView v-else />
    </main>

    <footer class="site-footer">
      <div class="container footer-inner">
        <div class="footer-brand">
          <span class="footer-name">Cohabit · 校园舍友匹配</span>
          <p class="footer-note">仅限同学院、同性别；联系方式在双方同意后可见。</p>
        </div>
        <nav class="footer-nav" aria-label="站内信息">
          <RouterLink to="/rules">规则说明</RouterLink>
          <RouterLink to="/privacy">隐私说明</RouterLink>
          <RouterLink v-if="auth.isAuthenticated" to="/settings">设置</RouterLink>
        </nav>
      </div>
      <div class="container footer-meta">
        <span>© {{ footerYear }} Cohabit</span>
        <span>本服务仅用于校内舍友匹配，请勿用于其他用途。</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  /*
   * 离线横条是 fixed 的：撑出同高占位，sticky 头部与页面内容一起下移，
   * 避免横条出现时头部下移压住主区域顶部（--shell-notice-h 由 NetworkNotice 维护）。
   */
  padding-top: var(--shell-notice-h, 0px);
}

.skip-link {
  position: fixed;
  top: calc(var(--shell-notice-h, 0px) + 8px);
  left: 12px;
  z-index: 60;
  padding: 10px 16px;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-size: 13px;
  transform: translateY(-200%);
}

.skip-link:focus-visible {
  transform: translateY(0);
}

.site-header {
  position: sticky;
  top: var(--shell-notice-h, 0px);
  z-index: 20;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--paper) 92%, transparent);
  backdrop-filter: blur(12px);
}

.header-inner {
  display: flex;
  min-height: 72px;
  align-items: center;
  gap: 28px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-serif);
  font-size: 22px;
  letter-spacing: 0;
}

.brand-mark {
  display: grid;
  width: 30px;
  height: 30px;
  flex: none;
  place-items: center;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 700;
}

.brand-name {
  font-weight: 600;
}

.primary-nav {
  display: flex;
  flex: 1;
  gap: 20px;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--muted);
  font-size: 14px;
  transition: color 0.15s ease;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--ink);
}

.nav-badge {
  display: inline-grid;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  place-items: center;
  border-radius: 999px;
  background: var(--coral);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.profile-chip {
  border: 1px solid var(--sand-deep);
  background: var(--sand);
}

.chip-warn {
  border: 1px solid #e8c9a8;
  background: #fbf1e6;
  color: #8a5a2b;
}

.site-main {
  flex: 1;
}

.route-progress {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 2px;
  overflow: hidden;
  background: color-mix(in srgb, var(--coral) 16%, transparent);
}

.route-progress::after {
  display: block;
  width: 40%;
  height: 100%;
  background: var(--coral);
  content: '';
  animation: route-progress-slide 1.1s ease-in-out infinite;
}

.shell-error {
  padding: 72px 0 48px;
  max-width: 760px;
  margin-inline: auto;
}

.shell-error-title {
  margin: 8px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(30px, 5vw, 44px);
  font-weight: 500;
  letter-spacing: 0;
  line-height: 1.1;
}

.shell-error-detail {
  margin: 12px 0 0;
  overflow-wrap: anywhere;
}

.shell-error-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.site-footer {
  border-top: 1px solid var(--line);
  padding: 28px 0 calc(24px + env(safe-area-inset-bottom));
  color: var(--muted);
  font-size: 13px;
}

.footer-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px 24px;
}

.footer-name {
  color: var(--ink);
  font-family: var(--font-serif);
  font-size: 15px;
}

.footer-note {
  margin: 4px 0 0;
}

.footer-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
}

.footer-nav a {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
}

.footer-nav a:hover,
.footer-nav a.router-link-active {
  color: var(--ink);
}

.footer-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 12px;
}

@keyframes route-progress-slide {
  from {
    transform: translateX(-100%);
  }

  to {
    transform: translateX(350%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .route-progress::after {
    width: 100%;
    animation: none;
  }
}

@media (max-width: 820px) {
  .header-inner {
    flex-wrap: wrap;
    min-height: 64px;
    gap: 12px 20px;
    padding: 12px 0;
  }

  .primary-nav {
    order: 3;
    flex-basis: 100%;
    justify-content: space-between;
    gap: 8px;
  }

  .header-actions {
    margin-left: auto;
  }
}

@media (max-width: 640px) {
  .profile-chip {
    display: none;
  }

  .footer-inner {
    flex-direction: column;
  }

  .footer-nav {
    column-gap: 18px;
  }
}
</style>
