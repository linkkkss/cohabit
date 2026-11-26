<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  createConnection,
  connectionErrorMessage,
} from '@/api/connections'
import { fetchPublicUser, fetchQuestionnaire, type PublicUser, type Questionnaire } from '@/api/profiles'
import type { MatchScore } from '@/api/matching'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import TagChips from '@/components/common/TagChips.vue'
import DimCompare from '@/components/match/DimCompare.vue'
import SecurityActions from '@/components/security/SecurityActions.vue'
import { lastActiveText } from '@/components/connections/connectionFormat'

/**
 * 匹配详情（docs/05 §7.2、docs/07 2:50–3:20）：用原生 `<dialog>`，Esc 关闭、
 * 打开时焦点进弹层。`/match/:uid` 路由不在 F1 的路由表里，所以详情是
 * `/match` 页内的弹层；底部吸底操作是“发起邀请”+“关闭”，邀请可选容量与留言。
 *
 * 自述需要 `GET /api/users/:uid`（公开摘要）另取；联系方式在这个弹层里也不展示。
 */
const props = defineProps<{
  match: MatchScore | null
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'blocked', uid: string): void
}>()

const dialogRef = ref<HTMLDialogElement | null>(null)
const publicUser = ref<PublicUser | null>(null)
const questionnaire = ref<Questionnaire | null>(null)
const promptsStatus = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')

/** 发起邀请（docs/04 §4.4：INVITE + capacity_pref；留言由后端截到 200 字）。 */
type InviteStatus = 'idle' | 'submitting' | 'success' | 'error'
const CAPACITY_OPTIONS: Array<2 | 4 | 6> = [2, 4, 6]
const MESSAGE_MAX_LENGTH = 500
const MESSAGE_SEND_LIMIT = 200
const capacity = ref<2 | 4 | 6>(4)
const message = ref('')
const inviteStatus = ref<InviteStatus>('idle')
const inviteError = ref('')
const sentTo = ref('')

const submitting = computed(() => inviteStatus.value === 'submitting')
const messageOverSendLimit = computed(() => message.value.length > MESSAGE_SEND_LIMIT)

/** 举报/拉黑后的就地反馈；拉黑后关闭弹层，由列表重新加载。 */
const reportNotice = ref('')
const targetUidNumber = computed(() => {
  const uid = props.match?.target.uid ?? ''
  const value = Number(uid)
  return Number.isInteger(value) && value > 0 ? value : 0
})

function onReported(): void {
  reportNotice.value = '举报已提交，管理员会核实。对方不会收到你举报的通知。'
}

function onBlocked(uid: string): void {
  emit('blocked', uid)
  closeDialog()
}

const meta = computed(() => {
  const target = props.match?.target
  if (!target) {
    return ''
  }
  const gender = target.gender === 'MALE' ? '男' : '女'
  return [gender, target.grade ? `${target.grade} 年级` : '', target.college, target.major]
    .filter((part) => Boolean(part))
    .join(' · ')
})

/** 红线冲突在下方有独立区块，这里只列其余风险，作为一句话摘要。 */
const riskChips = computed(() =>
  (props.match?.risks ?? []).filter((risk) => risk.code !== 'red_line'),
)
const activeText = computed(() => lastActiveText(props.match?.target.last_active_at ?? null))

const promptItems = computed(() => {
  const user = publicUser.value
  if (!user) {
    return []
  }
  const order = questionnaire.value?.prompts.map((item) => item.key) ?? Object.keys(user.prompts)
  const known = new Set(order)
  const keys = [...order, ...Object.keys(user.prompts).filter((key) => !known.has(key))]
  return keys
    .filter((key) => (user.prompts[key] ?? '').trim() !== '')
    .map((key) => ({
      key,
      title: questionnaire.value?.prompts.find((item) => item.key === key)?.title ?? '自述',
      text: user.prompts[key] ?? '',
    }))
})

async function loadPublic(): Promise<void> {
  const target = props.match?.target
  if (!target) {
    return
  }
  promptsStatus.value = 'loading'
  publicUser.value = null
  try {
    const [user, payload] = await Promise.all([
      fetchPublicUser(target.uid),
      fetchQuestionnaire().catch(() => null),
    ])
    publicUser.value = user
    if (payload) {
      questionnaire.value = payload
    }
    promptsStatus.value = 'ready'
  } catch {
    promptsStatus.value = 'error'
  }
}

function resetInvite(): void {
  capacity.value = 4
  message.value = ''
  inviteStatus.value = 'idle'
  inviteError.value = ''
  sentTo.value = ''
  reportNotice.value = ''
}

async function submitInvite(): Promise<void> {
  const target = props.match?.target
  if (!target || inviteStatus.value === 'submitting' || inviteStatus.value === 'success') {
    return
  }
  inviteStatus.value = 'submitting'
  inviteError.value = ''
  try {
    const text = message.value.trim().slice(0, MESSAGE_SEND_LIMIT)
    await createConnection({
      type: 'INVITE',
      target_uid: target.uid,
      capacity_pref: capacity.value,
      message: text || undefined,
    })
    sentTo.value = target.nickname
    inviteStatus.value = 'success'
  } catch (error) {
    inviteStatus.value = 'error'
    inviteError.value = connectionErrorMessage(error, '邀请没有发送成功，请稍后重试。')
  }
}

function openDialog(): void {
  const element = dialogRef.value
  if (!element) {
    return
  }
  if (!element.open) {
    element.showModal()
  }
  void loadPublic()
}

function closeDialog(): void {
  dialogRef.value?.close()
}

function onClose(): void {
  resetInvite()
  emit('update:open', false)
}

watch(
  () => props.open,
  (value) => {
    if (value) {
      resetInvite()
      openDialog()
    } else if (dialogRef.value?.open) {
      closeDialog()
    }
  },
)

watch(
  () => props.match?.target.uid,
  () => {
    resetInvite()
    if (props.open) {
      void loadPublic()
    }
  },
)

onMounted(() => {
  if (props.open) {
    openDialog()
  }
})
</script>

<template>
  <dialog
    ref="dialogRef"
    class="match-dialog"
    aria-labelledby="match-dialog-title"
    @close="onClose"
  >
    <div v-if="match" class="dialog-body">
      <header class="dialog-head">
        <AvatarBadge :name="match.target.nickname" size="lg" />
        <div class="dialog-id">
          <h2 id="match-dialog-title">{{ match.target.nickname }}</h2>
          <p class="candidate-meta">{{ meta }}</p>
          <p class="fine active-line">最近活跃：{{ activeText }}</p>
        </div>
        <div class="dialog-score">
          <span class="score">{{ match.score }}</span>
          <span class="fine">契合度</span>
        </div>
      </header>

      <p v-if="match.target.headline" class="headline">{{ match.target.headline }}</p>
      <TagChips :tags="match.target.tags" empty-text="对方还没有选标签。" />

      <p v-if="riskChips.length" class="risk-row">
        <span v-for="risk in riskChips" :key="risk.code + risk.text" class="risk-chip">
          {{ risk.text }}
        </span>
      </p>

      <NoticeBar v-if="reportNotice" tone="info">
        {{ reportNotice }}
      </NoticeBar>

      <div class="dialog-security">
        <SecurityActions
          target-type="USER"
          :target-id="targetUidNumber"
          :target-name="match.target.nickname"
          :block-uid="match.target.uid"
          @reported="onReported"
          @blocked="onBlocked"
        />
      </div>

      <section class="dialog-section">
        <h3>为什么可能合拍</h3>
        <ul class="reasons">
          <li v-for="reason in match.reasons" :key="reason">{{ reason }}</li>
        </ul>
      </section>

      <section class="dialog-section">
        <h3>六维对比</h3>
        <DimCompare :dims="match.dims" />
      </section>

      <section v-if="match.conflicts.length" class="dialog-section">
        <h3>红线冲突</h3>
        <NoticeBar tone="warn" :title="`有 ${match.conflicts.length} 项红线冲突`">
          有 {{ match.conflicts.length }} 项红线冲突，分数已按规则封顶；仍可查看，邀请前请再确认。
        </NoticeBar>
        <ul class="conflict-list">
          <li v-for="conflict in match.conflicts" :key="`${conflict.owner}-${conflict.red_line}`">
            <strong>{{ conflict.label }}</strong>
            <p class="fine">{{ conflict.message }}</p>
          </li>
        </ul>
      </section>

      <NoticeBar v-if="match.version_warning" tone="warn">
        {{ match.version_warning }}
      </NoticeBar>

      <section class="dialog-section">
        <h3>自述</h3>
        <p v-if="promptsStatus === 'loading'" class="fine">正在加载自述…</p>
        <p v-else-if="promptsStatus === 'error'" class="fine">
          自述暂时加载不出来，稍后再试。
        </p>
        <p v-else-if="!promptItems.length" class="fine">对方还没有填自述。</p>
        <div v-else class="prompt-blocks">
          <article v-for="prompt in promptItems" :key="prompt.key" class="prompt-block">
            <p class="prompt-title">{{ prompt.title }}</p>
            <p class="prompt-text">{{ prompt.text }}</p>
          </article>
        </div>
      </section>

      <section v-if="inviteStatus === 'success'" class="invite-success" role="status">
        <p class="eyebrow">已发送</p>
        <h3>已发送，等待对方同意</h3>
        <p class="fine">
          邀请已发给 {{ sentTo }}。对方同意后，你们会看到彼此的联系方式；双方都确认后才会组成寝室。
        </p>
        <RouterLink
          class="btn btn-small btn-primary"
          :to="{ name: 'connections', query: { role: 'sent' } }"
        >
          查看发出的请求
        </RouterLink>
      </section>

      <section v-else class="dialog-section invite-section">
        <h3>发起邀请</h3>
        <fieldset class="choice-field">
          <legend class="field-legend">期望容量</legend>
          <div class="choice-group">
            <label
              v-for="option in CAPACITY_OPTIONS"
              :key="option"
              class="choice"
              :class="{ selected: capacity === option }"
            >
              <input v-model.number="capacity" type="radio" name="match-capacity" :value="option" />
              <span>{{ option }} 人寝</span>
            </label>
          </div>
          <p class="fine">默认 4 人；寝室建立后容量不可修改。</p>
        </fieldset>
        <label class="field" for="match-invite-message">
          <span>留言（可选）</span>
          <textarea
            id="match-invite-message"
            v-model="message"
            rows="3"
            :maxlength="MESSAGE_MAX_LENGTH"
            placeholder="想找作息接近、能一起自习的室友"
          ></textarea>
        </label>
        <p class="fine">
          写清作息和整洁习惯会更容易被接受。留言最多 500 字，发送时保留前 200 字。
        </p>
        <p v-if="messageOverSendLimit" class="invite-warn">
          留言超过 200 字，发送时只会保留前 200 字。
        </p>
      </section>

      <p v-if="inviteStatus !== 'success'" class="fine dialog-unlock">
        双方都同意后，这里会显示彼此的联系方式。
      </p>
    </div>

    <footer class="dialog-foot">
      <NoticeBar
        v-if="inviteStatus === 'error' && inviteError"
        tone="error"
        title="邀请没有发送成功"
      >
        {{ inviteError }}
      </NoticeBar>
      <div class="dialog-actions">
        <button
          v-if="inviteStatus !== 'success'"
          type="button"
          class="btn btn-primary"
          :disabled="!match || submitting"
          @click="submitInvite"
        >
          {{ submitting ? '发送中…' : '发起邀请' }}
        </button>
        <button type="button" class="btn btn-ghost" :disabled="submitting" @click="closeDialog">
          关闭
        </button>
      </div>
    </footer>
  </dialog>
</template>

<style scoped>
.match-dialog {
  width: min(680px, calc(100% - 32px));
  max-height: min(88vh, 960px);
  margin: auto;
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 0;
  background: var(--paper);
  color: var(--ink);
}

.match-dialog[open] {
  display: flex;
  flex-direction: column;
}

.match-dialog::backdrop {
  background: color-mix(in srgb, var(--ink) 45%, transparent);
}

.dialog-body {
  display: grid;
  flex: 1 1 auto;
  gap: 18px;
  overflow: auto;
  min-height: 0;
  padding: 22px;
}

.dialog-head {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.dialog-id {
  display: grid;
  flex: 1;
  gap: 2px;
  min-width: 0;
}

.dialog-id h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 500;
}

.dialog-score {
  display: grid;
  justify-items: end;
  gap: 2px;
}

.dialog-score .score {
  line-height: 1;
}

.headline {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  line-height: 1.6;
}

.dialog-security {
  display: flex;
  justify-content: flex-start;
}

.dialog-section {
  display: grid;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}

.dialog-section h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.reasons {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
}

.risk-chip {
  border: 1px solid color-mix(in srgb, var(--coral) 30%, var(--line));
  border-radius: 999px;
  padding: 2px 9px;
  background: color-mix(in srgb, var(--coral) 5%, var(--paper));
  color: var(--coral-dark);
  font-size: 11px;
  line-height: 1.7;
}

.active-line {
  margin: 2px 0 0;
  color: var(--muted);
}

.reasons li {
  position: relative;
  padding-left: 16px;
  font-size: 14px;
  line-height: 1.7;
}

.reasons li::before {
  position: absolute;
  top: 0.7em;
  left: 0;
  width: 8px;
  height: 2px;
  background: var(--coral);
  content: '';
}

.conflict-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.conflict-list li {
  display: grid;
  gap: 2px;
  border-left: 2px solid color-mix(in srgb, var(--coral) 55%, var(--line));
  padding-left: 12px;
  font-size: 14px;
}

.conflict-list p {
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
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.dialog-unlock {
  margin: 0;
}

.invite-section .field > span {
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.invite-section .field textarea {
  min-height: 92px;
  line-height: 1.65;
  resize: vertical;
}

.invite-warn {
  margin: 0;
  color: var(--coral-dark);
  font-size: 12px;
}

.invite-success {
  display: grid;
  justify-items: start;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 18px;
  background: var(--sand);
}

.invite-success .eyebrow {
  margin: 0;
}

.invite-success h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
  line-height: 1.4;
}

.invite-success .fine {
  margin: 0;
}

.dialog-foot {
  position: sticky;
  bottom: 0;
  display: grid;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding: 12px 22px calc(12px + env(safe-area-inset-bottom));
  background: var(--paper);
}

.dialog-actions {
  display: flex;
  gap: 10px;
}

.dialog-actions .btn {
  flex: 1;
  min-height: 44px;
}

.dialog-foot .btn {
  min-height: 44px;
}

@media (max-width: 640px) {
  .match-dialog {
    width: 100%;
    max-height: 92vh;
    border-radius: 16px;
  }

  .dialog-body {
    padding: 18px 16px;
  }

  .dialog-foot {
    padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
  }

  .dialog-actions {
    flex-direction: column;
  }
}
</style>
