<script setup lang="ts">
/**
 * FoldText — React Bits <FoldText /> 的轻量 Vue 版（无 GSAP）。
 * 逐字沿铰链边翻折展开；支持 mount / scroll 触发，尊重 reduced-motion。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    text: string
    splitBy?: 'char' | 'word'
    hinge?: 'top' | 'bottom' | 'left' | 'right'
    trigger?: 'mount' | 'scroll'
    foldAngle?: number
    duration?: number
    stagger?: number
    perspective?: number
    as?: 'span' | 'h1' | 'h2' | 'p'
  }>(),
  {
    splitBy: 'char',
    hinge: 'top',
    trigger: 'mount',
    foldAngle: 92,
    duration: 0.68,
    stagger: 0.035,
    perspective: 800,
    as: 'span',
  },
)

const rootRef = ref<HTMLElement | null>(null)
const shown = ref(false)
let observer: IntersectionObserver | null = null
let timer = 0

const units = computed(() => {
  const text = props.text
  const parts = props.splitBy === 'word' ? text.split(/(\s+)/) : Array.from(text)
  return props.splitBy === 'word'
    ? parts.filter((part) => part !== '').map((part) => ({ char: part, space: /^\s+$/.test(part) }))
    : parts.map((char) => ({ char, space: /\s/.test(char) }))
})

const style = computed(() => ({
  '--ft-persp': `${Math.max(160, props.perspective)}px`,
  '--ft-angle': `${Math.max(0, Math.min(180, props.foldAngle))}deg`,
  '--ft-dur': `${Math.max(0.08, props.duration)}s`,
  '--ft-stag': `${Math.max(0, props.stagger)}s`,
}))

onMounted(() => {
  const el = rootRef.value
  if (!el) return
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  if (reduce) {
    shown.value = true
    return
  }
  if (props.trigger === 'mount') {
    timer = window.setTimeout(() => {
      shown.value = true
    }, 90)
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        shown.value = true
        observer?.disconnect()
        observer = null
      }
    },
    { threshold: 0.35 },
  )
  observer.observe(el)
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
  observer?.disconnect()
  observer = null
})
</script>

<template>
  <component :is="as" ref="rootRef" class="ft" :data-hinge="hinge" :class="{ 'is-in': shown }" :style="style">
    <span class="sr-only">{{ text }}</span>
    <span class="ft__line" aria-hidden="true">
      <span
        v-for="(unit, index) in units"
        :key="`${unit.char}-${index}`"
        class="ft__seg"
        :style="{ '--ft-i': index }"
      >
        <span v-if="unit.space" class="ft__space">{{ unit.char }}</span>
        <span v-else class="ft__piece">{{ unit.char }}</span>
      </span>
    </span>
  </component>
</template>

<style scoped>
.ft {
  display: inline-block;
  perspective: var(--ft-persp, 800px);
}

.ft__line {
  display: inline-block;
}

.ft__seg {
  display: inline-block;
  transform-style: preserve-3d;
}

.ft__piece {
  display: inline-block;
  transform-origin: 50% 0%;
  transform: rotateX(var(--ft-angle, 92deg)) translateZ(0.01px);
  opacity: 0;
  transition:
    transform var(--ft-dur, 0.68s) cubic-bezier(0.22, 1, 0.36, 1),
    opacity calc(var(--ft-dur, 0.68s) * 0.7) var(--ease-out);
  transition-delay: calc(var(--ft-i, 0) * var(--ft-stag, 0.035s));
  will-change: transform, opacity;
}

.ft[data-hinge='bottom'] .ft__piece {
  transform-origin: 50% 100%;
}

.ft[data-hinge='left'] .ft__piece {
  transform-origin: 0% 50%;
  transform: rotateY(calc(var(--ft-angle, 92deg) * -1));
}

.ft[data-hinge='right'] .ft__piece {
  transform-origin: 100% 50%;
  transform: rotateY(var(--ft-angle, 92deg));
}

.ft.is-in .ft__piece {
  transform: rotateX(0deg) rotateY(0deg);
  opacity: 1;
}

.ft__space {
  white-space: pre;
}

@media (prefers-reduced-motion: reduce) {
  .ft__piece {
    transform: none;
    opacity: 1;
    transition: none;
  }
}
</style>
