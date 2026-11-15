<script setup lang="ts">
import { computed } from 'vue'

/**
 * 头像（docs/05 §5）：M1 没有照片上传，统一用昵称首字回退。
 * 尺寸档位：sm 32 / md 44 / lg 64 / xl 96。
 */
const props = withDefaults(
  defineProps<{
    name: string
    size?: 'sm' | 'md' | 'lg' | 'xl'
  }>(),
  {
    size: 'md',
  },
)

const initial = computed(() => (props.name.trim().slice(0, 1) || '?').toUpperCase())
</script>

<template>
  <span class="avatar-badge" :class="`avatar-badge-${size}`" aria-hidden="true">{{ initial }}</span>
</template>

<style scoped>
.avatar-badge {
  display: inline-grid;
  flex: none;
  place-items: center;
  border-radius: 999px;
  background: var(--sand-deep);
  color: var(--ink);
  font-family: var(--font-serif);
  font-weight: 600;
  line-height: 1;
}

.avatar-badge-sm {
  width: 32px;
  height: 32px;
  font-size: 14px;
}

.avatar-badge-md {
  width: 44px;
  height: 44px;
  font-size: 18px;
}

.avatar-badge-lg {
  width: 64px;
  height: 64px;
  font-size: 26px;
}

.avatar-badge-xl {
  width: 96px;
  height: 96px;
  font-size: 38px;
}
</style>
