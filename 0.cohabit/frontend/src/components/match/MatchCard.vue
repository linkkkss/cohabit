<script setup lang="ts">
import { computed } from 'vue'
import type { MatchScore } from '@/api/matching'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import TagChips from '@/components/common/TagChips.vue'

/**
 * 匹配卡片（docs/05 §7.2 /match）：分数 → 昵称+meta → 首条自述/标签 → 操作。
 * 有红线冲突的候选照样展示，只加一个琥珀色角标（docs/03 §5.4）。
 */
const props = defineProps<{
  match: MatchScore
  sharedTags?: string[]
}>()

const emit = defineEmits<{
  (event: 'open', match: MatchScore): void
}>()

const meta = computed(() => {
  const target = props.match.target
  const gender = target.gender === 'MALE' ? '男' : '女'
  const parts = [gender, target.grade ? `${target.grade} 年级` : '', target.college, target.major]
  return parts.filter((part) => Boolean(part)).join(' · ')
})
</script>

<template>
  <article class="candidate-card match-card">
    <div class="match-top">
      <AvatarBadge :name="match.target.nickname" />
      <div class="match-id">
        <p class="candidate-name">{{ match.target.nickname }}</p>
        <p class="candidate-meta">{{ meta }}</p>
      </div>
      <div class="match-score">
        <span class="score">{{ match.score }}</span>
        <span class="fine">契合度</span>
      </div>
    </div>

    <p v-if="match.target.headline" class="headline">{{ match.target.headline }}</p>

    <TagChips
      :tags="match.target.tags"
      :max="4"
      :shared="sharedTags"
      empty-text="对方还没有选标签。"
    />

    <div class="match-foot">
      <span v-if="match.conflicts.length" class="badge-warn">
        <span class="badge-dot" aria-hidden="true"></span>有 {{ match.conflicts.length }} 项红线冲突
      </span>
      <span v-if="match.version_warning" class="badge-warn">
        <span class="badge-dot" aria-hidden="true"></span>问卷版本不同
      </span>
      <button type="button" class="btn btn-small btn-ghost match-open" @click="emit('open', match)">
        查看详情
      </button>
    </div>
  </article>
</template>

<style scoped>
.match-card {
  gap: 12px;
}

.match-top {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.match-id {
  display: grid;
  flex: 1;
  gap: 2px;
  min-width: 0;
}

.match-score {
  display: grid;
  justify-items: end;
  gap: 2px;
}

.match-score .score {
  line-height: 1;
}

.headline {
  margin: 0;
  display: -webkit-box;
  overflow: hidden;
  font-family: var(--font-serif);
  font-size: 19px;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.match-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: auto;
}

.badge-warn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid color-mix(in srgb, var(--coral) 45%, var(--line));
  border-radius: 999px;
  padding: 3px 10px;
  background: color-mix(in srgb, var(--coral) 8%, var(--paper));
  color: var(--coral-dark);
  font-size: 11px;
  line-height: 1.6;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--coral-dark);
}

.match-open {
  margin-left: auto;
}
</style>
