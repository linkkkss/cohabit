<script setup lang="ts" generic="T">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type Autoplay = 'drift' | 'off'

const props = withDefaults(
  defineProps<{
    items: readonly T[]
    active?: number
    cardWidth?: number
    ratio?: number
    gap?: number
    tilt?: number
    perspective?: number
    speed?: number
    autoplay?: Autoplay
    draggable?: boolean
    snap?: boolean
    pauseOnHover?: boolean
    depthFade?: number
    fadeColor?: string
    cornerRadius?: number
    ariaLabel?: string
  }>(),
  {
    active: 0,
    cardWidth: 238,
    ratio: 0.8,
    gap: 34,
    tilt: -7,
    perspective: 2400,
    speed: 4.2,
    autoplay: 'drift',
    draggable: true,
    snap: true,
    pauseOnHover: true,
    depthFade: 0.5,
    fadeColor: '#f7e4c8',
    cornerRadius: 22,
    ariaLabel: '同学旋转木马',
  },
)

const emit = defineEmits<{
  'update:active': [index: number]
  select: [index: number]
}>()

defineSlots<{
  default?: (props: { item: T; index: number; active: boolean }) => unknown
}>()

const rootRef = ref<HTMLElement | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const cameraRef = ref<HTMLElement | null>(null)
const ringRef = ref<HTMLElement | null>(null)
const cardEls = ref<HTMLElement[]>([])
const activeIndex = ref(0)
const dragging = ref(false)
const ready = ref(false)

const count = computed(() => Math.max(props.items.length, 1))
const step = computed(() => 360 / count.value)
const cardW = ref(props.cardWidth)
const cardH = computed(() => cardW.value / Math.max(props.ratio, 0.4))
const radius = computed(() => {
  const n = Math.max(count.value, 3)
  const pitch = cardW.value + props.gap
  return Math.max(pitch / (2 * Math.sin(Math.PI / n)), cardW.value * 0.72)
})

const rootStyle = computed(() => ({
  '--cc-w': `${cardW.value}px`,
  '--cc-h': `${cardH.value}px`,
  '--cc-fade': props.fadeColor,
  '--cc-radius': `${props.cornerRadius}px`,
  '--cc-depth-fade': String(props.depthFade),
}))

const state = {
  angle: 0,
  velocity: 0,
  target: null as number | null,
  hover: false,
  manual: false,
  fit: 1,
  step: 0,
  press: null as null | { id: number; x: number; angle: number; moved: boolean; samples: { t: number; a: number }[] },
  suppressClick: false,
}

let frameId = 0
let lastTime = 0
let resizeObserver: ResizeObserver | null = null
let visible = true
let intersectionObserver: IntersectionObserver | null = null

const prefersReduced = (): boolean =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

const wrap = (value: number): number => ((((value + 180) % 360) + 360) % 360) - 180

const measure = (): void => {
  const root = rootRef.value
  const stage = stageRef.value
  if (!root || !stage) return
  const rect = root.getBoundingClientRect()
  if (!rect.width || !rect.height) return

  cardW.value = Math.max(120, Math.min(props.cardWidth, rect.width * 0.62))
  const R = radius.value
  const P = props.perspective
  const tilt = (props.tilt * Math.PI) / 180
  const cosT = Math.cos(tilt)
  const sinT = Math.sin(tilt)
  const halfW = cardW.value / 2
  const halfH = cardH.value / 2

  let maxX = 1
  let maxY = 1

  for (let a = -180; a <= 180; a += 7.5) {
    const rad = (a * Math.PI) / 180
    const cos = Math.cos(rad)
    const sin = Math.sin(rad)
    for (const corner of [
      [-halfW, -halfH],
      [halfW, -halfH],
      [-halfW, halfH],
      [halfW, halfH],
    ]) {
      const x = corner[0]! * cos + R * sin
      const z = -corner[0]! * sin + R * cos
      const y = corner[1]!
      const y2 = y * cosT - z * sinT
      const z2 = y * sinT + z * cosT - R
      if (z2 >= P * 0.96) continue
      const k = P / (P - z2)
      maxX = Math.max(maxX, Math.abs(x * k))
      maxY = Math.max(maxY, Math.abs(y2 * k))
    }
  }

  const fitted = Math.min(1, (rect.width * 0.88) / (maxX * 2), (rect.height * 0.86) / (maxY * 2))
  // On narrow screens let the ring bleed past the stage edges: a larger card reads
  // better than a fully-fitted, tiny ring.
  const fit = rect.width < 560 ? Math.max(fitted, 0.8) : fitted
  state.fit = fit
  stage.style.perspective = `${P}px`
  stage.style.transform = `scale(${fit})`
}

const render = (): void => {
  const camera = cameraRef.value
  const ring = ringRef.value
  if (!camera || !ring) return
  const R = radius.value
  const angle = state.angle

  camera.style.transform = `translate3d(0, 0, ${-R}px) rotateX(${props.tilt}deg)`
  ring.style.transform = `rotateY(${angle}deg)`

  const list = cardEls.value
  for (let index = 0; index < list.length; index += 1) {
    const card = list[index]
    if (!card) continue
    const base = index * step.value
    card.style.transform = `rotateY(${base}deg) translateZ(${R}px)`
    const world = wrap(base + angle)
    const facing = Math.cos((world * Math.PI) / 180)
    const depth = Math.pow((1 - facing) / 2, 0.8) * props.depthFade
    card.style.setProperty('--cc-depth', depth.toFixed(3))
    card.style.visibility = facing < -0.02 ? 'hidden' : ''
    card.setAttribute('aria-hidden', Math.abs(world) > 90 ? 'true' : 'false')
  }

  const index = ((Math.round(-angle / step.value) % count.value) + count.value) % count.value || 0
  if (index !== activeIndex.value) {
    activeIndex.value = index
    emit('update:active', index)
  }
}

const frame = (now: number): void => {
  frameId = 0
  const dt = lastTime ? Math.min((now - lastTime) / 1000, 0.05) : 1 / 60
  lastTime = now
  let busy = false

  if (state.target !== null) {
    let remaining = dt
    const stiffness = 120
    const damping = 2 * Math.sqrt(stiffness)
    while (remaining > 0) {
      const h = Math.min(remaining, 1 / 240)
      const accel = stiffness * (state.target - state.angle) - damping * state.velocity
      state.velocity += accel * h
      state.angle += state.velocity * h
      remaining -= h
    }
    if (Math.abs(state.target - state.angle) < 0.01 && Math.abs(state.velocity) < 0.08) {
      state.angle = state.target
      state.velocity = 0
      state.target = null
    }
    busy = true
  } else if (!state.press) {
    const drifting = props.autoplay === 'drift' && !state.manual && !(props.pauseOnHover && state.hover)
    const cruise = drifting && !prefersReduced() ? -props.speed : 0
    state.velocity += (cruise - state.velocity) * (1 - Math.exp(-dt / 0.24))
    state.angle += state.velocity * dt
    if (Math.abs(state.velocity) > 0.01 || cruise !== 0) busy = true
    if (!drifting && props.snap && Math.abs(state.velocity) < 6 && state.velocity !== 0) {
      state.target = Math.round((state.angle + state.velocity * 0.12) / step.value) * step.value
      busy = true
    }
  } else {
    busy = true
  }

  render()
  if (busy && visible) frameId = requestAnimationFrame(frame)
  else lastTime = 0
}

const wake = (): void => {
  if (!frameId && visible) {
    if (!lastTime) lastTime = performance.now()
    frameId = requestAnimationFrame(frame)
  }
}

const focus = (index: number, fromOutside = false): void => {
  const n = count.value
  const safe = ((index % n) + n) % n
  let target = -safe * step.value
  target += 360 * Math.round((state.angle - target) / 360)
  state.target = target
  state.velocity = 0
  state.manual = true
  activeIndex.value = safe
  emit('update:active', safe)
  if (!fromOutside) emit('select', safe)
  wake()
}

const stepBy = (delta: number): void => {
  const base = state.target ?? Math.round(state.angle / step.value) * step.value
  state.target = base + delta * step.value
  state.velocity = 0
  state.manual = true
  wake()
}

const nudge = (): void => {
  if (!state.manual) state.manual = true
}

const onPointerDown = (event: PointerEvent): void => {
  if (!props.draggable || event.button !== 0) return
  state.suppressClick = false
  state.press = {
    id: event.pointerId,
    x: event.clientX,
    angle: state.angle,
    moved: false,
    samples: [{ t: performance.now(), a: state.angle }],
  }
  state.target = null
  state.velocity = 0
}

const onPointerMove = (event: PointerEvent): void => {
  const press = state.press
  if (!press || press.id !== event.pointerId) return
  const delta = event.clientX - press.x
  if (!press.moved) {
    if (Math.abs(delta) < 5) return
    press.moved = true
    dragging.value = true
    state.manual = true
    try {
      rootRef.value?.setPointerCapture(event.pointerId)
    } catch {
      /* capture is best effort */
    }
  }
  const degPerPx = 180 / (Math.PI * radius.value * state.fit)
  state.angle = press.angle + delta * degPerPx
  press.samples.push({ t: performance.now(), a: state.angle })
  while (press.samples.length > 2 && performance.now() - press.samples[0]!.t > 110) press.samples.shift()
  wake()
}

const endPress = (event: PointerEvent): void => {
  const press = state.press
  if (!press || press.id !== event.pointerId) return
  state.press = null
  dragging.value = false
  if (!press.moved) return
  state.suppressClick = true
  const first = press.samples[0]!
  const last = press.samples[press.samples.length - 1]!
  const span = (last.t - first.t) / 1000
  const velocity = span > 0.008 ? Math.max(-900, Math.min(900, (last.a - first.a) / span)) : 0
  state.velocity = velocity
  state.target = props.snap
    ? Math.round((state.angle + velocity * 0.16) / step.value) * step.value
    : null
  wake()
}

const onClick = (event: MouseEvent): void => {
  if (state.suppressClick) {
    state.suppressClick = false
    return
  }
  const target = event.target as HTMLElement | null
  const card = target?.closest<HTMLElement>('[data-cc-index]')
  if (!card) return
  const index = Number(card.dataset.ccIndex)
  if (Number.isNaN(index)) return
  if (index === activeIndex.value) emit('select', index)
  else focus(index, true)
}

const onKeydown = (event: KeyboardEvent): void => {
  if (event.key === 'ArrowRight') stepBy(-1)
  else if (event.key === 'ArrowLeft') stepBy(1)
  else if (event.key === 'Enter' || event.key === ' ') emit('select', activeIndex.value)
  else return
  event.preventDefault()
}

const onEnter = (): void => {
  state.hover = true
}

const onLeave = (): void => {
  state.hover = false
}

watch(
  () => props.active,
  (value) => {
    if (typeof value === 'number' && value !== activeIndex.value) focus(value, true)
  },
)

watch(count, () => {
  if (activeIndex.value >= count.value) {
    activeIndex.value = 0
    emit('update:active', 0)
  }
  measure()
  wake()
})

onMounted(() => {
  measure()
  render()
  requestAnimationFrame(() => {
    ready.value = true
    measure()
    render()
    wake()
  })

  resizeObserver = new ResizeObserver(() => {
    measure()
    render()
    wake()
  })
  if (rootRef.value) resizeObserver.observe(rootRef.value)

  intersectionObserver = new IntersectionObserver(([entry]) => {
    visible = entry?.isIntersecting ?? true
    if (visible) wake()
    else {
      cancelAnimationFrame(frameId)
      frameId = 0
      lastTime = 0
    }
  })
  if (rootRef.value) intersectionObserver.observe(rootRef.value)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId)
  frameId = 0
  resizeObserver?.disconnect()
  intersectionObserver?.disconnect()
  resizeObserver = null
  intersectionObserver = null
})

defineExpose({ focus, next: () => stepBy(-1), prev: () => stepBy(1), nudge })
</script>

<template>
  <div
    ref="rootRef"
    class="cc"
    :class="{ 'is-ready': ready, 'is-dragging': dragging }"
    :style="rootStyle"
    role="region"
    aria-roledescription="carousel"
    :aria-label="ariaLabel"
    :tabindex="0"
    :data-draggable="draggable ? '' : undefined"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="endPress"
    @pointercancel="endPress"
    @pointerenter="onEnter"
    @pointerleave="onLeave"
    @click="onClick"
    @keydown="onKeydown"
  >
    <div ref="stageRef" class="cc__stage">
      <div ref="cameraRef" class="cc__camera">
        <div ref="ringRef" class="cc__ring">
          <div
            v-for="(item, index) in items"
            :key="index"
            ref="cardEls"
            class="cc__card"
            :data-cc-index="index"
            :data-front="index === activeIndex ? '' : undefined"
            role="group"
            aria-roledescription="slide"
          >
            <div class="cc__face">
              <slot :item="item" :index="index" :active="index === activeIndex" />
              <span class="cc__shade" aria-hidden="true" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cc {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  outline: none;
  touch-action: pan-y;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.cc.is-dragging {
  cursor: grabbing;
}

.cc:focus-visible {
  box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--coral) 70%, transparent);
  border-radius: 24px;
}

.cc__stage {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  opacity: 0;
  transform-origin: center;
  transition: opacity 520ms var(--ease-out);
}

.cc.is-ready .cc__stage {
  opacity: 1;
}

.cc__camera,
.cc__ring,
.cc__card {
  width: 0;
  height: 0;
  transform-style: preserve-3d;
}

.cc__camera {
  position: relative;
}

.cc__ring,
.cc__card {
  position: absolute;
  left: 0;
  top: 0;
}

.cc__card {
  transform-style: preserve-3d;
}

.cc__face {
  position: absolute;
  left: calc(var(--cc-w) / -2);
  top: calc(var(--cc-h) / -2);
  width: var(--cc-w);
  height: var(--cc-h);
  border-radius: var(--cc-radius);
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  overflow: hidden;
  background: var(--paper-raised);
  box-shadow:
    0 30px 60px -40px rgba(54, 54, 54, 0.6),
    inset 0 0 0 1px color-mix(in srgb, var(--line) 82%, transparent);
}

.cc__shade {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: var(--cc-fade);
  opacity: calc(var(--cc-depth, 0) * 1);
  pointer-events: none;
}

@media (prefers-reduced-motion: reduce) {
  .cc__stage {
    transition: none;
  }
}
</style>
