<script setup lang="ts">
/**
 * ProfileCard — React Bits <ProfileCard /> 的 Vue 移植（暖白 / 墨黑 / 橙）。
 * 3D 倾斜 + 跟随指针的光泽 + 头像视差；底部为身份与状态行。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    avatarUrl?: string
    name?: string
    title?: string
    handle?: string
    status?: string
    statusColor?: string
    contactText?: string
    showUserInfo?: boolean
    theme?: 'light' | 'dark'
    radius?: number
    holo?: number
    glare?: number
    enableTilt?: boolean
    tiltStrength?: number
    parallax?: number
    intro?: boolean
    initial?: string
    meta?: string
  }>(),
  {
    avatarUrl: '',
    name: '',
    title: '',
    handle: '',
    status: '',
    statusColor: '#ff8a00',
    contactText: '联系',
    showUserInfo: true,
    theme: 'light',
    radius: 20,
    holo: 0.55,
    glare: 0.6,
    enableTilt: true,
    tiltStrength: 9,
    parallax: 10,
    intro: true,
    initial: '',
    meta: '',
  },
)

const emit = defineEmits<{ (event: 'contact'): void }>()

const rootRef = ref<HTMLElement | null>(null)
let raf = 0
let cleanup: (() => void) | null = null

const fallbackInitial = computed(() => props.initial || props.name.slice(0, 1) || 'C')

const style = computed(() => ({
  '--pc-radius': `${Math.max(0, props.radius)}px`,
  '--pc-holo': String(Math.min(1, Math.max(0, props.holo))),
  '--pc-glare': String(Math.min(1, Math.max(0, props.glare))),
  '--pc-parallax': `${Math.max(0, props.parallax)}px`,
  '--pc-status': props.statusColor,
}))

onMounted(() => {
  const root = rootRef.value
  if (!root) return
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const state = { x: 0, y: 0, tx: 0, ty: 0, vx: 0, vy: 0, light: 0, target: 0, sx: -1, sy: -1, sTarget: 0, sOn: 0, spotX: 50, spotY: 50 }
  let last = 0

  const write = (): void => {
    const strength = reduce || !props.enableTilt ? 0 : Math.max(0, props.tiltStrength)
    const depth = reduce ? 0 : Math.max(0, props.parallax)
    const s = root.style
    s.setProperty('--pc-rx', `${(state.y * strength).toFixed(2)}deg`)
    s.setProperty('--pc-ry', `${(-state.x * strength).toFixed(2)}deg`)
    s.setProperty('--pc-gx', `${(((state.x + 1) / 2) * 100).toFixed(2)}%`)
    s.setProperty('--pc-gy', `${(((state.y + 1) / 2) * 100).toFixed(2)}%`)
    s.setProperty('--pc-shift-x', `${(state.x * depth).toFixed(2)}px`)
    s.setProperty('--pc-shift-y', `${(state.y * depth).toFixed(2)}px`)
    s.setProperty('--pc-active', (state.light / 100).toFixed(3))
    s.setProperty('--pc-sx', `${state.spotX.toFixed(2)}%`)
    s.setProperty('--pc-sy', `${state.spotY.toFixed(2)}%`)
    s.setProperty('--pc-spot', state.sOn.toFixed(3))
  }

  const frame = (now: number): void => {
    const dt = Math.min(0.05, (now - last) / 1000 || 1 / 60)
    last = now
    const steps = Math.max(1, Math.ceil(dt / (1 / 120)))
    const h = dt / steps
    for (let i = 0; i < steps; i += 1) {
      state.vx += (150 * (state.tx - state.x) - 18 * state.vx) * h
      state.x += state.vx * h
      state.vy += (150 * (state.ty - state.y) - 18 * state.vy) * h
      state.y += state.vy * h
    }
    state.light += (state.target - state.light) * (1 - Math.exp(-dt / 0.18))
    state.sOn += (state.sTarget - state.sOn) * (1 - Math.exp(-dt / (state.sTarget > state.sOn ? 0.12 : 0.32)))
    if (Math.abs(state.sTarget - state.sOn) < 0.002) state.sOn = state.sTarget
    write()
    const moving =
      Math.abs(state.tx - state.x) > 0.002 ||
      Math.abs(state.ty - state.y) > 0.002 ||
      Math.abs(state.vx) > 0.002 ||
      Math.abs(state.vy) > 0.002 ||
      Math.abs(state.target - state.light) > 0.4 ||
      Math.abs(state.sTarget - state.sOn) > 0.002
    if (moving) raf = requestAnimationFrame(frame)
    else {
      state.x = state.tx
      state.y = state.ty
      write()
      raf = 0
    }
  }

  const wake = (): void => {
    if (raf) return
    last = performance.now()
    raf = requestAnimationFrame(frame)
  }

  const aim = (event: PointerEvent): void => {
    const rect = root.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    state.tx = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width) * 2 - 1))
    state.ty = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height) * 2 - 1))
    state.target = 100
    state.spotX = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100))
    state.spotY = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100))
    state.sTarget = 1
    wake()
  }

  const release = (): void => {
    state.tx = 0
    state.ty = 0
    state.target = 0
    state.sTarget = 0
    wake()
  }

  const onEnter = (event: PointerEvent): void => {
    if (event.pointerType === 'mouse') aim(event)
  }
  const onMove = (event: PointerEvent): void => {
    if (event.pointerType === 'mouse') aim(event)
  }

  root.addEventListener('pointerenter', onEnter)
  root.addEventListener('pointermove', onMove)
  root.addEventListener('pointerleave', release)

  const observer = new ResizeObserver(() => write())
  observer.observe(root)

  if (props.intro && !reduce) {
    state.x = 0.7
    state.y = -0.6
    state.light = 100
    write()
    state.tx = 0
    state.ty = 0
    wake()
  } else {
    write()
  }

  cleanup = () => {
    cancelAnimationFrame(raf)
    raf = 0
    observer.disconnect()
    root.removeEventListener('pointerenter', onEnter)
    root.removeEventListener('pointermove', onMove)
    root.removeEventListener('pointerleave', release)
  }
})

onBeforeUnmount(() => {
  cleanup?.()
  cleanup = null
})
</script>

<template>
  <div
    ref="rootRef"
    class="pc"
    :data-theme="theme"
    :style="style"
    @click.self="emit('contact')"
  >
    <div class="pc__body">
      <span class="pc__spot" aria-hidden="true" />
      <span class="pc__spot-edge" aria-hidden="true" />
      <div class="pc__tile">
        <div class="pc__portrait">
          <img v-if="avatarUrl" class="pc__photo" :src="avatarUrl" :alt="name" loading="lazy" draggable="false" />
          <slot v-else name="portrait">
            <div class="pc__art" aria-hidden="true">
              <span class="pc__art-ring" />
              <span class="pc__art-ring pc__art-ring--late" />
              <span class="pc__art-initial">{{ fallbackInitial }}</span>
            </div>
          </slot>
        </div>

        <span class="pc__foil" aria-hidden="true" />
        <span class="pc__glare" aria-hidden="true" />
        <span class="pc__sheen" aria-hidden="true" />
        <span class="pc__scrim" aria-hidden="true" />
        <span class="pc__rim" aria-hidden="true" />

        <div v-if="name || title" class="pc__info">
          <h3 class="pc__name">{{ name }}</h3>
          <p v-if="title" class="pc__title">{{ title }}</p>
        </div>
      </div>

      <div v-if="showUserInfo" class="pc__footer">
        <div class="pc__meta">
          <span v-if="handle" class="pc__handle">{{ handle }}</span>
          <span v-if="status" class="pc__status">{{ status }}</span>
        </div>
        <button v-if="contactText" type="button" class="pc__contact" @click="emit('contact')">
          {{ contactText }}
          <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
            <path
              d="M3 8h9M8.4 4l4 4-4 4"
              fill="none"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pc {
  --pc-rx: 0deg;
  --pc-ry: 0deg;
  --pc-gx: 50%;
  --pc-gy: 50%;
  --pc-shift-x: 0px;
  --pc-shift-y: 0px;
  --pc-active: 0;
  position: relative;
  width: 320px;
  max-width: 100%;
  perspective: 1100px;
  touch-action: pan-y;
  -webkit-tap-highlight-color: transparent;
}

.pc__body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--line) 85%, transparent);
  border-radius: calc(var(--pc-radius) + 12px);
  background: linear-gradient(180deg, rgba(255, 250, 241, 0.92), rgba(250, 236, 214, 0.76));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 30px 60px -40px rgba(54, 54, 54, 0.6),
    0 12px 24px -20px rgba(184, 95, 0, 0.35);
  -webkit-backdrop-filter: blur(18px) saturate(1.5);
  backdrop-filter: blur(18px) saturate(1.5);
  transform: rotateX(var(--pc-rx)) rotateY(var(--pc-ry));
  transform-style: preserve-3d;
  transition: transform 240ms var(--ease-out);
  will-change: transform;
}

.pc[data-theme='dark'] .pc__body {
  border-color: rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(40, 35, 29, 0.94), rgba(54, 54, 54, 0.92));
  box-shadow: 0 34px 60px -40px rgba(0, 0, 0, 0.9);
}

.pc__tile {
  position: relative;
  aspect-ratio: 4 / 5;
  border-radius: var(--pc-radius);
  overflow: hidden;
  isolation: isolate;
  background:
    radial-gradient(120% 80% at 20% 0%, #ffe8cc 0%, transparent 55%),
    radial-gradient(90% 70% at 100% 100%, #f8dcb9 0%, transparent 60%),
    linear-gradient(160deg, #fff5e6 0%, #f4e2c9 100%);
}

.pc__portrait {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  transform: translate3d(var(--pc-shift-x), var(--pc-shift-y), 0);
  transition: transform 200ms var(--ease-out);
}

.pc__photo {
  position: absolute;
  inset: calc(var(--pc-parallax) * -1);
  width: calc(100% + var(--pc-parallax) * 2);
  height: calc(100% + var(--pc-parallax) * 2);
  object-fit: cover;
  object-position: center;
  pointer-events: none;
  user-select: none;
}

.pc__art {
  position: relative;
  display: grid;
  place-items: center;
  width: 74%;
  aspect-ratio: 1;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.9), transparent 46%),
    linear-gradient(150deg, #ffa64d 0%, #ff8a00 46%, #a85a00 100%);
  box-shadow:
    inset 0 2px 0 rgba(255, 255, 255, 0.35),
    0 30px 50px -30px rgba(184, 95, 0, 0.85);
}

.pc__art-ring {
  position: absolute;
  inset: -12%;
  border: 1px solid rgba(54, 54, 54, 0.12);
  border-radius: 50%;
}

.pc__art-ring--late {
  inset: -24%;
  border-color: rgba(54, 54, 54, 0.08);
}

.pc__art-initial {
  position: relative;
  font-family: var(--font-serif);
  font-size: clamp(64px, 8vw, 92px);
  font-style: italic;
  line-height: 1;
  color: #2b1b08;
  text-shadow: 0 4px 18px rgba(255, 255, 255, 0.24);
}

.pc__foil {
  position: absolute;
  inset: 0;
  z-index: 2;
  border-radius: inherit;
  background: conic-gradient(
    from 140deg at var(--pc-gx) var(--pc-gy),
    rgba(255, 205, 130, 0.75),
    rgba(255, 138, 0, 0.55),
    rgba(255, 243, 220, 0.2),
    rgba(255, 180, 94, 0.7),
    rgba(255, 205, 130, 0.75)
  );
  mix-blend-mode: soft-light;
  opacity: calc(var(--pc-holo) * (0.18 + 0.5 * var(--pc-active)));
  pointer-events: none;
}

.pc__glare {
  position: absolute;
  inset: 0;
  z-index: 3;
  border-radius: inherit;
  background: radial-gradient(
    280px circle at var(--pc-gx) var(--pc-gy),
    rgba(255, 255, 255, 0.85) 0%,
    rgba(255, 255, 255, 0.28) 28%,
    transparent 62%
  );
  mix-blend-mode: overlay;
  opacity: calc(var(--pc-glare) * var(--pc-active));
  pointer-events: none;
}

.pc__sheen {
  position: absolute;
  inset: 0;
  z-index: 3;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 30%, rgba(255, 255, 255, 0.55) 46%, transparent 58%);
  transform: translateX(calc((var(--pc-gx) - 50%) * 0.6));
  opacity: calc(var(--pc-active) * 0.35);
  pointer-events: none;
}

.pc__scrim {
  position: absolute;
  inset: 0;
  z-index: 4;
  border-radius: inherit;
  background: linear-gradient(
    to top,
    rgba(54, 34, 10, 0.66) 0%,
    rgba(54, 34, 10, 0.44) 22%,
    rgba(54, 34, 10, 0.13) 46%,
    transparent 62%
  );
  pointer-events: none;
}

.pc__rim {
  position: absolute;
  inset: 0;
  z-index: 5;
  border-radius: inherit;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  pointer-events: none;
}

.pc__info {
  position: absolute;
  right: 20px;
  bottom: 20px;
  left: 20px;
  z-index: 6;
  color: #fff6e8;
}

.pc__name {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 500;
  line-height: 1.2;
  letter-spacing: 0.01em;
}

.pc__title {
  margin: 6px 0 0;
  color: rgba(255, 250, 244, 0.78);
  font-size: 13px;
  line-height: 1.5;
}

.pc__footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 3px 8px 6px;
}

.pc__meta {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.pc__handle {
  overflow: hidden;
  color: var(--ink);
  font-size: 13.5px;
  font-weight: 650;
  line-height: 1.3;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.pc[data-theme='dark'] .pc__handle {
  color: #fff6e8;
}

.pc__status {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.pc__status::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pc-status);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pc-status) 18%, transparent);
}

.pc__contact {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(251, 246, 238, 0.6));
  color: var(--ink);
  font-family: inherit;
  font-size: 12.5px;
  font-weight: 650;
  cursor: pointer;
  transition:
    transform 380ms var(--ease-out),
    background-color 300ms var(--ease-out),
    border-color 300ms var(--ease-out);
}

.pc__contact:hover {
  border-color: var(--ink);
  transform: translateY(-1px);
}

.pc__contact:active {
  transform: scale(0.96);
}

@media (max-width: 460px) {
  .pc__footer {
    gap: 8px;
  }

  .pc__contact {
    padding: 0 11px;
    font-size: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .pc__body,
  .pc__portrait,
  .pc__contact {
    transition: none;
  }
}

/* ---------------------------------------------------------------- 包豪斯 */
.pc__body {
  padding: 8px;
  border: 2px solid var(--ink);
  border-radius: 10px;
  background: var(--paper-raised);
  box-shadow: 8px 8px 0 var(--ink);
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
}

.pc[data-theme='dark'] .pc__body {
  border-color: var(--paper);
  background: var(--ink);
  box-shadow: 8px 8px 0 rgba(0, 0, 0, 0.55);
}

.pc__tile {
  border: 1.5px solid var(--ink);
  border-radius: 4px;
  background: var(--paper-deep);
}

.pc[data-theme='dark'] .pc__tile {
  border-color: rgba(255, 246, 232, 0.22);
}

.pc__art {
  width: 72%;
  border: 2px solid var(--ink);
  background: var(--coral);
  box-shadow: none;
}

.pc[data-theme='dark'] .pc__art {
  border-color: var(--paper);
}

.pc__art-ring {
  inset: -9%;
  border: 1.5px dashed rgba(54, 54, 54, 0.45);
}

.pc__art-ring--late {
  inset: -22%;
  border-style: solid;
  border-color: rgba(54, 54, 54, 0.18);
}

.pc__art-initial {
  color: #2b1b08;
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 700;
}

.pc__glare,
.pc__holo,
.pc__sheen {
  display: none;
}

.pc__scrim {
  background: none;
}

.pc[data-theme='dark'] .pc__scrim {
  background: none;
}

.pc__info {
  left: 0;
  right: 0;
  bottom: 0;
  padding: 12px 16px 14px;
  border-top: 1.5px solid var(--ink);
  background: var(--paper-raised);
}

.pc[data-theme='dark'] .pc__info {
  border-top-color: rgba(255, 246, 232, 0.26);
  background: #211d18;
}

.pc__name {
  color: var(--ink);
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 700;
}

.pc[data-theme='dark'] .pc__name {
  color: var(--paper);
}

.pc__title {
  color: var(--muted);
}

.pc[data-theme='dark'] .pc__title {
  color: rgba(255, 246, 232, 0.66);
}

.pc__footer {
  margin-top: 2px;
  border-top: 1.5px solid var(--ink);
  padding: 8px 6px 4px;
}

.pc[data-theme='dark'] .pc__footer {
  border-top-color: rgba(255, 246, 232, 0.24);
}

.pc__contact {
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  background: var(--paper-raised);
  box-shadow: 3px 3px 0 var(--ink);
  transition:
    transform 160ms var(--ease-out),
    box-shadow 160ms var(--ease-out);
}

.pc__contact:hover {
  transform: translate(-1px, -1px);
  box-shadow: 4px 4px 0 var(--ink);
}

.pc__contact:active {
  transform: translate(1px, 1px);
  box-shadow: none;
}

.pc[data-theme='dark'] .pc__contact {
  border-color: var(--paper);
  background: var(--paper);
  color: var(--ink);
  box-shadow: 3px 3px 0 rgba(255, 246, 232, 0.4);
}

.pc__handle {
  color: var(--ink);
}

.pc[data-theme='dark'] .pc__handle {
  color: var(--paper);
}

/* Spotlight — low-brightness pointer light (SparkLight) */
.pc__spot,
.pc__spot-edge {
  position: absolute;
  inset: 0;
  z-index: 6;
  border-radius: inherit;
  pointer-events: none;
  opacity: calc(var(--pc-spot, 0) * 0.55);
  transition: opacity 240ms var(--ease-out);
}

.pc__spot {
  background: radial-gradient(
    circle var(--pc-spot-size, 220px) at var(--pc-sx, 50%) var(--pc-sy, 50%),
    rgba(255, 168, 64, 0.5) 0%,
    rgba(255, 138, 0, 0.16) 46%,
    transparent 74%
  );
  mix-blend-mode: multiply;
}

.pc__spot-edge {
  padding: 1.5px;
  background: radial-gradient(
    circle var(--pc-spot-size, 220px) at var(--pc-sx, 50%) var(--pc-sy, 50%),
    rgba(255, 246, 232, 0.9),
    transparent 70%
  );
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask:
    linear-gradient(#000 0 0) content-box exclude,
    linear-gradient(#000 0 0);
  opacity: calc(var(--pc-spot, 0) * 0.4);
}

.pc[data-theme='dark'] .pc__spot {
  background: radial-gradient(
    circle var(--pc-spot-size, 220px) at var(--pc-sx, 50%) var(--pc-sy, 50%),
    rgba(255, 170, 70, 0.55) 0%,
    rgba(255, 138, 0, 0.16) 46%,
    transparent 74%
  );
  mix-blend-mode: screen;
}

@media (prefers-reduced-motion: reduce) {
  .pc__spot,
  .pc__spot-edge {
    display: none;
  }
}
</style>
