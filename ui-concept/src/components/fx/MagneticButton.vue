<script setup lang="ts">
/**
 * MagneticButton — 磁吸按钮：在 Magnet 的弹簧位移外再套一层按钮语义。
 * 主 CTA 用 primary，次级用 ghost；玻璃高光由全局 .btn 提供。
 */
import Magnet from './Magnet.vue'

withDefaults(
  defineProps<{
    to?: string
    href?: string
    type?: 'button' | 'submit'
    variant?: 'primary' | 'ghost' | 'dark'
    size?: 'md' | 'small'
    block?: boolean
    padding?: number
    strength?: number
    maxOffset?: number
    disabled?: boolean
  }>(),
  {
    to: '',
    href: '',
    type: 'button',
    variant: 'primary',
    size: 'md',
    block: false,
    padding: 90,
    strength: 2.6,
    maxOffset: 16,
    disabled: false,
  },
)
</script>

<template>
  <Magnet
    wrapper-class-name="magnetic-button"
    :class="{ 'is-block': block }"
    :padding="padding"
    :magnet-strength="strength"
    :max-offset="maxOffset"
    :scale="1.02"
    :disabled="disabled"
  >
    <RouterLink
      v-if="to"
      :to="to"
      class="btn"
      :class="[`btn-${variant}`, size === 'small' ? 'btn-small' : '', { 'is-block': block }]"
    >
      <slot />
    </RouterLink>
    <a
      v-else-if="href"
      :href="href"
      class="btn"
      :class="[`btn-${variant}`, size === 'small' ? 'btn-small' : '', { 'is-block': block }]"
    >
      <slot />
    </a>
    <button
      v-else
      :type="type"
      :disabled="disabled"
      class="btn"
      :class="[`btn-${variant}`, size === 'small' ? 'btn-small' : '', { 'is-block': block }]"
    >
      <slot />
    </button>
  </Magnet>
</template>

<style scoped>
.magnetic-button {
  display: inline-flex;
  vertical-align: middle;
}

.magnetic-button.is-block {
  display: flex;
  width: 100%;
}

.btn.is-block {
  width: 100%;
}
</style>
