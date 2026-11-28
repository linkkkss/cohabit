<script setup lang="ts">
/**
 * FlowingMenu — React Bits <FlowingMenu /> 的 Vue 版（Bauhaus 皮肤）。
 * 整屏菜单；悬停时一条橙色带在行间滑动，带内文字持续流动。
 */
import { onBeforeUnmount, ref } from 'vue'

export interface FlowingItem {
  key: string
  label: string
  meta?: string
}

const props = defineProps<{ items: FlowingItem[]; open: boolean; active?: string }>()
const emit = defineEmits<{ (event: 'select', key: string): void; (event: 'close'): void }>()

const listRef = ref<HTMLElement | null>(null)
const band = ref({ top: 0, height: 0, index: -1, visible: false })
const label = ref('')
let raf = 0

const move = (index: number, event: PointerEvent): void => {
  const list = listRef.value
  if (!list) return
  const row = (event.currentTarget as HTMLElement).closest('li') as HTMLElement | null
  if (!row) return
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    band.value = {
      top: row.offsetTop,
      height: row.offsetHeight,
      index,
      visible: true,
    }
    label.value = props.items[index]?.label ?? ''
  })
}

const leave = (): void => {
  band.value = { ...band.value, visible: false, index: -1 }
}

onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<template>
  <Transition name="flow">
    <div v-if="open" class="flow" role="dialog" aria-modal="true" aria-label="全站菜单">
      <div class="flow__head">
        <span class="flow__eyebrow">MENU · 全部页面</span>
        <button type="button" class="flow__close" aria-label="关闭菜单" @click="emit('close')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
          </svg>
        </button>
      </div>

      <div class="flow__stage">
        <div class="flow__listwrap">
        <div
          class="flow__band"
          :class="{ 'is-on': band.visible }"
          :style="{ transform: `translateY(${band.top}px)`, height: `${band.height}px` }"
          aria-hidden="true"
        >
          <div class="flow__track">
            <span v-for="n in 4" :key="n" class="flow__word">{{ label }}</span>
          </div>
        </div>

        <ul ref="listRef" class="flow__list" @pointerleave="leave">
          <li
            v-for="(item, index) in items"
            :key="item.key"
            class="flow__row"
            :class="{ 'is-active': item.key === active, 'is-lit': band.index === index }"
            @pointerenter="move(index, $event)"
          >
            <button type="button" class="flow__link" @click="emit('select', item.key)">
              <span class="flow__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="flow__label">{{ item.label }}</span>
              <span class="flow__meta">{{ item.meta }}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8" stroke-linecap="round" stroke-linejoin="round" /></svg></span>
            </button>
          </li>
        </ul>
        </div>
      </div>

      <p class="flow__foot">Esc 关闭 · 点击任意一行进入</p>
    </div>
  </Transition>
</template>

<style scoped>
.flow {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  flex-direction: column;
  padding: 22px clamp(18px, 4vw, 44px) 26px;
  background-color: var(--paper);
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.05) 1px, transparent 1px);
  background-size: 56px 56px;
}

.flow__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--ink);
}

.flow__eyebrow {
  display: inline-flex;
  padding: 7px 10px;
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  color: var(--coral-dark);
  font-family: var(--font-display);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.18em;
}

.flow__close {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 2px solid var(--ink);
  border-radius: 4px;
  background: var(--paper-raised);
  box-shadow: 3px 3px 0 var(--ink);
  color: var(--ink);
  cursor: pointer;
  transition: transform 160ms var(--ease-out);
}

.flow__close:hover {
  transform: translate(-1px, -1px);
}

.flow__close svg {
  width: 20px;
  height: 20px;
}

.flow__stage {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  min-height: 0;
}

.flow__listwrap {
  position: relative;
  width: 100%;
}

.flow__list {
  position: relative;
  z-index: 2;
  width: 100%;
  margin: 0;
  padding: 0;
  list-style: none;
}

.flow__row {
  border-top: 1.5px solid var(--line-strong);
}

.flow__row:last-child {
  border-bottom: 1.5px solid var(--line-strong);
}

.flow__link {
  display: grid;
  grid-template-columns: 64px 1fr auto;
  align-items: center;
  gap: 18px;
  width: 100%;
  padding: clamp(10px, 1.8vh, 20px) 6px;
  border: 0;
  background: none;
  color: var(--ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: opacity 220ms var(--ease-out);
}

.flow__index {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

.flow__label {
  font-family: var(--font-display);
  font-size: clamp(30px, 5.2vw, 64px);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.06;
}

.flow__meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12.5px;
}

.flow__meta svg {
  width: 18px;
  height: 18px;
}

.flow__row.is-lit .flow__link {
  color: var(--ink);
}

.flow__row.is-lit .flow__label {
  color: transparent;
  transition: color 180ms var(--ease-out);
}

.flow__row.is-lit .flow__index,
.flow__row.is-lit .flow__meta {
  color: color-mix(in srgb, var(--ink) 62%, transparent);
}

.flow__row.is-active .flow__label::after {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 12px;
  border-radius: 50%;
  background: var(--coral);
  vertical-align: middle;
}

.flow__band {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1;
  overflow: hidden;
  border-radius: 6px;
  background: var(--coral);
  opacity: 0;
  transform-origin: left center;
  transition:
    transform 420ms cubic-bezier(0.22, 1, 0.36, 1),
    height 420ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 200ms var(--ease-out);
  pointer-events: none;
}

.flow__band.is-on {
  opacity: 1;
}

.flow__track {
  display: flex;
  align-items: center;
  gap: 44px;
  width: max-content;
  height: 100%;
  padding-left: 48px;
  animation: flow-run 14s linear infinite;
}

.flow__word {
  color: var(--ink);
  font-family: var(--font-display);
  font-size: clamp(26px, 4.6vw, 58px);
  font-weight: 700;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.flow__foot {
  margin: 0;
  color: var(--muted);
  font-family: var(--font-mono, var(--font-display));
  font-size: 11px;
  letter-spacing: 0.12em;
}

@keyframes flow-run {
  to {
    transform: translateX(-50%);
  }
}

.flow-enter-active,
.flow-leave-active {
  transition:
    clip-path 520ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 320ms var(--ease-out);
}

.flow-enter-from,
.flow-leave-to {
  clip-path: inset(0 0 100% 0);
  opacity: 0.4;
}

.flow-enter-to,
.flow-leave-from {
  clip-path: inset(0 0 0 0);
}

@media (max-width: 620px) {
  .flow__link {
    grid-template-columns: 38px 1fr;
    gap: 10px;
  }

  .flow__meta {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .flow__band,
  .flow__track,
  .flow-enter-active,
  .flow-leave-active {
    transition: none;
    animation: none;
  }
}
</style>
