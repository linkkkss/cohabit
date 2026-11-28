<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    initial: string
    score: number
    college?: string
    grade?: string
    tone?: 'light' | 'ink'
  }>(),
  { college: '', grade: '', tone: 'light' },
)

const angle = ref(0)
const dragging = ref(false)
let velocity = 0
let raf = 0
let last = 0
let reduce = false
let startX = 0
let startAngle = 0
let lastX = 0
let lastT = 0

const K = 46
const C = 3.4

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v))

function frame(now: number) {
  raf = 0
  const dt = last ? Math.min(1 / 30, (now - last) / 1000) : 1 / 60
  last = now
  velocity += (-K * angle.value - C * velocity) * dt
  angle.value += velocity * dt
  if (Math.abs(angle.value) < 0.04 && Math.abs(velocity) < 0.04) {
    angle.value = 0
    velocity = 0
    last = 0
    return
  }
  raf = requestAnimationFrame(frame)
}

function wake() {
  if (reduce || raf) return
  last = 0
  raf = requestAnimationFrame(frame)
}

function onDown(event: PointerEvent) {
  if (reduce || event.button > 0) return
  dragging.value = true
  startX = event.clientX
  startAngle = angle.value
  lastX = event.clientX
  lastT = event.timeStamp
  velocity = 0
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
  cancelAnimationFrame(raf)
  raf = 0
}

function onMove(event: PointerEvent) {
  if (!dragging.value) return
  const dx = event.clientX - startX
  angle.value = clamp(startAngle + dx * 0.3, -52, 52)
  const dt = Math.max(8, event.timeStamp - lastT)
  velocity = clamp(((event.clientX - lastX) / dt) * 24, -160, 160)
  lastX = event.clientX
  lastT = event.timeStamp
}

function onUp() {
  if (!dragging.value) return
  dragging.value = false
  wake()
}

onMounted(() => {
  reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
})
</script>

<template>
  <div class="swing" :class="{ 'is-dragging': dragging }">
    <div class="swing__rail" aria-hidden="true">
      <span class="swing__pin" />
    </div>

    <div
      class="swing__tag"
      :class="`swing__tag--${tone}`"
      :style="{ transform: `rotate(${angle.toFixed(2)}deg)` }"
      role="img"
      :aria-label="`${name} 的今日匹配吊牌，匹配度 ${score}%`"
      @pointerdown="onDown"
      @pointermove="onMove"
      @pointerup="onUp"
      @pointercancel="onUp"
      @pointerleave="onUp"
    >
      <span class="swing__strap" aria-hidden="true" />
      <span class="swing__clamp" aria-hidden="true" />

      <div class="swing__card">
        <span class="swing__hole" aria-hidden="true" />
        <span class="swing__kicker">TODAY · 今日匹配</span>
        <span class="swing__score">{{ score }}<em>%</em></span>
        <span class="swing__initial">{{ initial }}</span>
        <div class="swing__info">
          <strong>{{ name }}</strong>
          <small>{{ college }}<template v-if="grade"> · {{ grade }}</template></small>
        </div>
      </div>
    </div>

    <p class="swing__hint">拖一下吊牌 · DRAG THE TAG</p>
  </div>
</template>

<style scoped>
.swing {
  position: relative;
  width: 100%;
  max-width: 300px;
  padding: 24px 0 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  touch-action: none;
  user-select: none;
}

.swing__rail {
  position: relative;
  width: 2px;
  height: 26px;
  background: var(--ink);
  opacity: 0.5;
}

.swing__pin {
  position: absolute;
  top: -5px;
  left: 50%;
  width: 8px;
  height: 8px;
  margin-left: -4px;
  border-radius: 50%;
  background: var(--ink);
}

.swing__tag {
  position: relative;
  width: 244px;
  margin-top: 0;
  transform-origin: 50% 0;
  cursor: grab;
}

.swing.is-dragging .swing__tag {
  cursor: grabbing;
  transition: none;
}

.swing__strap {
  position: absolute;
  top: 0;
  left: 50%;
  width: 26px;
  height: 78px;
  margin-left: -13px;
  background: linear-gradient(90deg, #4a443c 0%, #2b2722 50%, #4a443c 100%);
  box-shadow: inset 2px 0 0 rgba(255, 244, 226, 0.14), inset -2px 0 0 rgba(255, 244, 226, 0.14);
}

.swing__clamp {
  position: absolute;
  top: 62px;
  left: 50%;
  width: 54px;
  height: 16px;
  margin-left: -27px;
  border: 2px solid var(--ink);
  border-radius: 3px;
  background: linear-gradient(180deg, #fff6e8 0%, #e6d3b4 46%, #bda98a 100%);
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.35);
}

.swing__card {
  position: relative;
  margin-top: 74px;
  padding: 34px 18px 16px;
  border: 2px solid var(--ink);
  border-radius: 18px;
  background: linear-gradient(165deg, #fffaf0 0%, #f7ead6 55%, #efdcc0 100%);
  box-shadow: 8px 10px 0 rgba(54, 54, 54, 0.14);
  overflow: hidden;
}

.swing__tag--ink .swing__card {
  border-color: #1d1a16;
  background: linear-gradient(165deg, #3d3a35 0%, #2b2824 55%, #211f1c 100%);
  color: #fff4e2;
}

.swing__hole {
  position: absolute;
  top: 7px;
  left: 50%;
  width: 18px;
  height: 18px;
  margin-left: -9px;
  border-radius: 50%;
  background: var(--ink);
  box-shadow: 0 0 0 3px #f3e4cd;
}

.swing__tag--ink .swing__hole {
  box-shadow: 0 0 0 3px #2b2824;
}

.swing__kicker {
  display: block;
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.16em;
}

.swing__tag--ink .swing__kicker {
  color: rgba(255, 244, 226, 0.55);
}

.swing__score {
  position: absolute;
  top: 30px;
  right: 14px;
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  padding: 4px 9px;
  border: 1.5px solid var(--ink);
  border-radius: 999px;
  background: var(--paper-raised);
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
}

.swing__score em {
  color: var(--coral-dark);
  font-size: 9px;
  font-style: normal;
}

.swing__tag--ink .swing__score {
  border-color: rgba(255, 244, 226, 0.35);
  background: rgba(255, 244, 226, 0.08);
  color: #fff4e2;
}

.swing__tag--ink .swing__score em {
  color: #ffb45e;
}

.swing__initial {
  display: grid;
  place-items: center;
  height: 150px;
  font-family: 'Songti SC', 'Noto Serif SC', 'SimSun', serif;
  font-size: 88px;
  line-height: 1;
}

.swing__tag--ink .swing__initial {
  color: #ffb45e;
}

.swing__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 10px;
  border-top: 1.5px solid color-mix(in srgb, var(--ink) 22%, transparent);
}

.swing__tag--ink .swing__info {
  border-top-color: rgba(255, 244, 226, 0.22);
}

.swing__info strong {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.swing__info small {
  color: var(--muted);
  font-size: 11.5px;
}

.swing__tag--ink .swing__info small {
  color: rgba(255, 244, 226, 0.62);
}

.swing__hint {
  margin: 26px 0 0;
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 9.5px;
  letter-spacing: 0.16em;
}

@media (prefers-reduced-motion: reduce) {
  .swing__tag {
    transition: none;
  }
}
</style>
