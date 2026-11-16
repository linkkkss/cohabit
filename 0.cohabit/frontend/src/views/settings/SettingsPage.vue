<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { apiErrorMessage } from '@/api/client'
import { deleteMe, meFieldErrors, updateMe } from '@/api/me'
import {
  blockErrorMessage,
  fetchBlocks,
  unblockUser,
  type BlockedUser,
} from '@/api/security'
import { useAuthStore } from '@/stores/auth'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import ContactPanel from '@/components/profile/ContactPanel.vue'
import ConfirmDialog from '@/components/rooms/ConfirmDialog.vue'

/**
 * 设置页（docs/05 §7、开发手册 §6.1）：基础资料、联系方式、拉黑列表、账号与安全。
 *
 * - 基础资料走 `PUT /api/me`，性别/邮箱只读；保存后重新拉取 `GET /api/me`；
 * - 联系方式复用 ContactPanel（仅本人可见，脱敏展示）；
 * - 拉黑列表走 `GET/DELETE /api/blocks`，空态/错误/加载齐全；
 * - 注销账号走 `DELETE /api/me`，需要输入「注销」二次确认。
 */

const auth = useAuthStore()
const router = useRouter()

const GENDER_LABELS: Record<string, string> = { MALE: '男', FEMALE: '女' }
const GRADES = [
  { value: 1, label: '大一' },
  { value: 2, label: '大二' },
  { value: 3, label: '大三' },
  { value: 4, label: '大四' },
  { value: 5, label: '大五' },
]

const form = reactive({
  nickname: '',
  grade: 1,
  college: '',
  major: '',
})
const issues = reactive<Record<string, string>>({})
const saving = ref(false)
const saveError = ref('')
const savedNotice = ref('')

function clearIssues(): void {
  for (const key of Object.keys(issues)) {
    delete issues[key]
  }
}

function fillFromUser(): void {
  const user = auth.user
  if (!user) {
    return
  }
  form.nickname = user.nickname
  form.grade = user.grade || 1
  form.college = user.college
  form.major = user.major
}

function validate(): boolean {
  clearIssues()
  const nickname = form.nickname.trim()
  if (!nickname) {
    issues.nickname = '请填写昵称。'
  } else if (nickname.length > 20) {
    issues.nickname = '昵称最多 20 个字。'
  }
  if (!Number.isInteger(form.grade) || form.grade < 1 || form.grade > 5) {
    issues.grade = '请选择年级。'
  }
  if (!form.college.trim()) {
    issues.college = '请填写学院。'
  } else if (form.college.trim().length > 50) {
    issues.college = '学院最多 50 个字。'
  }
  if (!form.major.trim()) {
    issues.major = '请填写专业。'
  } else if (form.major.trim().length > 50) {
    issues.major = '专业最多 50 个字。'
  }
  return Object.keys(issues).length === 0
}

async function saveProfile(): Promise<void> {
  if (saving.value) {
    return
  }
  saveError.value = ''
  savedNotice.value = ''
  if (!validate()) {
    return
  }
  saving.value = true
  try {
    await updateMe({
      nickname: form.nickname.trim(),
      grade: form.grade,
      college: form.college.trim(),
      major: form.major.trim(),
    })
    await auth.fetchMe()
    fillFromUser()
    savedNotice.value = '资料已保存。'
  } catch (caught) {
    const fieldIssues = meFieldErrors(caught)
    for (const [field, message] of Object.entries(fieldIssues)) {
      issues[field] = message
    }
    saveError.value = apiErrorMessage(caught, '保存失败，请检查后再试。')
  } finally {
    saving.value = false
  }
}

/* 拉黑列表 */
const blocksStatus = ref<'loading' | 'ready' | 'error'>('loading')
const blocks = ref<BlockedUser[]>([])
const blocksTotal = ref(0)
const blocksNext = ref<string | null>(null)
const blocksError = ref('')
const blocksNotice = ref('')
const loadingMoreBlocks = ref(false)
const unblockingUid = ref('')

const hasMoreBlocks = computed(() => blocksNext.value !== null)

async function loadBlocks(reset = true): Promise<void> {
  if (reset) {
    blocksStatus.value = 'loading'
    blocksError.value = ''
    blocksNotice.value = ''
  }
  try {
    const payload = await fetchBlocks({ page: reset ? 1 : blocks.value.length / 20 + 1 })
    if (reset) {
      blocks.value = payload.results
    } else {
      blocks.value = [...blocks.value, ...payload.results]
    }
    blocksTotal.value = payload.count
    blocksNext.value = payload.next
    blocksStatus.value = 'ready'
  } catch (caught) {
    blocksStatus.value = 'error'
    blocksError.value = apiErrorMessage(caught, '拉黑列表加载失败，请稍后重试。')
  }
}

async function loadMoreBlocks(): Promise<void> {
  if (loadingMoreBlocks.value || !hasMoreBlocks.value) {
    return
  }
  loadingMoreBlocks.value = true
  try {
    const payload = await fetchBlocks({
      page: Math.floor(blocks.value.length / 20) + 1,
      pageSize: 20,
    })
    blocks.value = [...blocks.value, ...payload.results]
    blocksTotal.value = payload.count
    blocksNext.value = payload.next
  } catch (caught) {
    blocksNotice.value = apiErrorMessage(caught, '加载更多失败，请稍后重试。')
  } finally {
    loadingMoreBlocks.value = false
  }
}

async function unblock(item: BlockedUser): Promise<void> {
  if (unblockingUid.value) {
    return
  }
  unblockingUid.value = item.uid
  blocksNotice.value = ''
  try {
    await unblockUser(item.uid)
    blocks.value = blocks.value.filter((entry) => entry.uid !== item.uid)
    blocksTotal.value = Math.max(0, blocksTotal.value - 1)
    blocksNotice.value = `已解除对「${item.nickname}」的拉黑。`
  } catch (caught) {
    blocksNotice.value = blockErrorMessage(caught, '解除拉黑失败，请稍后重试。')
  } finally {
    unblockingUid.value = ''
  }
}

function formatDay(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

/* 账号注销 */
const deleteOpen = ref(false)
const deleting = ref(false)
const deleteError = ref('')
const accountDeleted = ref(false)

const deleteDescription = computed(() =>
  auth.hasRoom
    ? '注销后账号会被停用，无法继续登录。你是房主时会自动解散寝室，其他成员会退出；进行中的组寝请求会关闭，联系方式会被清理。这个操作无法在页面内撤销。'
    : '注销后账号会被停用，无法继续登录；进行中的组寝请求会关闭，联系方式会被清理。这个操作无法在页面内撤销。',
)

async function confirmDelete(): Promise<void> {
  if (deleting.value) {
    return
  }
  deleting.value = true
  deleteError.value = ''
  try {
    await deleteMe()
    deleteOpen.value = false
    accountDeleted.value = true
    auth.clearSession()
  } catch (caught) {
    deleteError.value = apiErrorMessage(caught, '注销失败，请稍后重试。')
  } finally {
    deleting.value = false
  }
}

const logoutBusy = ref(false)

async function logout(): Promise<void> {
  if (logoutBusy.value) {
    return
  }
  logoutBusy.value = true
  try {
    await auth.logout()
    await router.push({ name: 'login' })
  } finally {
    logoutBusy.value = false
  }
}

onMounted(() => {
  fillFromUser()
  void loadBlocks()
})
</script>

<template>
  <section class="container settings-page">
    <template v-if="accountDeleted">
      <header class="page-head">
        <div>
          <p class="eyebrow">Settings</p>
          <h1>账号已注销</h1>
          <p class="lede">你的账号已经停用，当前设备上的登录状态也已清除。</p>
        </div>
      </header>
      <NoticeBar tone="info" title="还可以做什么">
        感谢你使用过 Cohabit 学生寝室匹配。如果之后想重新使用，需要联系管理员恢复账号。
      </NoticeBar>
      <RouterLink class="btn btn-primary" to="/">返回首页</RouterLink>
    </template>

    <template v-else>
      <header class="page-head">
        <div>
          <p class="eyebrow">Settings</p>
          <h1>设置</h1>
          <p class="lede">
            管理基础资料、联系方式与拉黑列表。联系方式只在双方同意后可见，通知和公开页面都不会出现你的 QQ、微信或手机号。
          </p>
        </div>
      </header>

      <section class="card settings-card" aria-labelledby="settings-basic-title">
        <div class="settings-head">
          <h2 id="settings-basic-title">基础资料</h2>
          <p class="fine">昵称、年级、学院和专业会展示在匹配卡片和公开摘要里。</p>
        </div>

        <form class="form-grid" novalidate @submit.prevent="saveProfile">
          <NoticeBar v-if="saveError" tone="error" title="资料没有保存成功">
            {{ saveError }}
          </NoticeBar>
          <NoticeBar v-else-if="savedNotice" tone="info" title="已保存">
            {{ savedNotice }}
          </NoticeBar>

          <div class="form-row">
            <label class="field" for="settings-nickname">
              <span>昵称</span>
              <input
                id="settings-nickname"
                v-model="form.nickname"
                name="nickname"
                type="text"
                maxlength="20"
                autocomplete="nickname"
                :aria-invalid="Boolean(issues.nickname)"
              />
              <p v-if="issues.nickname" class="field-error">{{ issues.nickname }}</p>
            </label>

            <div class="field">
              <label for="settings-grade">年级</label>
              <select
                id="settings-grade"
                v-model.number="form.grade"
                name="grade"
                :aria-invalid="Boolean(issues.grade)"
              >
                <option v-for="grade in GRADES" :key="grade.value" :value="grade.value">
                  {{ grade.label }}
                </option>
              </select>
              <p v-if="issues.grade" class="field-error">{{ issues.grade }}</p>
            </div>
          </div>

          <div class="form-row">
            <label class="field" for="settings-college">
              <span>学院</span>
              <input
                id="settings-college"
                v-model="form.college"
                name="college"
                type="text"
                maxlength="50"
                :aria-invalid="Boolean(issues.college)"
              />
              <p v-if="issues.college" class="field-error">{{ issues.college }}</p>
            </label>

            <label class="field" for="settings-major">
              <span>专业</span>
              <input
                id="settings-major"
                v-model="form.major"
                name="major"
                type="text"
                maxlength="50"
                :aria-invalid="Boolean(issues.major)"
              />
              <p v-if="issues.major" class="field-error">{{ issues.major }}</p>
            </label>
          </div>

          <div class="form-row readonly-row">
            <div class="field readonly-field">
              <span class="readonly-label">性别</span>
              <p class="readonly-value">{{ GENDER_LABELS[auth.user?.gender ?? ''] ?? '未填写' }}</p>
              <p class="fine">性别与寝室匹配相关，注册后不可修改。</p>
            </div>
            <div class="field readonly-field">
              <span class="readonly-label">邮箱</span>
              <p class="readonly-value">用于登录</p>
              <p class="fine">邮箱只用于登录与找回账号，不在这里展示，也不会出现在公开页面。</p>
            </div>
          </div>

          <div class="settings-actions">
            <p class="fine">修改后点击保存；邮箱和性别需要联系管理员处理。</p>
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? '保存中…' : '保存资料' }}
            </button>
          </div>
        </form>
      </section>

      <ContactPanel />

      <section class="card settings-card" aria-labelledby="settings-blocks-title">
        <div class="settings-head">
          <h2 id="settings-blocks-title">拉黑列表</h2>
          <p class="fine">
            拉黑后对方无法再邀请你，双方进行中的组寝请求会立即关闭；已经同住的寝室不受影响。
          </p>
        </div>

        <NoticeBar v-if="blocksNotice" tone="info">
          {{ blocksNotice }}
        </NoticeBar>

        <StateBlock v-if="blocksStatus === 'loading'" status="loading" :rows="1" />
        <StateBlock
          v-else-if="blocksStatus === 'error'"
          status="error"
          :message="blocksError"
          @retry="loadBlocks(true)"
        />
        <div v-else-if="!blocks.length" class="empty settings-empty">
          <p class="settings-empty-title">还没有拉黑任何人</p>
          <p class="fine">如果遇到骚扰或索要联系方式，可以在匹配详情、组寝请求或寝室成员里拉黑对方。</p>
        </div>
        <template v-else>
          <ul class="block-list">
            <li v-for="item in blocks" :key="item.uid" class="block-row">
              <AvatarBadge :name="item.nickname" size="sm" />
              <div class="block-body">
                <p class="block-name">{{ item.nickname }}</p>
                <p class="fine">拉黑于 {{ formatDay(item.created_at) }}</p>
              </div>
              <button
                type="button"
                class="btn btn-ghost btn-small"
                :disabled="unblockingUid === item.uid"
                @click="unblock(item)"
              >
                {{ unblockingUid === item.uid ? '解除中…' : '解除拉黑' }}
              </button>
            </li>
          </ul>
          <div class="settings-actions">
            <p class="fine">共 {{ blocksTotal }} 人</p>
            <button
              v-if="hasMoreBlocks"
              type="button"
              class="btn btn-ghost btn-small"
              :disabled="loadingMoreBlocks"
              @click="loadMoreBlocks"
            >
              {{ loadingMoreBlocks ? '加载中…' : '加载更多' }}
            </button>
          </div>
        </template>
      </section>

      <section class="card settings-card" aria-labelledby="settings-account-title">
        <div class="settings-head">
          <h2 id="settings-account-title">账号与安全</h2>
          <p class="fine">注销会停用账号并清理联系方式，且无法在页面内恢复。</p>
        </div>

        <dl class="account-meta">
          <div>
            <dt>账号 UID</dt>
            <dd>{{ auth.user?.uid ?? '—' }}</dd>
          </div>
          <div>
            <dt>身份</dt>
            <dd>{{ auth.user?.role === 'ADMIN' ? '管理员' : '学生' }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ auth.user?.status === 'ACTIVE' ? '正常' : '已停用' }}</dd>
          </div>
        </dl>

        <div class="link-list">
          <RouterLink class="settings-link" to="/rules">
            <span>社区规则</span>
            <span class="fine">查看举报、拉黑与组寝边界</span>
          </RouterLink>
          <RouterLink class="settings-link" to="/privacy">
            <span>隐私说明</span>
            <span class="fine">了解联系方式与通知的可见范围</span>
          </RouterLink>
        </div>

        <NoticeBar v-if="deleteError" tone="error" title="注销没有完成">
          {{ deleteError }}
        </NoticeBar>

        <div class="settings-actions danger-actions">
          <div>
            <p class="danger-title">注销账号</p>
            <p class="fine">停用账号、退出所有设备，并清理联系方式。</p>
          </div>
          <button
            type="button"
            class="btn btn-danger"
            :disabled="auth.isPreview"
            @click="deleteOpen = true; deleteError = ''"
          >
            注销账号
          </button>
        </div>
        <p v-if="auth.isPreview" class="fine">预览模式不能注销账号。</p>

        <div class="settings-actions">
          <p class="fine">退出登录会清除当前设备上的登录状态。</p>
          <button type="button" class="btn btn-ghost" :disabled="logoutBusy" @click="logout">
            {{ logoutBusy ? '退出中…' : '退出登录' }}
          </button>
        </div>
      </section>

      <ConfirmDialog
        :open="deleteOpen"
        title="确认注销账号"
        :description="deleteDescription"
        confirm-label="注销账号"
        confirm-word="注销"
        tone="danger"
        :busy="deleting"
        @confirm="confirmDelete"
        @cancel="deleteOpen = false"
      />
    </template>
  </section>
</template>

<style scoped>
.settings-page {
  display: grid;
  gap: 16px;
  padding-bottom: 48px;
}

.settings-page .page-head {
  margin-bottom: 0;
}

.settings-card {
  display: grid;
  gap: 14px;
  margin: 0;
}

.settings-head {
  display: grid;
  gap: 4px;
}

.settings-head h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
}

.settings-head .fine,
.settings-actions .fine {
  margin: 0;
}

.form-grid {
  display: grid;
  gap: 14px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.field {
  display: grid;
  gap: 6px;
}

.field > span,
.field > label {
  color: var(--muted);
  font-size: 12px;
}

.field input,
.field select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 11px 13px;
  background: var(--paper);
  color: var(--ink);
  font: inherit;
  font-size: 15px;
}

.field input:focus-visible,
.field select:focus-visible {
  border-color: var(--ink);
  outline: 2px solid var(--coral-dark);
  outline-offset: 2px;
}

.readonly-field {
  align-content: start;
  border: 1px dashed var(--line);
  border-radius: 12px;
  padding: 10px 13px;
  background: var(--sand);
}

.readonly-label {
  color: var(--muted);
  font-size: 12px;
}

.readonly-value {
  margin: 0;
  font-size: 15px;
}

.readonly-field .fine {
  margin: 0;
}

.settings-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}

.settings-actions .btn {
  min-height: 44px;
}

.settings-empty {
  display: grid;
  gap: 6px;
  justify-items: start;
}

.settings-empty-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 18px;
}

.block-list {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.block-row {
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--line);
  padding: 10px 0;
}

.block-row:last-child {
  border-bottom: 0;
}

.block-body {
  flex: 1;
  min-width: 0;
}

.block-name {
  margin: 0;
  overflow: hidden;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.block-body .fine {
  margin: 2px 0 0;
}

.account-meta {
  display: grid;
  gap: 8px;
  margin: 0;
}

.account-meta > div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px dashed var(--line);
  padding-bottom: 8px;
  font-size: 14px;
}

.account-meta dt {
  color: var(--muted);
}

.account-meta dd {
  margin: 0;
  overflow-wrap: anywhere;
  text-align: right;
}

.link-list {
  display: grid;
  gap: 8px;
}

.settings-link {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 4px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  color: var(--ink);
  text-decoration: none;
}

.settings-link:hover {
  border-color: var(--ink);
}

.danger-actions {
  border-top: 1px dashed var(--line);
}

.danger-title {
  margin: 0;
  color: var(--coral-dark);
  font-size: 15px;
}

.btn-danger {
  border: 1px solid var(--coral-dark);
  background: transparent;
  color: var(--coral-dark);
}

.btn-danger:hover:not(:disabled) {
  background: var(--coral-dark);
  color: var(--paper);
}

@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }

  .settings-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .settings-actions .btn {
    width: 100%;
  }

  .block-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .block-row .btn {
    width: 100%;
    min-height: 44px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .settings-link {
    transition: none;
  }
}
</style>
