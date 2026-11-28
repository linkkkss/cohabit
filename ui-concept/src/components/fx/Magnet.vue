<script setup lang="ts">
/**
 * Magnet — React Bits <Magnet /> 的 Vue 移植。
 * 外层 wrapper 保持占位，内层跟着指针做弹簧位移；多个磁吸元素默认只吸附最近的一个。
 * 物理参数与 React 版本一致：stiffness 170 / damping 16 / mass 1。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

type Axis = 'both' | 'x' | 'y'

const props = withDefaults(
  defineProps<{
    padding?: number
    magnetStrength?: number
    exclusive?: boolean
    axis?: Axis
    maxOffset?: number | null
    tilt?: number
    scale?: number
    spring?: { stiffness?: number; damping?: number; mass?: number }
    disabled?: boolean
    onActiveChange?: (active: boolean) => void
    wrapperClassName?: string
    innerClassName?: string
  }>(),
  {
    padding: 100,
    magnetStrength: 2,
    exclusive: true,
    axis: 'both',
    maxOffset: null,
    tilt: 0,
    scale: 1,
    spring: () => ({ stiffness: 170, damping: 16, mass: 1 }),
    disabled: false,
    onActiveChange: undefined,
    wrapperClassName: '',
    innerClassName: '',
  },
)

interface Settings {
  padding: number
  disabled: boolean
  strength: number
  maxOffset: number | null
  exclusive: boolean
  axis: Axis
  tilt: number
  scale: number
  stiffness: number
  damping: number
  mass: number
  reduce: boolean
  onActiveChange?: (active: boolean) => void
}

interface Entry {
  wrapper: HTMLElement
  settings: () => Settings
  wake: () => void
  active: boolean
}

const wrapperRef = ref<HTMLElement | null>(null)
const innerRef = ref<HTMLElement | null>(null)

const registry = new Set<Entry>()
const field: { pointer: { x: number; y: number } | null; owner: Entry | null } = {
  pointer: null,
  owner: null,
}
let detach: (() => void) | null = null

const smoothstep = (edge0: number, edge1: number, value: number): number => {
  const t = Math.min(1, Math.max(0, (value - edge0) / (edge1 - edge0)))
  return t * t * (3 - 2 * t)
}

const reach = (rect: DOMRect, pointer: { x: number; y: number }) => {
  const dx = pointer.x - (rect.left + rect.width / 2)
  const dy = pointer.y - (rect.top + rect.height / 2)
  const outside = Math.hypot(
    Math.max(0, Math.abs(dx) - rect.width / 2),
    Math.max(0, Math.abs(dy) - rect.height / 2),
  )
  return { dx, dy, outside }
}

const arbitrate = (): void => {
  let winner: Entry | null = null
  let nearest = Number.POSITIVE_INFINITY
  let closest = Number.POSITIVE_INFINITY
  for (const entry of registry) {
    const s = entry.settings()
    let near: { dx: number; dy: number; outside: number } | null = null
    if (field.pointer && !s.disabled && !s.reduce) {
      const candidate = reach(entry.wrapper.getBoundingClientRect(), field.pointer)
      if (candidate.outside <= s.padding) near = candidate
    }
    if (!s.exclusive) {
      if (near || entry.active) entry.wake()
      continue
    }
    if (!near) continue
    const center = Math.hypot(near.dx, near.dy)
    if (near.outside < nearest || (near.outside === nearest && center < closest)) {
      winner = entry
      nearest = near.outside
      closest = center
    }
  }
  const previous = field.owner
  field.owner = winner
  if (previous && previous !== winner) previous.wake()
  if (winner) winner.wake()
}

const attach = (): (() => void) => {
  const onPointerMove = (event: PointerEvent): void => {
    if (event.pointerType === 'touch') return
    field.pointer = { x: event.clientX, y: event.clientY }
    arbitrate()
  }
  const onLeave = (): void => {
    field.pointer = null
    arbitrate()
  }
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  window.addEventListener('scroll', arbitrate, { passive: true, capture: true })
  document.documentElement.addEventListener('pointerleave', onLeave)
  window.addEventListener('blur', onLeave)
  return () => {
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('scroll', arbitrate, { capture: true })
    document.documentElement.removeEventListener('pointerleave', onLeave)
    window.removeEventListener('blur', onLeave)
  }
}

let cleanup: (() => void) | null = null

onMounted(() => {
  const wrapper = wrapperRef.value
  const inner = innerRef.value
  if (!wrapper || !inner) return

  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const current = { x: 0, y: 0, tiltX: 0, tiltY: 0, scale: 1 }
  const velocity = { x: 0, y: 0, tiltX: 0, tiltY: 0, scale: 0 }
  let active = false
  let raf = 0
  let last = 0

  const settings = (): Settings => ({
    padding: Math.max(0, props.padding),
    disabled: props.disabled,
    strength: Math.max(0.1, props.magnetStrength),
    maxOffset: props.maxOffset ?? null,
    exclusive: props.exclusive,
    axis: props.axis,
    tilt: props.tilt,
    scale: props.scale,
    stiffness: Math.max(1, props.spring?.stiffness ?? 170),
    damping: Math.max(0, props.spring?.damping ?? 16),
    mass: Math.max(0.01, props.spring?.mass ?? 1),
    reduce,
    onActiveChange: props.onActiveChange,
  })

  const solve = (target: typeof current, dt: number): boolean => {
    const s = settings()
    let resting = true
    ;(Object.keys(current) as Array<keyof typeof current>).forEach((key) => {
      const force = s.stiffness * (target[key] - current[key]) - s.damping * velocity[key]
      velocity[key] += (force / s.mass) * dt
      current[key] += velocity[key] * dt
      const epsilon = key === 'scale' ? 0.001 : 0.05
      if (Math.abs(target[key] - current[key]) > epsilon || Math.abs(velocity[key]) > epsilon) {
        resting = false
      }
    })
    return resting
  }

  const measure = (): { target: typeof current; engaged: boolean } => {
    const s = settings()
    const target = { x: 0, y: 0, tiltX: 0, tiltY: 0, scale: 1 }
    if (s.disabled || s.reduce || !field.pointer) return { target, engaged: false }
    if (s.exclusive && field.owner !== entry) return { target, engaged: false }
    const rect = wrapper.getBoundingClientRect()
    const { dx, dy, outside } = reach(rect, field.pointer)
    if (outside > s.padding) return { target, engaged: false }
    const pull = s.padding > 0 ? 1 - smoothstep(s.padding * 0.5, s.padding, outside) : 1
    let x = s.axis === 'y' ? 0 : (dx / s.strength) * pull
    let y = s.axis === 'x' ? 0 : (dy / s.strength) * pull
    if (s.maxOffset !== null) {
      const length = Math.hypot(x, y)
      if (length > s.maxOffset) {
        x *= s.maxOffset / length
        y *= s.maxOffset / length
      }
    }
    const nx = Math.max(-1, Math.min(1, dx / Math.max(rect.width / 2, 1)))
    const ny = Math.max(-1, Math.min(1, dy / Math.max(rect.height / 2, 1)))
    target.x = x
    target.y = y
    target.tiltX = -ny * s.tilt * pull
    target.tiltY = nx * s.tilt * pull
    target.scale = 1 + (s.scale - 1) * pull
    return { target, engaged: true }
  }

  const apply = (): void => {
    const { x, y, tiltX, tiltY, scale } = current
    const turned = Math.abs(tiltX) > 0.01 || Math.abs(tiltY) > 0.01
    inner.style.transform =
      `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0)` +
      (turned
        ? ` perspective(800px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg)`
        : '') +
      (Math.abs(scale - 1) > 0.0005 ? ` scale(${scale.toFixed(4)})` : '')
  }

  const frame = (now: number): void => {
    raf = 0
    const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60
    last = now
    const { target, engaged } = measure()
    if (engaged !== active) {
      active = engaged
      entry.active = engaged
      if (engaged) wrapper.setAttribute('data-magnet-active', '')
      else wrapper.removeAttribute('data-magnet-active')
      settings().onActiveChange?.(engaged)
    }
    const steps = Math.ceil(dt / (1 / 120))
    let resting = true
    for (let i = 0; i < steps; i += 1) resting = solve(target, dt / steps)
    if (resting) {
      ;(Object.keys(current) as Array<keyof typeof current>).forEach((key) => {
        current[key] = target[key]
        velocity[key] = 0
      })
    }
    apply()
    if (!resting) raf = requestAnimationFrame(frame)
    else last = 0
  }

  function wake(): void {
    if (!raf) raf = requestAnimationFrame(frame)
  }

  const entry: Entry = { wrapper, settings, wake, active: false }
  registry.add(entry)
  if (!detach) detach = attach()

  cleanup = () => {
    cancelAnimationFrame(raf)
    registry.delete(entry)
    if (field.owner === entry) field.owner = null
    if (!registry.size && detach) {
      detach()
      detach = null
    }
  }
})

onBeforeUnmount(() => {
  cleanup?.()
  cleanup = null
})
</script>

<template>
  <div ref="wrapperRef" :class="wrapperClassName" class="magnet">
    <div ref="innerRef" :class="innerClassName" class="magnet__inner">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.magnet {
  position: relative;
  display: inline-block;
}

.magnet__inner {
  will-change: transform;
}
</style>
