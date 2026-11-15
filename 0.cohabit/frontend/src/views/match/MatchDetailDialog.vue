<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { fetchPublicUser, fetchQuestionnaire, type PublicUser, type Questionnaire } from '@/api/profiles'
import type { MatchScore } from '@/api/matching'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import TagChips from '@/components/common/TagChips.vue'
import DimCompare from '@/components/match/DimCompare.vue'

/**
 * 匹配详情（docs/05 §7.2）：用原生 `<dialog>`，Esc 关闭、打开时焦点进弹层。
 * `/match/:uid` 路由不在 F1 的路由表里（路由不在本任务写权限内），
 * 所以详情是 `/match` 页内的弹层，而不是独立页；移动端操作条固定在弹层底部。
 *
 * 自述需要 `GET /api/users/:uid`（公开摘要）另取；联系方式在这个弹层里也不展示。
 */
const props = defineProps<{
  match: MatchScore | null
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
}>()

const dialogRef = ref<HTMLDialogElement | null>(null)
const publicUser = ref<PublicUser | null>(null)
const questionnaire = ref<Questionnaire | null>(null)
const promptsStatus = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')

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
  emit('update:open', false)
}

watch(
  () => props.open,
  (value) => {
    if (value) {
      openDialog()
    } else if (dialogRef.value?.open) {
      closeDialog()
    }
  },
)

watch(
  () => props.match?.target.uid,
  () => {
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
        </div>
        <div class="dialog-score">
          <span class="score">{{ match.score }}</span>
          <span class="fine">契合度</span>
        </div>
      </header>

      <p v-if="match.target.headline" class="headline">{{ match.target.headline }}</p>
      <TagChips :tags="match.target.tags" empty-text="对方还没有选标签。" />

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

      <p class="fine dialog-unlock">双方都同意后，这里会显示彼此的联系方式。</p>
    </div>

    <footer class="dialog-foot">
      <button type="button" class="btn btn-primary btn-block" @click="closeDialog">关闭</button>
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

.match-dialog::backdrop {
  background: color-mix(in srgb, var(--ink) 45%, transparent);
}

.dialog-body {
  display: grid;
  gap: 18px;
  overflow: auto;
  max-height: calc(88vh - 76px);
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

.dialog-foot {
  position: sticky;
  bottom: 0;
  border-top: 1px solid var(--line);
  padding: 12px 22px calc(12px + env(safe-area-inset-bottom));
  background: var(--paper);
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
    max-height: calc(92vh - 76px);
    padding: 18px 16px;
  }

  .dialog-foot {
    padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
  }
}
</style>
