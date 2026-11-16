<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { apiErrorCode, apiErrorMessage } from '@/api/client'
import { fetchProfile } from '@/api/profiles'
import { fetchMatches, type MatchScore } from '@/api/matching'
import MatchCard from '@/components/match/MatchCard.vue'
import MatchDetailDialog from '@/views/match/MatchDetailDialog.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'

/**
 * 匹配页（docs/05 §7.2 /match）：
 * - 固定筛选（本学院 / 同性别 / 画像 100%）只展示、不提供关闭；
 * - 可选筛选：专业（精确）+ 最低契合度；
 * - 卡片顺序由后端给定（分数 → 完整度 → 更新时间 → uid），前端不重排；
 * - 有红线冲突的候选照样展示（docs/03 §5.4），只用琥珀角标提示。
 */

const PAGE_SIZE = 20

const route = useRoute()

const status = ref<'loading' | 'ready' | 'error'>('loading')
const errorMessage = ref('')
const incomplete = ref(false)
const matches = ref<MatchScore[]>([])
const total = ref(0)
const nextPage = ref<number | null>(null)
const loadingMore = ref(false)
const loadMoreError = ref('')
const securityNotice = ref('')
const myTags = ref<string[]>([])

const filters = reactive({ major: '', minScore: 0 })
const applied = reactive({ major: '', minScore: 0 })

const selected = ref<MatchScore | null>(null)
const dialogOpen = ref(false)

const emptyTitle = computed(() =>
  incomplete.value ? '先完成画像' : '还没有候选',
)

const emptyMessage = computed(() =>
  incomplete.value
    ? '先完成画像，才能看到可能合拍的人。'
    : '还没有候选。同学院、同性别的同学完成画像后会出现在这里。',
)

function sharedTagsFor(match: MatchScore): string[] {
  const mine = myTags.value
  return match.target.tags.filter((tag) => mine.includes(tag)).slice(0, 3)
}

async function loadMyTags(): Promise<void> {
  try {
    const profile = await fetchProfile()
    myTags.value = profile.tags
  } catch {
    // 标签高亮只是锦上添花，取不到就不标。
  }
}

async function load(reset = true): Promise<void> {
  loadMoreError.value = ''
  if (reset) {
    status.value = 'loading'
    incomplete.value = false
    matches.value = []
    total.value = 0
    nextPage.value = null
  } else {
    loadingMore.value = true
  }

  const page = reset ? 1 : (nextPage.value ?? 1)
  try {
    const payload = await fetchMatches({
      page,
      pageSize: PAGE_SIZE,
      major: applied.major || undefined,
      minScore: applied.minScore > 0 ? applied.minScore : undefined,
    })
    total.value = payload.count
    matches.value = reset ? payload.results : [...matches.value, ...payload.results]
    nextPage.value = payload.next ? page + 1 : null
    status.value = 'ready'
  } catch (error) {
    if (apiErrorCode(error) === 'PROFILE_INCOMPLETE') {
      incomplete.value = true
      matches.value = []
      status.value = 'ready'
    } else if (reset) {
      status.value = 'error'
      errorMessage.value = apiErrorMessage(error, '匹配加载失败，请稍后重试。')
    } else {
      loadMoreError.value = apiErrorMessage(error, '加载更多失败，请稍后重试。')
    }
  } finally {
    loadingMore.value = false
  }
}

function applyFilters(): void {
  applied.major = filters.major
  applied.minScore = filters.minScore
  void load(true)
}

function resetFilters(): void {
  filters.major = ''
  filters.minScore = 0
  applyFilters()
}

function openDetail(match: MatchScore): void {
  selected.value = match
  dialogOpen.value = true
}

function reload(): void {
  void load(true)
}

/** 在匹配详情里拉黑后：刷新候选并给出列表页提示（详情弹层已关闭）。 */
function onBlocked(): void {
  securityNotice.value = '已拉黑。进行中的请求已关闭，对方不会再出现在你的候选里。'
  reload()
}

onMounted(() => {
  void loadMyTags()
  void load(true)
})

// 从画像页返回时可能带 ?major=，方便直接筛专业。
const initialMajor = route.query.major
if (typeof initialMajor === 'string' && initialMajor.trim()) {
  filters.major = initialMajor.trim()
  applied.major = initialMajor.trim()
}
</script>

<template>
  <section class="container match-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">匹配</p>
        <h1>可能合拍的人</h1>
        <p class="lede">
          按契合度从高到低排序；有红线冲突的候选分数会按规则封顶，但仍会展示，邀请前请再确认。
        </p>
      </div>
      <p v-if="status === 'ready' && !incomplete" class="fine match-count">共 {{ total }} 位候选</p>
    </header>

    <div class="match-filters">
      <div class="filter-fixed">
        <span class="chip">本学院</span>
        <span class="chip">同性别</span>
        <span class="chip">画像 100%</span>
        <span class="fine">固定筛选，不可关闭</span>
      </div>
      <form class="filter-row" @submit.prevent="applyFilters">
        <label class="field filter-field">
          <span>专业（精确）</span>
          <input v-model.trim="filters.major" type="text" placeholder="如：计算机科学与技术" />
        </label>
        <label class="field filter-field">
          <span>最低契合度</span>
          <select v-model.number="filters.minScore">
            <option :value="0">不限</option>
            <option :value="60">60 以上</option>
            <option :value="70">70 以上</option>
            <option :value="80">80 以上</option>
            <option :value="90">90 以上</option>
          </select>
        </label>
        <div class="filter-actions">
          <button class="btn btn-small btn-primary" type="submit">应用筛选</button>
          <button class="btn btn-small btn-ghost" type="button" @click="resetFilters">重置</button>
        </div>
      </form>
    </div>

    <NoticeBar v-if="securityNotice" tone="info">{{ securityNotice }}</NoticeBar>
    <NoticeBar v-if="loadMoreError" tone="error">{{ loadMoreError }}</NoticeBar>

    <StateBlock v-if="status === 'loading'" status="loading" :rows="3" />
    <StateBlock
      v-else-if="status === 'error'"
      status="error"
      :message="errorMessage"
      @retry="reload"
    />
    <StateBlock
      v-else-if="!matches.length"
      status="empty"
      :title="emptyTitle"
      :message="emptyMessage"
    >
      <RouterLink v-if="incomplete" class="btn btn-primary" :to="{ name: 'onboarding' }">
        去完善画像
      </RouterLink>
      <p v-else class="fine">
        也可以先去
        <RouterLink :to="{ name: 'profile' }">完善画像</RouterLink>
        或
        <RouterLink :to="{ name: 'plaza' }">看看寝室广场</RouterLink>。
      </p>
    </StateBlock>

    <div v-else class="candidate-grid">
      <MatchCard
        v-for="match in matches"
        :key="match.target.uid"
        :match="match"
        :shared-tags="sharedTagsFor(match)"
        @open="openDetail"
      />
    </div>

    <div v-if="status === 'ready' && !incomplete && nextPage" class="match-more">
      <button
        class="btn btn-ghost"
        type="button"
        :disabled="loadingMore"
        @click="load(false)"
      >
        {{ loadingMore ? '加载中…' : '加载更多' }}
      </button>
    </div>

    <MatchDetailDialog
      :match="selected"
      :open="dialogOpen"
      @update:open="dialogOpen = $event"
      @blocked="onBlocked"
    />
  </section>
</template>

<style scoped>
.match-page {
  padding-bottom: 48px;
}

.match-count {
  margin: 0;
}

.match-filters {
  display: grid;
  gap: 12px;
  margin-bottom: 20px;
}

.filter-fixed {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.filter-field {
  max-width: 240px;
}

.filter-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
}

.match-more {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

@media (max-width: 640px) {
  .filter-field {
    max-width: none;
  }

  .filter-actions {
    width: 100%;
  }

  .filter-actions .btn {
    flex: 1;
  }
}
</style>
