<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import {
  MAX_PROMPTS,
  MIN_PROMPTS,
  MIN_TAGS,
  QUESTIONNAIRE_VERSION,
  fetchProfile,
  fetchQuestionnaire,
  issueText,
  profileFieldIssues,
  saveProfile,
  type BasicProfile,
  type Dims,
  type HardQuestion,
  type Profile,
  type ProfileFieldIssue,
  type ProfilePatch,
  type Questionnaire,
  type SoftQuestion,
} from '@/api/profiles'
import { useAuthStore } from '@/stores/auth'
import { safeRedirect } from '@/router/redirect'
import CompletenessPanel from '@/components/profile/CompletenessPanel.vue'
import HardQuestionField from '@/components/profile/HardQuestionField.vue'
import PromptEditor from '@/components/profile/PromptEditor.vue'
import RedLinePicker from '@/components/profile/RedLinePicker.vue'
import SoftScale from '@/components/profile/SoftScale.vue'
import TagPicker from '@/components/profile/TagPicker.vue'
import { buildCompletenessReport } from '@/components/profile/completeness'
import StateBlock from '@/components/common/StateBlock.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'

/**
 * 问卷向导（docs/05 §7.2 /onboarding）：4 步、可分段保存、完成度常驻。
 *
 * - 题库来自 `GET /api/questionnaire`，前端不硬编码题目。
 * - 每一步只提交本步字段（PATCH），服务端合并并重算 dims/completeness。
 * - 基本资料在 M1 只读：后端只提供 `GET /api/me`（docs/04 §4.1 的 PUT /api/me 未实现）。
 */

type StepKey = 'basic' | 'hard' | 'soft' | 'tags'

interface StepMeta {
  key: StepKey
  title: string
  summary: string
}

const STEPS: StepMeta[] = [
  { key: 'basic', title: '基本资料', summary: '确认公开信息' },
  { key: 'hard', title: '生活习惯', summary: '11 个硬指标' },
  { key: 'soft', title: '相处方式与红线', summary: '6 个软指标 + 9 条红线' },
  { key: 'tags', title: '标签与自述', summary: '3–8 个标签 + 2–3 段自述' },
]

const EMPTY_DIMS: Dims = { sleep: 0, clean: 0, social: 0, noise: 0, boundary: 0, spend: 0 }
const EMPTY_QUESTIONNAIRE: Questionnaire = {
  version: QUESTIONNAIRE_VERSION,
  hard: [],
  soft: [],
  red_lines: [],
  tags: [],
  prompts: [],
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const status = ref<'loading' | 'ready' | 'error'>('loading')
const loadError = ref('')
const questionnaire = ref<Questionnaire | null>(null)

const step = ref(readStep())
const saving = ref(false)
const savedNotice = ref('')
const banner = ref('')
const clientIssues = ref<Record<string, string>>({})
const serverIssues = ref<Record<string, ProfileFieldIssue>>({})

const draft = reactive({
  hard: {} as Record<string, string>,
  soft: {} as Record<string, number>,
  red: [] as string[],
  confirmed: false,
  tags: [] as string[],
  prompts: {} as Record<string, string>,
})

function readStep(): number {
  const raw = Number(route.query.step)
  if (Number.isInteger(raw) && raw >= 1 && raw <= STEPS.length) {
    return raw
  }
  return 1
}

const questionnaireView = computed<Questionnaire>(
  () => questionnaire.value ?? EMPTY_QUESTIONNAIRE,
)

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

const draftProfile = computed<Profile>(() => ({
  hard_answers: { ...draft.hard },
  soft_answers: { ...draft.soft },
  red_lines: [...draft.red],
  red_lines_confirmed: draft.confirmed,
  tags: [...draft.tags],
  prompts: { ...draft.prompts },
  dims: EMPTY_DIMS,
  completeness: 0,
  questionnaire_version: QUESTIONNAIRE_VERSION,
}))

const report = computed(() =>
  buildCompletenessReport(draftProfile.value, basic.value, questionnaire.value),
)

const hardGroups = computed(() => {
  const order: string[] = []
  const map = new Map<string, HardQuestion[]>()
  for (const question of questionnaireView.value.hard) {
    if (!map.has(question.group)) {
      map.set(question.group, [])
      order.push(question.group)
    }
    map.get(question.group)?.push(question)
  }
  return order.map((group) => ({ group, questions: map.get(group) ?? [] }))
})

const currentStep = computed<StepMeta>(() => STEPS[step.value - 1] ?? STEPS[0])

const hardAnsweredCount = computed(
  () => questionnaireView.value.hard.filter((question) => Boolean(draft.hard[question.key])).length,
)

const softQuestions = computed<SoftQuestion[]>(() => questionnaireView.value.soft)

const promptErrors = computed<Record<string, string>>(() => {
  const result: Record<string, string> = {}
  for (const [key, message] of Object.entries(clientIssues.value)) {
    if (key.startsWith('prompts.')) {
      result[key.slice('prompts.'.length)] = message
    }
  }
  for (const key of Object.keys(serverIssues.value)) {
    if (key.startsWith('prompts.')) {
      result[key.slice('prompts.'.length)] = issueText(serverIssues.value, key)
    }
  }
  return result
})

const localIssueCount = computed(() => Object.keys(clientIssues.value).length)

const primaryLabel = computed(() => {
  if (step.value === 1) {
    return '开始填问卷'
  }
  return step.value < STEPS.length ? '保存并继续' : '保存并完成'
})

function errorOf(key: string): string {
  return clientIssues.value[key] ?? issueText(serverIssues.value, key)
}

function applyProfile(next: Profile): void {
  draft.hard = { ...next.hard_answers }
  draft.soft = { ...next.soft_answers }
  draft.red = [...next.red_lines]
  draft.confirmed = next.red_lines_confirmed
  draft.tags = [...next.tags]
  draft.prompts = { ...next.prompts }
}

async function load(): Promise<void> {
  status.value = 'loading'
  loadError.value = ''
  try {
    const [questionnairePayload, profile] = await Promise.all([
      fetchQuestionnaire(),
      fetchProfile(),
    ])
    questionnaire.value = questionnairePayload
    applyProfile(profile)
    status.value = 'ready'
  } catch (error) {
    status.value = 'error'
    loadError.value = apiErrorMessage(error, '问卷加载失败，请稍后重试。')
  }
}

function goPrev(): void {
  if (step.value > 1) {
    step.value -= 1
  }
}

interface PatchResult {
  patch: ProfilePatch | null
  issues: Record<string, string>
  blocked: boolean
}

function buildPatch(stepIndex: number): PatchResult {
  const issues: Record<string, string> = {}
  const view = questionnaireView.value

  if (stepIndex === 2) {
    return {
      patch: { hard_answers: { ...draft.hard }, questionnaire_version: QUESTIONNAIRE_VERSION },
      issues,
      blocked: false,
    }
  }

  if (stepIndex === 3) {
    return {
      patch: {
        soft_answers: { ...draft.soft },
        red_lines: [...draft.red],
        red_lines_confirmed: draft.confirmed,
      },
      issues,
      blocked: false,
    }
  }

  if (stepIndex === 4) {
    const prompts: Record<string, string> = {}
    for (const question of view.prompts) {
      const raw = (draft.prompts[question.key] ?? '').trim()
      if (!raw) {
        continue
      }
      const lines = raw.split(/\r\n|\r|\n/).length
      if (raw.length > question.max_length) {
        issues[`prompts.${question.key}`] = `最多 ${question.max_length} 字，当前 ${raw.length} 字。`
      } else if (lines > 3) {
        issues[`prompts.${question.key}`] = `最多 3 行，当前 ${lines} 行。`
      } else {
        prompts[question.key] = raw
      }
    }
    if (Object.keys(prompts).length > MAX_PROMPTS) {
      issues.prompts = `最多填 ${MAX_PROMPTS} 题自述。`
    }
    const blocked = Object.keys(issues).length > 0
    return {
      patch: blocked ? null : { tags: [...draft.tags], prompts },
      issues,
      blocked,
    }
  }

  return { patch: null, issues, blocked: false }
}

function finish(): void {
  const target = safeRedirect(route.query.redirect) ?? '/match'
  void router.replace(target)
}

async function saveStep(): Promise<void> {
  if (saving.value) {
    return
  }
  banner.value = ''

  // 第 1 步没有可写字段（基本资料只读），直接进入下一步。
  if (step.value === 1) {
    step.value = 2
    return
  }

  const result = buildPatch(step.value)
  clientIssues.value = result.issues
  if (result.blocked || !result.patch) {
    banner.value = '还有题目需要调整，改完再保存。'
    return
  }

  saving.value = true
  savedNotice.value = ''
  try {
    const updated = await saveProfile(result.patch)
    applyProfile(updated)
    serverIssues.value = {}
    clientIssues.value = {}
    // 必须等 /api/me 返回再决定是否跳转：路由守卫的 requiresProfile 读的是 store 里的
    // profile_completeness，若提前跳转会被守卫弹回 /onboarding。
    await auth.fetchMe().catch(() => undefined)

    if (step.value < STEPS.length) {
      step.value += 1
      savedNotice.value = '已保存这一步，接着填下一步。'
      window.scrollTo({ top: 0 })
    } else if (updated.completeness >= 100) {
      savedNotice.value = '画像已完成，正在进入匹配。'
      finish()
    } else {
      savedNotice.value = `已保存。画像还差 ${100 - updated.completeness}% 才能开始匹配；已保存的内容不会丢。`
    }
  } catch (error) {
    const issues = profileFieldIssues(error)
    serverIssues.value = issues
    const serverCount = Object.keys(issues).length
    banner.value = serverCount
      ? `有 ${serverCount} 项需要修改，请检查标红的题目。`
      : apiErrorMessage(error, '保存失败，请稍后重试。')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="container wizard">
    <header class="wizard-head">
      <p class="eyebrow">问卷 {{ questionnaireView.version }}</p>
      <h1 class="display">把你的“住法”说清楚</h1>
      <p class="lede">
        四步填完就能开始匹配。每一步都会单独保存，中途离开不会丢已保存的内容。
      </p>
    </header>

    <StateBlock
      v-if="status === 'loading'"
      status="loading"
      :rows="2"
      title="正在加载问卷"
    />
    <StateBlock
      v-else-if="status === 'error'"
      status="error"
      :message="loadError"
      @retry="load"
    />

    <template v-else>
      <div class="wizard-status card">
        <div class="wizard-status-head">
          <span class="fine">画像完成度</span>
          <strong class="wizard-status-value">{{ report.total }}%</strong>
        </div>
        <div
          class="progress"
          role="progressbar"
          aria-label="画像完成度"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="report.total"
        >
          <span :style="{ width: `${report.total}%` }"></span>
        </div>
        <p class="fine wizard-status-note">
          {{ report.remaining > 0
            ? `画像还差 ${report.remaining}% 才能开始匹配；已保存的内容不会丢。`
            : '画像已完成，可以开始匹配。' }}
        </p>
      </div>

      <ol class="wizard-steps">
        <li v-for="(item, index) in STEPS" :key="item.key">
          <button
            type="button"
            class="wizard-step"
            :class="{ 'wizard-step-active': step === index + 1 }"
            :aria-current="step === index + 1 ? 'step' : undefined"
            @click="step = index + 1"
          >
            <span class="wizard-step-index">{{ index + 1 }}</span>
            <span class="wizard-step-text">
              <strong>{{ item.title }}</strong>
              <span class="fine">{{ item.summary }}</span>
            </span>
          </button>
        </li>
      </ol>

      <NoticeBar v-if="banner" tone="error" title="还没有保存">{{ banner }}</NoticeBar>
      <NoticeBar v-else-if="localIssueCount" tone="warn">
        有 {{ localIssueCount }} 项填写不符合要求，已在下面标红。
      </NoticeBar>
      <NoticeBar v-else-if="savedNotice" tone="info">{{ savedNotice }}</NoticeBar>

      <form class="wizard-form" novalidate @submit.prevent="saveStep">
        <div class="wizard-body card">
          <h2 class="wizard-title">{{ currentStep.title }}</h2>

          <div v-if="step === 1" class="stack">
            <p class="fine">
              这些是注册时填写的公开资料。当前版本暂不支持在问卷里修改昵称/学院/专业；如需变更请联系管理员。
            </p>
            <dl class="basic-grid">
              <div class="basic-row">
                <dt>昵称</dt>
                <dd>{{ basic.nickname || '未填写' }}</dd>
              </div>
              <div class="basic-row">
                <dt>性别</dt>
                <dd>{{ basic.gender === 'MALE' ? '男' : '女' }}</dd>
              </div>
              <div class="basic-row">
                <dt>年级</dt>
                <dd>{{ basic.grade ? `${basic.grade} 年级` : '未填写' }}</dd>
              </div>
              <div class="basic-row">
                <dt>学院</dt>
                <dd>{{ basic.college || '未填写' }}</dd>
              </div>
              <div class="basic-row">
                <dt>专业</dt>
                <dd>{{ basic.major || '未填写' }}</dd>
              </div>
            </dl>
            <p class="fine">
              性别只用于匹配范围（同院同性别），不会展示给不符合条件的人；画像里也不展示联系方式。
            </p>
          </div>

          <div v-else-if="step === 2" class="stack">
            <p class="fine">
              11 个硬指标决定六维里的基础分。可以分次填，全部答完才拿满 20 分。
            </p>
            <section v-for="group in hardGroups" :key="group.group" class="question-group">
              <h3 class="question-group-title">{{ group.group }}</h3>
              <HardQuestionField
                v-for="question in group.questions"
                :key="question.key"
                :question="question"
                :model-value="draft.hard[question.key] ?? ''"
                :error="errorOf(`hard_answers.${question.key}`)"
                @update:model-value="draft.hard[question.key] = $event"
              />
            </section>
            <p class="fine">已答 {{ hardAnsweredCount }} / {{ questionnaireView.hard.length }} 题。</p>
          </div>

          <div v-else-if="step === 3" class="stack">
            <section class="question-group">
              <h3 class="question-group-title">6 个软指标</h3>
              <p class="fine">每题 1–5 档，答 1 题得 5 分；两端是含义，中间是程度。</p>
              <SoftScale
                v-for="question in softQuestions"
                :key="question.key"
                :question="question"
                :model-value="draft.soft[question.key]"
                :error="errorOf(`soft_answers.${question.key}`)"
                @update:model-value="draft.soft[question.key] = $event"
              />
            </section>

            <section class="question-group">
              <h3 class="question-group-title">9 条红线</h3>
              <p class="fine">
                红线是「无论如何都接受不了」的事。选中的红线会参与匹配计算；没有就点「以上都不是」，然后勾选确认。
              </p>
              <RedLinePicker
                :options="questionnaireView.red_lines"
                :model-value="draft.red"
                :confirmed="draft.confirmed"
                :error="errorOf('red_lines')"
                :confirm-error="errorOf('red_lines_confirmed')"
                @update:model-value="draft.red = $event"
                @update:confirmed="draft.confirmed = $event"
              />
              <p v-if="draft.red.length && !draft.confirmed" class="fine">
                选了红线但还没勾选确认，这一块暂时不计分。
              </p>
            </section>
          </div>

          <div v-else class="stack">
            <section class="question-group">
              <h3 class="question-group-title">标签</h3>
              <p class="fine">标签是公开的，会出现在匹配卡片上；至少 {{ MIN_TAGS }} 个才有 10 分。</p>
              <TagPicker
                :groups="questionnaireView.tags"
                :model-value="draft.tags"
                :error="errorOf('tags')"
                @update:model-value="draft.tags = $event"
              />
            </section>

            <section class="question-group">
              <h3 class="question-group-title">自述</h3>
              <p class="fine">
                从下面 {{ questionnaireView.prompts.length }} 题里挑 {{ MIN_PROMPTS }}–{{ MAX_PROMPTS }} 题写，会被公开展示。
              </p>
              <PromptEditor
                :questions="questionnaireView.prompts"
                :model-value="draft.prompts"
                :errors="promptErrors"
                @update:model-value="draft.prompts = $event"
              />
            </section>
          </div>
        </div>

        <div class="wizard-actions">
          <button v-if="step > 1" type="button" class="btn btn-ghost" @click="goPrev">
            上一步
          </button>
          <button type="submit" class="btn btn-primary wizard-submit" :disabled="saving">
            {{ saving ? '保存中…' : primaryLabel }}
          </button>
        </div>
      </form>

      <CompletenessPanel class="wizard-report" :report="report" />
    </template>
  </section>
</template>

<style scoped>
.wizard {
  padding-bottom: 40px;
}

.wizard-head {
  padding: 40px 0 24px;
}

.wizard-head h1 {
  margin: 8px 0 12px;
}

.stack {
  display: grid;
  gap: 18px;
}

.wizard-status {
  display: grid;
  gap: 8px;
  margin-bottom: 20px;
}

.wizard-status-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.wizard-status-value {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 500;
}

.wizard-status-note {
  margin: 0;
}

.wizard-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 0 0 20px;
  padding: 0;
  list-style: none;
}

.wizard-step {
  display: flex;
  width: 100%;
  gap: 10px;
  align-items: flex-start;
  min-height: 56px;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 10px 12px;
  background: var(--paper);
  color: var(--ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.wizard-step:hover {
  border-color: var(--ink);
}

.wizard-step-active {
  border-color: var(--coral);
  background: color-mix(in srgb, var(--coral) 7%, var(--paper));
}

.wizard-step-index {
  display: grid;
  flex: none;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: var(--sand-deep);
  font-size: 12px;
  font-weight: 600;
}

.wizard-step-text {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.wizard-form {
  display: grid;
  gap: 16px;
}

.wizard-body {
  display: grid;
  gap: 18px;
}

.wizard-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 500;
}

.question-group {
  display: grid;
  gap: 14px;
  border-top: 1px solid var(--line);
  padding-top: 18px;
}

.question-group:first-child {
  border-top: 0;
  padding-top: 0;
}

.question-group-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.basic-grid {
  display: grid;
  gap: 10px;
  margin: 0;
}

.basic-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
}

.basic-row dt {
  color: var(--muted);
  font-size: 13px;
}

.basic-row dd {
  margin: 0;
  font-size: 14px;
  text-align: right;
}

.wizard-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: flex-end;
}

.wizard-submit {
  min-width: 160px;
}

.wizard-report {
  margin-top: 24px;
}

@media (max-width: 920px) {
  .wizard-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .wizard-head {
    padding-top: 28px;
  }

  .wizard-steps {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .wizard-step-text .fine {
    display: none;
  }

  .wizard-actions {
    position: sticky;
    bottom: 0;
    z-index: 5;
    justify-content: stretch;
    margin: 0 -14px -14px;
    padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
    border-top: 1px solid var(--line);
    background: var(--paper);
  }

  .wizard-actions .btn {
    flex: 1 1 auto;
  }

  .wizard-submit {
    min-width: 0;
  }
}
</style>
