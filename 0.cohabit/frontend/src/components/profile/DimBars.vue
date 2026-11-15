<script setup lang="ts">
import { DIM_KEYS, DIM_LABELS, type Dims } from '@/api/profiles'

/**
 * 六维条形图（docs/05 §4.2 `.dims`/`.dim-row`）。
 * 数值来自 `GET /api/me/profile` 的 `dims`，未答的维度后端给 0，这里照实显示。
 */
defineProps<{ dims: Dims }>()
</script>

<template>
  <div class="dims">
    <div v-for="key in DIM_KEYS" :key="key" class="dim-row">
      <span class="dim-label">{{ DIM_LABELS[key] }}</span>
      <span class="dim-track" aria-hidden="true">
        <span class="dim-fill" :style="{ width: `${dims[key]}%` }"></span>
      </span>
      <span class="dim-value">{{ dims[key] }}</span>
    </div>
  </div>
</template>

<style scoped>
.dims {
  display: grid;
  gap: 10px;
}

.dim-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 34px;
  align-items: center;
  gap: 10px;
}

.dim-label {
  color: var(--muted);
  font-size: 13px;
}

.dim-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--sand);
}

.dim-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--coral);
}

.dim-value {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
</style>
