<script setup lang="ts">
import { DIM_KEYS, DIM_LABELS } from '@/api/profiles'
import type { MatchDims } from '@/api/matching'

/**
 * 六维对比（docs/05 §4.3 `.dims`/`.dim-row`）：每行两条 6px 细条 = 我 / 对方，
 * 右侧是 `dim_score = 100 - |a - b|`。数值全部来自接口，不在前端重算。
 */
defineProps<{ dims: MatchDims }>()
</script>

<template>
  <div class="dim-compare">
    <div v-for="key in DIM_KEYS" :key="key" class="dim-compare-row">
      <span class="dim-compare-label">{{ DIM_LABELS[key] }}</span>
      <span class="dim-compare-bars">
        <span class="dim-compare-track" :aria-label="`我的${DIM_LABELS[key]} ${dims.a[key]}`">
          <span class="dim-compare-fill dim-compare-mine" :style="{ width: `${dims.a[key]}%` }"></span>
        </span>
        <span class="dim-compare-track" :aria-label="`对方${DIM_LABELS[key]} ${dims.b[key]}`">
          <span class="dim-compare-fill dim-compare-theirs" :style="{ width: `${dims.b[key]}%` }"></span>
        </span>
      </span>
      <span class="dim-compare-value">{{ dims.dim_score[key] }}</span>
    </div>
    <p class="dim-compare-legend fine">
      上条是你，下条是对方；右侧是这一维的接近度（100 − 差值）。
    </p>
  </div>
</template>

<style scoped>
.dim-compare {
  display: grid;
  gap: 10px;
}

.dim-compare-row {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 34px;
  align-items: center;
  gap: 10px;
}

.dim-compare-label {
  color: var(--muted);
  font-size: 13px;
}

.dim-compare-bars {
  display: grid;
  gap: 3px;
}

.dim-compare-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--sand);
}

.dim-compare-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.dim-compare-mine {
  background: var(--coral);
}

.dim-compare-theirs {
  background: var(--ink);
}

.dim-compare-value {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.dim-compare-legend {
  margin: 2px 0 0;
}
</style>
