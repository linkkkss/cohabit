<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PillNav, { type PillNavItem } from '@/components/shell/PillNav.vue'
import Dock, { type DockItem } from '@/components/shell/Dock.vue'
import FlowingMenu, { type FlowingItem } from '@/components/shell/FlowingMenu.vue'
import { useRouter } from 'vue-router'
import { installScrollReveal } from '@/composables/useScrollReveal'
import { useIntro } from '@/composables/useIntro'

const route = useRoute()
const router = useRouter()
const { introActive } = useIntro()

const items: PillNavItem[] = [
  { label: '首页', to: '/' },
  { label: '广场', to: '/plaza' },
  { label: '匹配', to: '/match', badge: 2 },
  { label: '我的画像', to: '/profile' },
]

const menuOpen = ref(false)

const dockItems = computed<DockItem[]>(() => [
  { key: '/', label: '首页', glyph: 'home', active: route.path === '/' },
  { key: '/plaza', label: '广场', glyph: 'plaza', active: route.path.startsWith('/plaza') },
  { key: '/match', label: '今日匹配', glyph: 'match', badge: 2, active: route.path.startsWith('/match') },
  { key: '/profile', label: '我的画像', glyph: 'profile', active: route.path.startsWith('/profile') },
  { key: 'menu', label: '全部页面', glyph: 'menu' },
])

const flowItems: FlowingItem[] = [
  { key: '/', label: '首页', meta: '先聊清楚，再住一起' },
  { key: '/plaza', label: '广场', meta: '六位同学，习惯对得上' },
  { key: '/match', label: '今日匹配', meta: '每天只推一个' },
  { key: '/profile', label: '我的画像', meta: '别人看到的和你看到的' },
]

const onDock = (item: DockItem): void => {
  if (item.glyph === 'menu') {
    menuOpen.value = true
    return
  }
  if (route.path !== item.key) router.push(item.key)
}

const onFlow = (key: string): void => {
  menuOpen.value = false
  if (route.path !== key) router.push(key)
}

const onKey = (event: KeyboardEvent): void => {
  if (event.key === 'Escape' && menuOpen.value) menuOpen.value = false
}

const mainRef = ref<HTMLElement | null>(null)
const scrolled = ref(false)
const noticeOpen = ref(false)
const narrow = ref(false)
let disposeReveal: (() => void) | null = null
let media: MediaQueryList | null = null

const onScroll = (): void => {
  scrolled.value = window.scrollY > 8
}

const onNarrow = (event: MediaQueryListEvent | MediaQueryList): void => {
  narrow.value = event.matches
}

onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('keydown', onKey)
  media = window.matchMedia('(max-width: 900px)')
  onNarrow(media)
  media.addEventListener('change', onNarrow)
  if (mainRef.value) disposeReveal = installScrollReveal(mainRef.value)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('keydown', onKey)
  media?.removeEventListener('change', onNarrow)
  media = null
  disposeReveal?.()
  disposeReveal = null
})

watch(
  () => route.fullPath,
  () => {
    noticeOpen.value = false
    menuOpen.value = false
  },
)
</script>

<template>
  <div class="shell">
    <a class="skip-link" href="#main">跳到主要内容</a>

    <header class="header" :class="{ 'is-scrolled': scrolled, 'is-intro': introActive }">
      <div class="container header__inner">
        <RouterLink class="brand" to="/" aria-label="Cohabit 首页">
          <span class="brand__mark" aria-hidden="true">
            <svg viewBox="0 0 48 48"><rect x="1" y="1" width="46" height="46" rx="2" fill="#ff8a00" stroke="#363636" stroke-width="2" /><path d="M35 15H17V33H35" fill="none" stroke="#fff4e2" stroke-width="8" /></svg>
          </span>
          <span class="brand__name">Cohabit</span>
        </RouterLink>

        <div class="nav-slot">
          <PillNav
            :items="items"
            aria-label="主导航"
            :indicator="'pill'"
            :collapse="narrow ? 'always' : 'auto'"
          />
        </div>

        <div class="header__actions">
          <button class="icon-btn icon-btn--menu" type="button" aria-label="全部页面" title="全部页面" @click="menuOpen = true">
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
              <path d="M3 6h14M3 10h14M3 14h14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </button>
          <button class="icon-btn" type="button" aria-label="搜索" title="搜索">
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
              <circle cx="8.6" cy="8.6" r="5.4" fill="none" stroke="currentColor" stroke-width="1.6" />
              <path d="m13 13 4 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
          </button>
          <button
            class="icon-btn icon-btn--bell"
            type="button"
            :aria-expanded="noticeOpen"
            aria-label="通知"
            title="通知"
            @click="noticeOpen = !noticeOpen"
          >
            <svg viewBox="0 0 20 20" width="17" height="17" aria-hidden="true">
              <path
                d="M5.4 13.2V9.1a4.6 4.6 0 0 1 9.2 0v4.1l1.1 1.5H4.3l1.1-1.5Z"
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linejoin="round"
              />
              <path d="M8.4 16.4a1.8 1.8 0 0 0 3.2 0" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
            </svg>
            <span class="icon-btn__dot" aria-hidden="true" />
          </button>

          <RouterLink class="me" to="/profile" aria-label="打开我的画像">
            <span class="me__avatar" aria-hidden="true">林</span>
            <span class="me__meta">
              <span class="me__name">林知夏</span>
              <span class="me__sub mono">78% 完成</span>
            </span>
          </RouterLink>
        </div>
      </div>

      <Transition name="notice">
        <div v-if="noticeOpen" class="notice">
          <div class="container notice__inner">
            <span class="notice__dot" aria-hidden="true" />
            <p><strong>2 条新匹配</strong>在等你回应 —— 匹配度 92% 的那位，红线也一致。</p>
            <RouterLink class="notice__link" to="/match">去看看 →</RouterLink>
            <button class="notice__close" type="button" aria-label="关闭通知" @click="noticeOpen = false">×</button>
          </div>
        </div>
      </Transition>
    </header>

    <main id="main" ref="mainRef" class="main" tabindex="-1">
      <RouterView v-slot="{ Component }">
        <Transition name="route" mode="out-in">
          <component :is="Component" :key="route.path" />
        </Transition>
      </RouterView>
    </main>

    <footer class="footer">
      <div class="container footer__inner">
        <div class="footer__brand">
          <p class="footer__word">Cohabit<span class="footer__dot">.</span></p>
          <p class="footer__line">先聊清楚，再住一起。</p>
          <p class="footer__note mono">UI concept · cream / charcoal / hermès orange</p>
        </div>
        <div class="footer__cols">
          <div class="footer__col">
            <p class="footer__head mono">产品</p>
            <RouterLink to="/plaza">广场</RouterLink>
            <RouterLink to="/match">今日匹配</RouterLink>
            <RouterLink to="/profile">我的画像</RouterLink>
          </div>
          <div class="footer__col">
            <p class="footer__head mono">关于</p>
            <a href="#">组寝规则</a>
            <a href="#">隐私说明</a>
            <a href="#">联系我们</a>
          </div>
          <div class="footer__col">
            <p class="footer__head mono">设计</p>
            <a href="#">配色与字体</a>
            <a href="#">动效说明</a>
            <a href="#">无障碍</a>
          </div>
        </div>
      </div>
      <div class="container footer__bottom">
        <span>© 2026 Cohabit · 校园组寝</span>
        <span class="mono">made for calmer roommates</span>
      </div>
    </footer>

    <Dock v-if="!introActive" :items="dockItems" @select="onDock" />
    <FlowingMenu :items="flowItems" :open="menuOpen" :active="route.path" @select="onFlow" @close="menuOpen = false" />
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  overflow-x: clip;
}

.skip-link {
  position: fixed;
  top: 8px;
  left: 12px;
  z-index: 90;
  padding: 10px 16px;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-size: 13px;
  transform: translateY(-220%);
  transition: transform 240ms var(--ease-out);
}

.skip-link:focus-visible {
  transform: translateY(0);
}

.header {
  position: sticky;
  top: 0;
  z-index: 40;
  border-bottom: var(--bd);
  background: var(--paper);
  transition:
    box-shadow 300ms var(--ease-out),
    opacity 420ms var(--ease-out);
}

.header.is-intro {
  opacity: 0;
  pointer-events: none;
}

.header.is-scrolled {
  background: var(--paper);
  box-shadow: 0 6px 0 rgba(54, 54, 54, 0.07);
}

.header__inner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  min-height: 76px;
  align-items: center;
  gap: 18px;
}

.brand {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand__mark {
  display: block;
  width: 36px;
  height: 36px;
  border-radius: 2px;
  box-shadow: 3px 3px 0 var(--ink);
  transition: transform 420ms var(--ease-out);
}

.brand__mark svg {
  display: block;
  width: 100%;
  height: 100%;
}

.brand:hover .brand__mark {
  transform: rotate(-6deg) scale(1.04);
}

.nav-slot {
  display: flex;
  min-width: 0;
  justify-content: center;
}

.header__actions {
  display: flex;
  align-items: center;
  justify-self: end;
  gap: 8px;
}

.icon-btn {
  position: relative;
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  background: var(--paper-raised);
  color: var(--ink);
  transition:
    transform 420ms var(--ease-out),
    border-color 320ms var(--ease-out),
    background-color 320ms var(--ease-out);
}

.icon-btn:hover {
  border-color: var(--ink);
  background: var(--paper-raised);
  transform: translate(-2px, -2px);
  box-shadow: 3px 3px 0 var(--ink);
}

.icon-btn:active {
  transform: translate(1px, 1px);
  box-shadow: none;
}

.icon-btn__dot {
  position: absolute;
  top: 8px;
  right: 9px;
  width: 6px;
  height: 6px;
  border: 1px solid var(--paper-raised);
  border-radius: 50%;
  background: var(--coral);
}

.me {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 4px 12px 4px 4px;
  border: 1.5px solid var(--ink);
  border-radius: 3px;
  background: var(--paper-raised);
  transition:
    border-color 320ms var(--ease-out),
    background-color 320ms var(--ease-out),
    transform 420ms var(--ease-out);
}

.me:hover {
  border-color: var(--ink);
  background: var(--paper-raised);
  transform: translate(-2px, -2px);
  box-shadow: 3px 3px 0 var(--ink);
}

.me__avatar {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  background: var(--coral);
  color: #2b1b08;
  font-family: var(--font-display);
  font-size: 14px;
  font-style: normal;
  font-weight: 700;
}

.me__meta {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.me__name {
  font-size: 12.5px;
  font-weight: 600;
}

.me__sub {
  color: var(--muted);
  font-size: 9.5px;
  letter-spacing: 0.06em;
}

.notice {
  position: absolute;
  right: 0;
  left: 0;
  border-bottom: var(--bd);
  background: var(--paper-raised);
  box-shadow: 0 6px 0 rgba(54, 54, 54, 0.06);
}

.notice__inner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  font-size: 13px;
}

.notice__dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: var(--coral);
}

.notice p {
  margin: 0;
  color: var(--muted);
}

.notice p strong {
  color: var(--ink);
}

.notice__link {
  margin-left: auto;
  color: var(--coral-dark);
  font-size: 12.5px;
  font-weight: 600;
}

.notice__close {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--muted);
}

.notice__close:hover {
  background: var(--sand);
  color: var(--ink);
}

.main {
  flex: 1;
  outline: none;
}

.footer {
  margin-top: clamp(48px, 6vw, 88px);
  border-top: var(--bd);
  padding: clamp(36px, 4vw, 56px) 0 104px;
  background: transparent;
}

@media (max-width: 900px) {
  .icon-btn--menu {
    display: none;
  }

  .footer {
    padding-bottom: 40px;
  }
}

.footer__inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 32px;
}

.footer__word {
  margin: 0;
  font-family: var(--font-display);
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}

.footer__dot {
  color: var(--coral);
}

.footer__line {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 13px;
}

.footer__note {
  margin: 18px 0 0;
  color: color-mix(in srgb, var(--muted) 72%, transparent);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.footer__cols {
  display: flex;
  flex-wrap: wrap;
  gap: 32px 56px;
}

.footer__col {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}

.footer__col a {
  color: var(--muted);
  transition: color 260ms var(--ease-out);
}

.footer__col a:hover {
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-thickness: 2px;
  text-decoration-color: var(--coral);
}

.footer__head {
  margin: 0 0 4px;
  color: var(--ink);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.footer__bottom {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px 20px;
  margin-top: 40px;
  border-top: 1.5px solid var(--ink);
  padding: 18px 0 28px;
  color: color-mix(in srgb, var(--muted) 78%, transparent);
  font-size: 11.5px;
}

.route-enter-active,
.route-leave-active {
  transition:
    opacity 220ms var(--ease-out),
    transform 320ms var(--ease-out);
}

.route-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.route-leave-to {
  opacity: 0;
}

.notice-enter-active,
.notice-leave-active {
  transition:
    opacity 260ms var(--ease-out),
    transform 320ms var(--ease-out);
}

.notice-enter-from,
.notice-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 900px) {
  .header__inner {
    grid-template-columns: auto minmax(0, 1fr) auto;
    min-height: 68px;
    padding: 9px 0;
    gap: 12px;
  }

  .nav-slot {
    justify-content: flex-end;
  }

  .brand__name,
  .me__meta {
    display: none;
  }

  .nav-slot :deep(.pill-nav__panel) {
    position: fixed;
    top: 76px;
    right: 14px;
    left: 14px;
    min-width: 0;
    border-radius: 24px;
  }
}

@media (max-width: 420px) {
  .icon-btn {
    width: 36px;
    height: 36px;
  }

  .me {
    padding: 3px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .route-enter-active,
  .route-leave-active,
  .notice-enter-active,
  .notice-leave-active {
    transition: none;
  }
}
</style>
