<script setup lang="ts">
/**
 * ShinyText — React Bits <ShinyText /> 的 Vue 移植。
 * 一道光带扫过文字；支持 loop / view / hover 三种触发方式。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    text: string
    color?: string
    shineColor?: string
    speed?: number
    delay?: number
    angle?: number
    shineWidth?: number
    softness?: number
    glow?: number
    direction?: 'left' | 'right'
    trigger?: 'loop' | 'view' | 'hover'
    disabled?: boolean
  }>(),
  {
    color: 'currentColor',
    shineColor: '#fff4e8',
    speed: 3.2,
    delay: 0,
    angle: 100,
    shineWidth: 34,
    softness: 0.8,
    glow: 0.35,
    direction: 'left',
    trigger: 'loop',
    disabled: false,
  },
)

const rootRef = ref<HTMLElement | null>(null)
const seen = ref(false)
let observer: IntersectionObserver | null = null

const style = computed(() => ({
  '--shine-color': props.shineColor,
  '--shine-angle': `${props.angle}deg`,
  '--shine-half': `${Math.max(2, props.shineWidth) / 2}%`,
  '--shine-dur': `${Math.max(0.4, props.speed)}s`,
  '--shine-delay': `${Math.max(0, props.delay)}s`,
  '--shine-glow': String(Math.min(1, Math.max(0, props.glow))),
  '--shine-soft': String(Math.min(1, Math.max(0, props.softness))),
  color: props.color,
}))

onMounted(() => {
  if (props.trigger !== 'view' || !rootRef.value) return
  if (typeof IntersectionObserver === 'undefined') {
    seen.value = true
    return
  }
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        seen.value = true
        observer?.disconnect()
        observer = null
      }
    },
    { threshold: 0.4 },
  )
  observer.observe(rootRef.value)
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})
</script>

<template>
  <span
    ref="rootRef"
    class="shiny"
    :class="[
      `shiny--${trigger}`,
      { 'is-on': trigger === 'loop' || seen, 'is-right': direction === 'right', 'is-disabled': disabled },
    ]"
    :style="style"
  >
    <span class="shiny__base">{{ text }}</span>
    <span class="shiny__glow" aria-hidden="true">{{ text }}</span>
    <span class="shiny__glare" aria-hidden="true">{{ text }}</span>
  </span>
</template>

<style scoped>
.shiny {
  position: relative;
  display: inline-block;
  white-space: pre-wrap;
}

.shiny__base {
  position: relative;
  z-index: 1;
}

.shiny__glare,
.shiny__glow {
  position: absolute;
  inset: 0;
  display: block;
  background-image: linear-gradient(
    var(--shine-angle),
    transparent calc(50% - var(--shine-half)),
    var(--shine-color) 50%,
    transparent calc(50% + var(--shine-half))
  );
  background-size: 260% 100%;
  background-repeat: no-repeat;
  background-position: 190% 0;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  pointer-events: none;
  user-select: none;
}

.shiny__glow {
  z-index: 2;
  filter: blur(0.16em);
  opacity: var(--shine-glow);
}

.shiny__glare {
  z-index: 3;
}

.shiny.is-on .shiny__glare,
.shiny.is-on .shiny__glow {
  animation: shiny-sweep var(--shine-dur) var(--shine-delay) cubic-bezier(0.45, 0, 0.25, 1) infinite;
}

.shiny.is-right.is-on .shiny__glare,
.shiny.is-right.is-on .shiny__glow {
  animation-name: shiny-sweep-rev;
}

.shiny--hover .shiny__glare,
.shiny--hover .shiny__glow {
  animation: shiny-hover var(--shine-dur) var(--ease-out) 1 both;
  opacity: 0;
}

.shiny--hover:hover .shiny__glare,
.shiny--hover:hover .shiny__glow {
  opacity: var(--shine-glow);
  animation-play-state: running;
}

.shiny--hover:hover .shiny__glare {
  opacity: 1;
}

.shiny.is-disabled .shiny__glare,
.shiny.is-disabled .shiny__glow {
  display: none;
}

@keyframes shiny-sweep {
  0% {
    background-position: 190% 0;
  }
  55%,
  100% {
    background-position: -90% 0;
  }
}

@keyframes shiny-sweep-rev {
  0% {
    background-position: -90% 0;
  }
  55%,
  100% {
    background-position: 190% 0;
  }
}

@keyframes shiny-hover {
  0% {
    background-position: 190% 0;
  }
  100% {
    background-position: -90% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .shiny.is-on .shiny__glare,
  .shiny.is-on .shiny__glow,
  .shiny--hover .shiny__glare,
  .shiny--hover .shiny__glow {
    animation: none;
    opacity: 0;
  }
}
</style>
