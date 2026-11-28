<script setup lang="ts">
/**
 * ScrollFloat — React Bits <ScrollFloat /> 的 Vue 实现（不依赖 GSAP）。
 * 文字进入视口时按字符错峰浮入；缓动统一走 ease-out：快速进入、自然减速。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

type Effect = 'float' | 'blur' | 'flip' | 'wave'
type Order = 'start' | 'end' | 'center' | 'edges' | 'random'
type Direction = 'up' | 'down'

const props = withDefaults(
  defineProps<{
    text: string
    as?: string
    effect?: Effect
    splitBy?: 'chars' | 'words'
    direction?: Direction
    order?: Order
    stagger?: number
    distance?: number
    stretch?: number
    immediate?: boolean
  }>(),
  {
    as: 'h2',
    effect: 'float',
    splitBy: 'words',
    direction: 'up',
    order: 'start',
    stagger: 0.035,
    distance: 0.8,
    stretch: 1,
    immediate: false,
  },
)

const rootRef = ref<HTMLElement | null>(null)
const shown = ref(false)
let observer: IntersectionObserver | null = null

const random = (index: number): number => {
  const value = Math.sin((index + 1) * 12.9898) * 43758.5453
  return value - Math.floor(value)
}

const groups = computed(() => {
  if (props.splitBy === 'words') {
    return props.text
      .split(/(\s+)/)
      .filter((part) => part !== '')
      .map((part) => ({ space: /^\s+$/.test(part), chars: [...part] }))
  }
  return [...props.text].map((char) => ({ space: char === ' ', chars: [char] }))
})

const delays = computed(() => {
  const total = groups.value.reduce((sum, group) => sum + group.chars.length, 0)
  const middle = (total - 1) / 2
  const ranks = Array.from({ length: total }, (_, index) => {
    if (props.order === 'end') return total - 1 - index
    if (props.order === 'center') return Math.abs(index - middle)
    if (props.order === 'edges') return middle - Math.abs(index - middle)
    return index
  })
  if (props.order === 'random') {
    const shuffled = ranks.map((_, index) => index).sort((a, b) => random(a) - random(b))
    shuffled.forEach((target, rank) => {
      ranks[target] = rank
    })
  }
  const first = Math.min(...ranks, 0)
  return ranks.map((rank) => (rank - first) * Math.max(0, props.stagger) * 1000)
})

const charDelays = computed(() => {
  let index = 0
  return groups.value.map((group) =>
    group.chars.map(() => {
      const delay = delays.value[index] ?? 0
      index += 1
      return delay
    }),
  )
})

onMounted(() => {
  if (props.immediate) {
    shown.value = true
    return
  }
  if (typeof IntersectionObserver === 'undefined' || !rootRef.value) {
    shown.value = true
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      shown.value = true
      observer?.disconnect()
      observer = null
    },
    { threshold: 0.12, rootMargin: '0px 0px -6% 0px' },
  )
  observer.observe(rootRef.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})
</script>

<template>
  <component
    :is="as"
    ref="rootRef"
    class="scroll-float"
    :class="[`scroll-float--${effect}`, `scroll-float--${direction}`, { 'is-in': shown }]"
    :style="{ '--sf-distance': String(distance), '--sf-stretch': String(stretch) }"
    :aria-label="text"
  >
    <span class="sr-only">{{ text }}</span>
    <span class="scroll-float__line" aria-hidden="true">
      <span v-for="(group, gi) in groups" :key="gi" class="scroll-float__group">
        <span
          v-for="(char, ci) in group.chars"
          :key="ci"
          class="scroll-float__char"
          :class="{ 'is-space': group.space }"
          :style="{ '--sf-delay': `${charDelays[gi]?.[ci] ?? 0}ms` }"
          >{{ char }}</span
        >
      </span>
    </span>
  </component>
</template>

<style scoped>
.scroll-float {
  margin: 0;
  padding-block: 0.08em;
}

.scroll-float__line {
  display: block;
}

.scroll-float__group {
  display: inline-block;
  white-space: pre-wrap;
}

.scroll-float__char {
  display: inline-block;
  opacity: 0;
  transform: translateY(calc(0.72em * var(--sf-distance)));
  transition:
    transform 1000ms var(--ease-out),
    opacity 520ms var(--ease-out),
    filter 900ms var(--ease-out);
  transition-delay: var(--sf-delay, 0ms);
  will-change: transform, opacity;
}

.scroll-float__char.is-space {
  width: 0.32em;
}

.scroll-float__gap {
  display: inline-block;
  width: 0.32em;
}

.scroll-float--down .scroll-float__char {
  transform: translateY(calc(-0.72em * var(--sf-distance)));
}

.scroll-float--blur .scroll-float__char {
  filter: blur(10px);
  transform: translateY(calc(0.3em * var(--sf-distance))) scale(1.12);
}

.scroll-float--flip .scroll-float__char {
  transform: perspective(600px) rotateX(calc(-78deg * var(--sf-distance)));
  transform-origin: 50% 60%;
}

.scroll-float--wave .scroll-float__char {
  transform: translateY(calc(0.5em * var(--sf-distance))) rotate(calc(-6deg * var(--sf-distance)));
}

.scroll-float.is-in .scroll-float__char {
  opacity: 1;
  transform: none;
  filter: none;
}

@media (prefers-reduced-motion: reduce) {
  .scroll-float__char {
    opacity: 1;
    transform: none;
    filter: none;
    transition: none;
  }
}
</style>
