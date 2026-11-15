<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import {
  DIM_LABELS,
  DIM_KEYS,
  fetchProfile,
  fetchQuestionnaire,
  type BasicProfile,
  type Profile,
  type Questionnaire,
} from '@/api/profiles'
import { useAuthStore } from '@/stores/auth'
import CompletenessPanel from '@/components/profile/CompletenessPanel.vue'
import ContactPanel from '@/components/profile/ContactPanel.vue'
import DimBars from '@/components/profile/DimBars.vue'
import TagChips from '@/components/common/TagChips.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import { buildCompletenessReport } from '@/components/profile/completeness'
import { RouterLink } from 'vue-router'

/**
 * 我的画像（docs/05 §7.2 /profile）：只读总览 + 编辑入口 + 完成度明细 + 六维 + 联系方式。
 * 联系方式只在本人页面的独立区块里出现（仅本人可见），公开摘要与匹配卡片都不含它。
 */

const auth = useAuthStore()

/** 未加载完成时的占位，让 `buildCompletenessReport` 恒有完整结构可用。 */
const EMPTY_PROFILE: Profile = {
  hard_answers: {},
  soft_answers: {},
  red_lines: [],
  red_lines_confirmed: false,
  tags: [],
  prompts: {},
  dims: { sleep: 0, clean: 0, social: 0, noise: 0, boundary: 0, spend: 0 },
  completeness: 0,
  questionnaire_version: 'v1',
}

const status = ref<'loading' | 'ready' | 'error'>('loading')
const loadError = ref('')
const profile = ref<Profile | null>(null)
const questionnaire = ref<Questionnaire | null>(null)

const basic = computed<BasicProfile>(() => {
  const user = auth.user
  return {
    nickname: user?.nickname ?? '',
    gender: user?.gender ?? 'MALE',
    grade: user?.grade ?? 0,
    college: user?.college ?? '',
    major: user?.major ?? '',
  }
})

const report = computed(() =>
  buildCompletenessReport(
    profile.value ?? EMPTY_PROFILE,
    basic.value,
    questionnaire.value,
  ),
)

const filledPrompts = computed(() => {
  const current = profile.value
  if (!current) {
    return []
  }
  const order = questionnaire.value?.prompts.map((item) => item.key) ?? []
  const known = new Set(order)
  const keys = [...order, ...Object.keys(current.prompts).filter((key) => !known.has(key))]
  return keys
    .filter((key) => (current.prompts[key] ?? '').trim() !== '')
    .map((key) => ({
      key,
      title: questionnaire.value?.prompts.find((item) => item.key === key)?.title ?? key,
      text: current.prompts[key] ?? '',
    }))
})

const redLineLabels = computed(() => {
  const current = profile.value
  if (!current) {
    return []
  }
  return current.red_lines.map(
    (id) => questionnaire.value?.red_lines.find((item) => item.id === id)?.label ?? id,
  )
})

const hardAnswers = computed(() => {
  const current = profile.value
  if (!current) {
    return []
  }
  return (questionnaire.value?.hard ?? [])
    .map((question) => {
      const value = current.hard_answers[question.key] ?? ''
      if (!value) {
        return null
      }
      const option = question.options.find((item) => item.value === value)
      return { key: question.key, title: question.title, label: option?.label ?? value }
    })
    .filter((item): item is { key: string; title: string; label: string } => item !== null)
})

const softAnswers = computed(() => {
  const current = profile.value
  if (!current) {
    return []
  }
  return (questionnaire.value?.soft ?? [])
    .map((question) => {
      const value = current.soft_answers[question.key]
      if (typeof value !== 'number') {
        return null
      }
      return { key: question.key, title: question.title, value }
    })
    .filter((item): item is { key: string; title: string; value: number } => item !== null)
})

const dimSummary = computed(() => {
  const current = profile.value
  if (!current) {
    return ''
  }
  return DIM_KEYS.map((key) => `${DIM_LABELS[key]} ${current.dims[key]}`).join(' · ')
})

async function load(): Promise<void> {
  status.value = 'loading'
  loadError.value = ''
  try {
    const [profilePayload, questionnairePayload] = await Promise.all([
      fetchProfile(),
      fetchQuestionnaire(),
    ])
    profile.value = profilePayload
    questionnaire.value = questionnairePayload
    status.value = 'ready'
  } catch (error) {
    status.value = 'error'
    loadError.value = apiErrorMessage(error, '画像加载失败，请稍后重试。')
  }
}

onMounted(load)
</script>

<template>
  <section class="container profile-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">我的画像</p>
        <h1>别人看到的和你看到的</h1>
        <p class="lede">
          画像用于匹配，不影响他人可见内容。标签订阅与自述会公开展示；六维与红线只有自己可见。
        </p>
      </div>
      <RouterLink class="btn btn-primary" :to="{ name: 'onboarding' }">编辑画像</RouterLink>
    </header>

    <StateBlock v-if="status === 'loading'" status="loading" :rows="2" />
    <StateBlock
      v-else-if="status === 'error'"
      status="error"
      :message="loadError"
      @retry="load"
    />

    <template v-else-if="profile">
      <div class="profile-grid">
        <section class="card profile-card">
          <h2 class="profile-title">完成度</h2>
          <CompletenessPanel :report="report" />
        </section>

        <section class="card profile-card">
          <h2 class="profile-title">六维画像</h2>
          <p class="fine">分数 0–100，只用于匹配计算，不会显示给其他人。</p>
          <DimBars :dims="profile.dims" />
          <p class="fine profile-dims-line">{{ dimSummary }}</p>
        </section>
      </div>

      <section class="card profile-card">
        <h2 class="profile-title">公开内容</h2>
        <p class="fine">下面这些会出现在匹配卡片和你的公开摘要里。</p>

        <div class="profile-block">
          <p class="eyebrow">标签</p>
          <TagChips :tags="profile.tags" empty-text="还没有选标签。" />
        </div>

        <div class="profile-block">
          <p class="eyebrow">自述</p>
          <p v-if="!filledPrompts.length" class="fine">还没有填自述。</p>
          <div v-else class="prompt-blocks">
            <article v-for="prompt in filledPrompts" :key="prompt.key" class="prompt-block">
              <p class="prompt-title">{{ prompt.title }}</p>
              <p class="prompt-text">{{ prompt.text }}</p>
            </article>
          </div>
          <NoticeBar class="profile-privacy" tone="warn">
            请勿填写 QQ、微信、手机号；联系方式只在双方同意后可见。
          </NoticeBar>
        </div>
      </section>

      <section class="card profile-card">
        <h2 class="profile-title">只有自己可见</h2>

        <div class="profile-block">
          <p class="eyebrow">红线</p>
          <p v-if="!profile.red_lines.length" class="fine">没有选择红线。</p>
          <ul v-else class="redline-summary">
            <li v-for="label in redLineLabels" :key="label">{{ label }}</li>
          </ul>
          <p class="fine">
            {{ profile.red_lines_confirmed ? '已确认红线。' : '红线还未确认，暂不计入完成度。' }}
          </p>
        </div>

        <details class="answers">
          <summary>查看问卷答案</summary>
          <div class="answers-body">
            <div>
              <p class="eyebrow">硬指标（{{ hardAnswers.length }} / {{ questionnaire?.hard.length ?? 11 }}）</p>
              <ul class="answer-list">
                <li v-for="answer in hardAnswers" :key="answer.key">
                  <span class="fine">{{ answer.title }}</span>
                  <span>{{ answer.label }}</span>
                </li>
              </ul>
            </div>
            <div>
              <p class="eyebrow">软指标（{{ softAnswers.length }} / {{ questionnaire?.soft.length ?? 6 }}）</p>
              <ul class="answer-list">
                <li v-for="answer in softAnswers" :key="answer.key">
                  <span class="fine">{{ answer.title }}</span>
                  <span>{{ answer.value }} / 5</span>
                </li>
              </ul>
            </div>
          </div>
        </details>
      </section>

      <ContactPanel />
    </template>
  </section>
</template>

<style scoped>
.profile-page {
  padding-bottom: 48px;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.profile-card {
  display: grid;
  gap: 14px;
  margin-bottom: 16px;
}

.profile-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
}

.profile-block {
  display: grid;
  gap: 8px;
}

.profile-block .eyebrow {
  margin: 0;
}

.profile-dims-line {
  margin: 0;
}

.prompt-blocks {
  display: grid;
  gap: 14px;
}

.prompt-block {
  border-left: 2px solid var(--coral);
  padding-left: 14px;
}

.prompt-title {
  margin: 0 0 4px;
  color: var(--muted);
  font-size: 12px;
}

.prompt-text {
  margin: 0;
  display: -webkit-box;
  overflow: hidden;
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.7;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 6;
}

.profile-privacy {
  margin-top: 6px;
}

.redline-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.redline-summary li {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 12px;
}

.answers summary {
  cursor: pointer;
  font-size: 14px;
}

.answers-body {
  display: grid;
  gap: 18px;
  margin-top: 12px;
}

.answer-list {
  display: grid;
  gap: 8px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.answer-list li {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 8px;
  font-size: 13px;
}

@media (max-width: 920px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .profile-card {
    margin-bottom: 12px;
  }
}
</style>
