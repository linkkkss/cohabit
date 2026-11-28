<script setup lang="ts">
/**
 * Dock — macOS 式放大 dock 的 Vue 版（Bauhaus 皮肤）。
 * 指针靠近时图标按距离放大并上浮；含角标、激活点、工具提示。
 */
import { onBeforeUnmount, ref } from 'vue'

export interface DockItem {
  key: string
  label: string
  glyph: 'home' | 'plaza' | 'match' | 'profile' | 'menu'
  badge?: string | number
  active?: boolean
}

const props = withDefaults(
  defineProps<{
    items: DockItem[]
    base?: number
    peak?: number
    distance?: number
  }>(),
  { base: 46, peak: 72, distance: 150 },
)

const emit = defineEmits<{ (event: 'select', item: DockItem): void }>()

const rootRef = ref<HTMLElement | null>(null)
const hovered = ref(-1)
const lift = ref<number[]>(props.items.map(() => 0))
let raf = 0
let target = props.items.map(() => 0)

const paths: Record<DockItem['glyph'], string> = {
  home: 'M4 11.5 12 4l8 7.5V20h-6v-5h-4v5H4z',
  plaza: 'M4 5h7v7H4zM13 5h7v7h-7zM4 14h7v5H4zM13 14h7v5h-7z',
  match: 'M12 20s-7-4.3-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.7-7 9-7 9z',
  profile: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20a7 7 0 0 1 14 0',
  menu: 'M4 7h16M4 12h16M4 17h16',
}

const animate = (): void => {
  raf = 0
  const next = target.map((value, index) => lift.value[index] + (value - lift.value[index]) * 0.35)
  lift.value = next
  const busy = next.some((value, index) => Math.abs(value - target[index]) > 0.002)
  if (busy) raf = requestAnimationFrame(animate)
}

const wake = (): void => {
  if (!raf) raf = requestAnimationFrame(animate)
}

const onMove = (event: PointerEvent): void => {
  const root = rootRef.value
  if (!root) return
  const buttons = Array.from(root.querySelectorAll<HTMLElement>('[data-dock-item]'))
  const x = event.clientX
  target = buttons.map((button) => {
    const rect = button.getBoundingClientRect()
    const center = rect.left + rect.width / 2
    const reach = 1 - Math.min(1, Math.abs(x - center) / props.distance)
    return Math.max(0, reach) ** 2.2
  })
  wake()
}

const onLeave = (): void => {
  hovered.value = -1
  target = props.items.map(() => 0)
  wake()
}

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
})
</script>

<template>
  <nav ref="rootRef" class="dock" aria-label="页面快捷导航" @pointermove="onMove" @pointerleave="onLeave">
    <button
      v-for="(item, index) in items"
      :key="item.key"
      type="button"
      data-dock-item
      class="dock__item"
      :class="{ 'is-active': item.active, 'is-menu': item.glyph === 'menu' }"
      :style="{ '--lift': lift[index].toFixed(3) }"
      :aria-label="item.label"
      :aria-current="item.active ? 'page' : undefined"
      @pointerenter="hovered = index"
      @click="emit('select', item)"
    >
      <span class="dock__tile">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path :d="paths[item.glyph]" />
        </svg>
        <span v-if="item.badge" class="dock__badge">{{ item.badge }}</span>
      </span>
      <span class="dock__dot" aria-hidden="true" />
      <span class="dock__label" :class="{ 'is-on': hovered === index }" aria-hidden="true">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.dock {
  position: fixed;
  bottom: 18px;
  left: 50%;
  z-index: 40;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px;
  border: 2px solid var(--ink);
  border-radius: 16px;
  background: color-mix(in srgb, var(--paper-raised) 92%, transparent);
  box-shadow:
    5px 5px 0 var(--ink),
    0 18px 40px -28px rgba(54, 54, 54, 0.7);
  backdrop-filter: blur(14px) saturate(1.2);
  transform: translateX(-50%);
}

.dock__item {
  position: relative;
  display: grid;
  place-items: center;
  width: calc(var(--dock-base, 46px) * (1 + var(--lift, 0) * 0.52));
  height: calc(var(--dock-base, 46px) * (1 + var(--lift, 0) * 0.52));
  margin: 0;
  padding: 0;
  border: 0;
  background: none;
  color: var(--ink);
  cursor: pointer;
  transform: translateY(calc(var(--lift, 0) * -10px));
  transform-origin: 50% 100%;
}

.dock__tile {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  border: 1.5px solid var(--ink);
  border-radius: calc(8px + var(--lift, 0) * 5px);
  background: var(--paper);
  box-shadow: 2px 2px 0 rgba(54, 54, 54, calc(0.28 + var(--lift, 0) * 0.5));
  transition: background-color 160ms var(--ease-out);
}

.dock__item:hover .dock__tile,
.dock__item:focus-visible .dock__tile {
  background: var(--coral);
}

.dock__item.is-active .dock__tile {
  background: var(--coral);
  color: var(--ink);
}

.dock__item:focus-visible {
  outline: none;
}

.dock__item:focus-visible .dock__tile {
  outline: 2px solid var(--coral-dark);
  outline-offset: 3px;
}

.dock__tile svg {
  width: 52%;
  height: 52%;
}

.dock__badge {
  position: absolute;
  top: -7px;
  right: -7px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--coral);
  color: var(--ink);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  line-height: 15px;
  text-align: center;
}

.dock__dot {
  position: absolute;
  bottom: -6px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: transparent;
}

.dock__item.is-active .dock__dot {
  background: var(--ink);
}

.dock__label {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 50%;
  padding: 5px 8px;
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--paper-raised);
  color: var(--ink);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transform: translate(-50%, 4px);
  transition:
    opacity 140ms var(--ease-out),
    transform 140ms var(--ease-out);
}

.dock__label.is-on {
  opacity: 1;
  transform: translate(-50%, 0);
}

.dock__item.is-menu .dock__tile {
  border-style: dashed;
}

@media (max-width: 900px) {
  .dock {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dock__item,
  .dock__label,
  .dock__tile {
    transition: none;
  }
}
</style>
