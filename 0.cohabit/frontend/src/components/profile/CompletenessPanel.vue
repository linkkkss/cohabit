<script setup lang="ts">
import type { CompletenessReport } from '@/components/profile/completeness'

/**
 * 完成度分块展示（docs/03 §2.6）：基础 20 / 硬指标 20 / 软指标 30 / 红线 10 / 标签 10 / 自述 10。
 * 总分直接取接口的 `completeness`，分块分数是同一套规则的镜像，用来解释「还差在哪」。
 */
withDefaults(
  defineProps<{
    report: CompletenessReport
    showHints?: boolean
  }>(),
  {
    showHints: true,
  },
)

function percent(score: number, max: number): number {
  return max > 0 ? Math.round((score / max) * 100) : 0
}
</script>

<template>
  <div class="completeness">
    <div class="completeness-head">
      <p class="eyebrow">画像完成度</p>
      <p class="completeness-total">{{ report.total }}<span class="completeness-unit">%</span></p>
      <p v-if="report.remaining > 0" class="completeness-note">
        画像还差 {{ report.remaining }}% 才能开始匹配；已保存的内容不会丢。
      </p>
      <p v-else class="completeness-note">画像已完成，可以开始匹配。</p>
    </div>

    <ul class="completeness-list">
      <li v-for="section in report.sections" :key="section.key" class="completeness-row">
        <div class="meter">
          <span>{{ section.label }}</span>
          <strong>{{ section.score }} / {{ section.max }}</strong>
        </div>
        <div class="completeness-track">
          <span :style="{ width: `${percent(section.score, section.max)}%` }"></span>
        </div>
        <p v-if="showHints && section.hint" class="fine completeness-hint">{{ section.hint }}</p>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.completeness {
  display: grid;
  gap: 18px;
}

.completeness-head {
  display: grid;
  gap: 6px;
}

.completeness-total {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 42px;
  font-weight: 500;
  line-height: 1;
}

.completeness-unit {
  margin-left: 2px;
  color: var(--muted);
  font-size: 18px;
}

.completeness-note {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.completeness-list {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.completeness-row {
  display: grid;
  gap: 6px;
}

.completeness-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--sand);
}

.completeness-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--coral);
  transition: width 0.2s ease;
}

.completeness-hint {
  margin: 0;
}

@media (max-width: 640px) {
  .completeness-total {
    font-size: 34px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .completeness-track span {
    transition: none;
  }
}
</style>
