<script setup lang="ts">
/**
 * PillNav — React Bits <PillNav /> 的 Vue 移植（RouterLink 版）。
 * 胶囊底 + 滑动指示器 + 标签翻卷；空间不足时自动折叠成汉堡菜单。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

export interface PillNavItem {
  label: string
  to: string
  badge?: number | string
}

const props = withDefaults(
  defineProps<{
    items: PillNavItem[]
    activeTo?: string
    ariaLabel?: string
    size?: 'sm' | 'md'
    collapse?: 'auto' | 'always' | 'never'
    indicator?: 'pill' | 'dot' | 'none'
  }>(),
  {
    activeTo: '',
    ariaLabel: '主导航',
    size: 'md',
    collapse: 'auto',
    indicator: 'pill',
  },
)

const route = useRoute()
const rootRef = ref<HTMLElement | null>(null)
const listRef = ref<HTMLElement | null>(null)
const measureRef = ref<HTMLElement | null>(null)
const itemRefs = ref<HTMLElement[]>([])
const collapsed = ref(false)
const open = ref(false)
const indicatorReady = ref(false)

const activeIndex = computed(() => {
  const target = props.activeTo || route.path
  if (!target) return -1
  const exact = props.items.findIndex((item) => item.to === target)
  if (exact !== -1) return exact
  return props.items.findIndex((item) => target.startsWith(`${item.to}/`))
})

const setItemRef = (el: Element | null, index: number): void => {
  if (el instanceof HTMLElement) itemRefs.value[index] = el
}

let indicatorObserver: ResizeObserver | null = null
let autoObserver: ResizeObserver | null = null

const syncIndicator = (): void => {
  const nav = rootRef.value
  const active = itemRefs.value[activeIndex.value]
  if (!nav || !active) {
    indicatorReady.value = false
    return
  }
  nav.style.setProperty('--ind-x', `${active.offsetLeft}px`)
  nav.style.setProperty('--ind-w', `${active.offsetWidth}px`)
  indicatorReady.value = true
}

const evaluateCollapse = (): void => {
  if (props.collapse === 'always') {
    collapsed.value = true
    return
  }
  if (props.collapse === 'never') {
    collapsed.value = false
    return
  }
  const parent = rootRef.value?.parentElement
  const measure = measureRef.value
  if (!parent || !measure) return
  const styles = getComputedStyle(parent)
  const available =
    parent.clientWidth - (parseFloat(styles.paddingLeft) || 0) - (parseFloat(styles.paddingRight) || 0)
  const needed = measure.offsetWidth + 26
  collapsed.value = needed > available + 1
}

watch(
  () => [activeIndex.value, collapsed.value, props.items.length],
  async () => {
    await nextTick()
    syncIndicator()
    evaluateCollapse()
  },
)

watch(
  () => route.fullPath,
  () => {
    open.value = false
  },
)

const onDocumentPointerDown = (event: PointerEvent): void => {
  const target = event.target
  if (!(target instanceof Node)) return
  if (rootRef.value?.contains(target)) return
  open.value = false
}

const onKeydown = (event: KeyboardEvent): void => {
  if (event.key !== 'Escape' || !open.value) return
  open.value = false
}

onMounted(async () => {
  await nextTick()
  syncIndicator()
  evaluateCollapse()
  if (rootRef.value) {
    indicatorObserver = new ResizeObserver(() => {
      syncIndicator()
      evaluateCollapse()
    })
    indicatorObserver.observe(rootRef.value)
  }
  if (rootRef.value?.parentElement) {
    autoObserver = new ResizeObserver(evaluateCollapse)
    autoObserver.observe(rootRef.value.parentElement)
  }
  if (listRef.value) {
    autoObserver?.observe(listRef.value)
  }
  document.fonts?.ready.then(() => syncIndicator()).catch(() => undefined)
  document.addEventListener('pointerdown', onDocumentPointerDown)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  indicatorObserver?.disconnect()
  autoObserver?.disconnect()
  document.removeEventListener('pointerdown', onDocumentPointerDown)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <nav
    ref="rootRef"
    class="pill-nav"
    :data-collapsed="collapsed ? '' : undefined"
    :data-open="open ? '' : undefined"
    :data-size="size"
    :data-indicator="indicator"
    :aria-label="ariaLabel"
  >
    <div v-if="!collapsed" class="pill-nav__inner">
      <div class="pill-nav__bar">
        <span
          class="pill-nav__indicator"
          :class="{ 'is-ready': indicatorReady && activeIndex >= 0 && indicator === 'pill' }"
          aria-hidden="true"
        />
        <ul ref="listRef" class="pill-nav__list">
          <li
            v-for="(item, index) in items"
            :key="item.to"
            :ref="(el) => setItemRef(el as Element | null, index)"
            class="pill-nav__item"
            :data-active="index === activeIndex ? '' : undefined"
          >
            <RouterLink :to="item.to" class="pill-nav__link">
              <span class="pill-nav__label">
                <span class="pill-nav__label-line">{{ item.label }}</span>
                <span class="pill-nav__label-line pill-nav__label-line--alt" aria-hidden="true">{{
                  item.label
                }}</span>
              </span>
              <span v-if="item.badge" class="pill-nav__badge">{{ item.badge }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
      <span v-if="indicator === 'dot'" class="pill-nav__dot" :class="{ 'is-ready': indicatorReady }" aria-hidden="true" />
    </div>

    <div v-else class="pill-nav__collapsed">
      <button
        type="button"
        class="pill-nav__toggle"
        :aria-expanded="open"
        :aria-label="open ? '关闭菜单' : '打开菜单'"
        @click="open = !open"
      >
        <span class="pill-nav__burger" :data-open="open ? '' : undefined" aria-hidden="true">
          <span />
          <span />
        </span>
        <span class="pill-nav__toggle-text">{{ open ? '收起' : '菜单' }}</span>
      </button>

      <Transition name="pill-panel">
        <div v-if="open" class="pill-nav__panel">
          <RouterLink
            v-for="(item, index) in items"
            :key="item.to"
            :to="item.to"
            class="pill-nav__row"
            :data-active="index === activeIndex ? '' : undefined"
            @click="open = false"
          >
            <span>{{ item.label }}</span>
            <span v-if="item.badge" class="pill-nav__badge pill-nav__badge--row">{{ item.badge }}</span>
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" class="pill-nav__arrow">
              <path d="M3 8h9M8.5 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </RouterLink>
        </div>
      </Transition>
    </div>

    <div ref="measureRef" class="pill-nav__measure" aria-hidden="true">
      <span v-for="item in items" :key="item.to" class="pill-nav__measure-item">{{ item.label }}</span>
    </div>
  </nav>
</template>

<style scoped>
.pill-nav {
  --pn-h: 46px;
  --pn-pad: 5px;
  --pn-font: 13.5px;
  --pn-x: 18px;
  --ind-x: 0px;
  --ind-w: 0px;
  position: relative;
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: center;
  font-size: var(--pn-font);
  line-height: 1;
  -webkit-tap-highlight-color: transparent;
}

.pill-nav[data-size='sm'] {
  --pn-h: 40px;
  --pn-font: 12.5px;
  --pn-x: 15px;
}

.pill-nav__inner {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 0;
}

.pill-nav__bar {
  position: relative;
  display: flex;
  align-items: center;
  height: var(--pn-h);
  padding: var(--pn-pad);
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--paper-raised);
  box-shadow: 4px 4px 0 var(--ink);
}

.pill-nav__indicator {
  position: absolute;
  top: var(--pn-pad);
  bottom: var(--pn-pad);
  left: 0;
  width: var(--ind-w);
  transform: translateX(var(--ind-x));
  border-radius: 999px;
  background: var(--ink);
  box-shadow: none;
  opacity: 0;
  transition:
    transform 560ms var(--ease-out-soft),
    width 480ms var(--ease-out-soft),
    opacity 260ms var(--ease-out);
  pointer-events: none;
}

.pill-nav__indicator.is-ready {
  opacity: 1;
}

.pill-nav__list {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: stretch;
  gap: 2px;
  height: calc(var(--pn-h) - var(--pn-pad) * 2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.pill-nav__item {
  position: relative;
  display: flex;
}

.pill-nav__link {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 100%;
  padding: 0 var(--pn-x);
  border-radius: 999px;
  color: var(--ink);
  font-family: var(--font-display);
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  text-decoration: none;
  transition: color 360ms var(--ease-out);
}

.pill-nav__link::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  border-radius: inherit;
  background: color-mix(in srgb, var(--ink) 7%, transparent);
  opacity: 0;
  transform: scale(0.82);
  transition:
    opacity 300ms var(--ease-out),
    transform 420ms var(--ease-out);
}

.pill-nav__item:hover .pill-nav__link::before {
  opacity: 1;
  transform: scale(1);
}

.pill-nav__item[data-active] .pill-nav__link {
  color: #fff6e8;
}

.pill-nav__item[data-active] .pill-nav__link::before {
  opacity: 0;
}

.pill-nav__label {
  position: relative;
  display: block;
  height: 1em;
  overflow: hidden;
}

.pill-nav__label-line {
  display: block;
  height: 1em;
  line-height: 1;
  transition: transform 520ms var(--ease-out);
}

.pill-nav__label-line--alt {
  position: absolute;
  top: 100%;
  left: 0;
}

.pill-nav__item:hover .pill-nav__label-line {
  transform: translateY(-100%);
}

.pill-nav__badge {
  display: inline-flex;
  min-width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  padding: 0 4px;
  background: var(--coral);
  color: #2b1b08;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.pill-nav__item[data-active] .pill-nav__badge {
  background: #ff8a00;
}

.pill-nav__dot {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: var(--coral);
  opacity: 0;
  transform: translateX(calc(var(--ind-x) + var(--ind-w) / 2 - 2px));
  transition:
    transform 560ms var(--ease-out-soft),
    opacity 260ms var(--ease-out);
}

.pill-nav__dot.is-ready {
  opacity: 1;
}

.pill-nav__collapsed {
  position: relative;
  display: flex;
  width: 100%;
  justify-content: flex-end;
}

.pill-nav__toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 42px;
  padding: 0 18px;
  border: 1px solid color-mix(in srgb, var(--line) 88%, transparent);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 250, 241, 0.82), rgba(251, 246, 238, 0.58));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 14px 30px -26px rgba(54, 54, 54, 0.55);
  -webkit-backdrop-filter: blur(18px) saturate(1.6);
  backdrop-filter: blur(18px) saturate(1.6);
  color: var(--ink);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 420ms var(--ease-out),
    border-color 300ms var(--ease-out);
}

.pill-nav__toggle:active {
  transform: scale(0.97);
}

.pill-nav__burger {
  position: relative;
  display: block;
  width: 15px;
  height: 10px;
}

.pill-nav__burger > span {
  position: absolute;
  left: 0;
  width: 100%;
  height: 1.5px;
  border-radius: 2px;
  background: currentColor;
  transition:
    transform 460ms var(--ease-out),
    top 460ms var(--ease-out);
}

.pill-nav__burger > span:first-child {
  top: 1.5px;
}

.pill-nav__burger > span:last-child {
  top: 7px;
}

.pill-nav__burger[data-open] > span:first-child {
  top: 4.25px;
  transform: rotate(45deg);
}

.pill-nav__burger[data-open] > span:last-child {
  top: 4.25px;
  transform: rotate(-45deg);
}

.pill-nav__panel {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  display: grid;
  gap: 2px;
  min-width: 190px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: rgba(255, 252, 246, 0.94);
  box-shadow: 0 24px 50px -28px rgba(54, 54, 54, 0.6);
  -webkit-backdrop-filter: blur(20px) saturate(1.6);
  backdrop-filter: blur(20px) saturate(1.6);
  z-index: 60;
}

.pill-nav__row {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 42px;
  padding: 0 14px;
  border-radius: 14px;
  color: var(--ink);
  font-size: 14px;
  font-weight: 550;
  text-decoration: none;
  transition: background-color 240ms var(--ease-out);
}

.pill-nav__row[data-active] {
  background: color-mix(in srgb, var(--coral) 12%, transparent);
  color: var(--coral-dark);
}

.pill-nav__row:hover {
  background: color-mix(in srgb, var(--ink) 6%, transparent);
}

.pill-nav__arrow {
  margin-left: auto;
  opacity: 0.4;
}

.pill-nav__badge--row {
  background: var(--coral-soft);
  color: var(--coral-dark);
}

.pill-nav__measure {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  gap: 2px;
  visibility: hidden;
  pointer-events: none;
  white-space: nowrap;
}

.pill-nav[data-collapsed] .pill-nav__measure {
  display: none;
}

.pill-nav__measure-item {
  padding: 0 var(--pn-x);
  font-size: var(--pn-font);
  font-weight: 550;
}

.pill-panel-enter-active,
.pill-panel-leave-active {
  transition:
    opacity 240ms var(--ease-out),
    transform 320ms var(--ease-out);
  transform-origin: top right;
}

.pill-panel-enter-from,
.pill-panel-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.96);
}

@media (prefers-reduced-motion: reduce) {
  .pill-nav__indicator,
  .pill-nav__dot,
  .pill-nav__label-line,
  .pill-nav__link::before,
  .pill-panel-enter-active,
  .pill-panel-leave-active {
    transition: none;
  }
}
</style>
