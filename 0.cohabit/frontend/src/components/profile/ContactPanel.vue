<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { apiErrorFields, apiErrorMessage } from '@/api/client'
import {
  fetchContact,
  saveContact,
  type ContactInfo,
  type ContactPatch,
} from '@/api/profiles'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'

/**
 * 我的联系方式（docs/05 §7.2「联系方式单独区块（仅本人可见）」）。
 *
 * - 只读取 `GET /api/me/contact`，只写入 `PUT /api/me/contact`；
 * - 页面上永远脱敏展示，勾选的字段只有在连接解锁后才会给对方看；
 * - 本组件只出现在自己的 /profile，公开用户接口不返回任何联系方式。
 */

const status = ref<'loading' | 'ready' | 'error'>('loading')
const loadError = ref('')
const contact = ref<ContactInfo | null>(null)
const editing = ref(false)
const saving = ref(false)
const savedNotice = ref('')
const formError = ref('')

const form = reactive({
  qq: '',
  wechat: '',
  phone: '',
  show_qq: true,
  show_wechat: true,
  show_phone: true,
})

const issues = reactive<Record<string, string>>({})

const QQ_RE = /^\d{5,12}$/
const PHONE_RE = /^1[3-9]\d{9}$/

function resetForm(next: ContactInfo | null): void {
  form.qq = next?.qq ?? ''
  form.wechat = next?.wechat ?? ''
  form.phone = next?.phone ?? ''
  form.show_qq = next?.show_qq ?? true
  form.show_wechat = next?.show_wechat ?? true
  form.show_phone = next?.show_phone ?? true
}

function clearIssues(): void {
  for (const key of Object.keys(issues)) {
    delete issues[key]
  }
}

async function load(): Promise<void> {
  status.value = 'loading'
  loadError.value = ''
  try {
    const payload = await fetchContact()
    contact.value = payload
    resetForm(payload)
    status.value = 'ready'
  } catch (error) {
    status.value = 'error'
    loadError.value = apiErrorMessage(error, '联系方式加载失败，请稍后重试。')
  }
}

function startEdit(): void {
  resetForm(contact.value)
  clearIssues()
  formError.value = ''
  savedNotice.value = ''
  editing.value = true
}

function cancelEdit(): void {
  editing.value = false
  clearIssues()
  formError.value = ''
}

function mask(value: string | null, kind: 'qq' | 'wechat' | 'phone'): string {
  if (!value) {
    return '未填写'
  }
  if (kind === 'phone' && value.length >= 7) {
    return `${value.slice(0, 3)}****${value.slice(-4)}`
  }
  if (kind === 'qq' && value.length >= 5) {
    return `${value.slice(0, 2)}${'*'.repeat(Math.max(value.length - 4, 3))}${value.slice(-2)}`
  }
  if (kind === 'wechat') {
    return `${value.slice(0, 2)}***`
  }
  return value
}

function rows(): {
  key: 'qq' | 'wechat' | 'phone'
  label: string
  value: string
  has: boolean
  shown: boolean
}[] {
  const current = contact.value
  return [
    {
      key: 'qq',
      label: 'QQ',
      value: mask(current?.qq ?? null, 'qq'),
      has: Boolean(current?.qq),
      shown: current?.show_qq ?? false,
    },
    {
      key: 'wechat',
      label: '微信',
      value: mask(current?.wechat ?? null, 'wechat'),
      has: Boolean(current?.wechat),
      shown: current?.show_wechat ?? false,
    },
    {
      key: 'phone',
      label: '手机号',
      value: mask(current?.phone ?? null, 'phone'),
      has: Boolean(current?.phone),
      shown: current?.show_phone ?? false,
    },
  ]
}

function collect(): ContactPatch | null {
  clearIssues()
  formError.value = ''
  const qq = form.qq.trim()
  const wechat = form.wechat.trim()
  const phone = form.phone.trim()
  if (qq && !QQ_RE.test(qq)) {
    issues.qq = 'QQ 必须是 5–12 位数字。'
  }
  if (wechat.length > 40) {
    issues.wechat = '微信最多 40 个字符。'
  }
  if (phone && !PHONE_RE.test(phone)) {
    issues.phone = '手机号必须是 11 位中国大陆号码。'
  }
  if (Object.keys(issues).length) {
    return null
  }
  return {
    qq: qq || null,
    wechat: wechat || null,
    phone: phone || null,
    show_qq: form.show_qq,
    show_wechat: form.show_wechat,
    show_phone: form.show_phone,
  }
}

async function submit(): Promise<void> {
  if (saving.value) {
    return
  }
  const patch = collect()
  if (!patch) {
    return
  }
  saving.value = true
  try {
    contact.value = await saveContact(patch)
    resetForm(contact.value)
    editing.value = false
    savedNotice.value =
      '联系方式已保存。仅本人可见；双方都同意解锁后，才会向对方展示勾选的字段。'
  } catch (error) {
    const fields = apiErrorFields(error)
    let mapped = 0
    for (const key of ['qq', 'wechat', 'phone']) {
      const text = fields[key]?.[0]
      if (text) {
        issues[key] = text
        mapped += 1
      }
    }
    if (!mapped) {
      formError.value = apiErrorMessage(error, '保存失败，请稍后重试。')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="contact-panel" aria-labelledby="contact-title">
    <div class="contact-head">
      <h2 id="contact-title">联系方式</h2>
      <span class="chip">仅本人可见</span>
    </div>
    <p class="fine contact-note">
      这里填写的联系方式只有你自己能看到；双方都同意解锁后，才会向对方展示你勾选的字段。
    </p>

    <StateBlock v-if="status === 'loading'" status="loading" :rows="1" />
    <StateBlock
      v-else-if="status === 'error'"
      status="error"
      :message="loadError"
      @retry="load"
    />

    <template v-else>
      <NoticeBar v-if="savedNotice" tone="info">{{ savedNotice }}</NoticeBar>
      <NoticeBar v-if="formError" tone="error">{{ formError }}</NoticeBar>

      <dl v-if="!editing" class="contact-list">
        <div v-for="row in rows()" :key="row.key" class="contact-row">
          <dt>{{ row.label }}</dt>
          <dd>
            <span class="contact-value">{{ row.value }}</span>
            <span v-if="row.has" class="contact-flag" :class="{ 'is-shown': row.shown }">
              {{ row.shown ? '解锁后展示' : '不展示' }}
            </span>
          </dd>
        </div>
      </dl>

      <div class="contact-actions">
        <button
          v-if="!editing"
          class="btn btn-small btn-ghost"
          type="button"
          @click="startEdit"
        >
          编辑联系方式
        </button>
      </div>

      <form v-if="editing" class="form-grid contact-form" @submit.prevent="submit">
        <p class="fine contact-note">
          填写后保存；留空表示不填写，保存时会把该项清空。这些内容不会出现在公开画像里。
        </p>
        <div class="form-row">
          <div class="field contact-field">
            <label for="contact-qq">QQ</label>
            <input
              id="contact-qq"
              v-model.trim="form.qq"
              type="text"
              inputmode="numeric"
              autocomplete="off"
              placeholder="5–12 位数字"
              :aria-invalid="Boolean(issues.qq)"
            />
            <span v-if="issues.qq" class="field-error">{{ issues.qq }}</span>
            <label class="contact-toggle">
              <input v-model="form.show_qq" type="checkbox" />
              <span>解锁后向对方展示 QQ</span>
            </label>
          </div>
          <div class="field contact-field">
            <label for="contact-wechat">微信</label>
            <input
              id="contact-wechat"
              v-model.trim="form.wechat"
              type="text"
              autocomplete="off"
              placeholder="微信号，最多 40 字"
              :aria-invalid="Boolean(issues.wechat)"
            />
            <span v-if="issues.wechat" class="field-error">{{ issues.wechat }}</span>
            <label class="contact-toggle">
              <input v-model="form.show_wechat" type="checkbox" />
              <span>解锁后向对方展示微信</span>
            </label>
          </div>
        </div>
        <div class="field contact-field">
          <label for="contact-phone">手机号</label>
          <input
            id="contact-phone"
            v-model.trim="form.phone"
            type="tel"
            inputmode="numeric"
            autocomplete="off"
            placeholder="11 位中国大陆号码"
            :aria-invalid="Boolean(issues.phone)"
          />
          <span v-if="issues.phone" class="field-error">{{ issues.phone }}</span>
          <label class="contact-toggle">
            <input v-model="form.show_phone" type="checkbox" />
            <span>解锁后向对方展示手机号</span>
          </label>
        </div>
        <div class="contact-actions">
          <button class="btn btn-small btn-primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存联系方式' }}
          </button>
          <button class="btn btn-small btn-ghost" type="button" :disabled="saving" @click="cancelEdit">
            取消
          </button>
        </div>
      </form>
    </template>
  </section>
</template>

<style scoped>
.contact-panel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 20px;
  background: var(--paper);
}

.contact-head {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.contact-head h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
}

.contact-note {
  margin: 0;
  color: var(--muted);
}

.contact-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.contact-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px dashed var(--line);
  padding-bottom: 8px;
}

.contact-row:last-child {
  border-bottom: 0;
}

.contact-row dt {
  font-size: 12px;
  color: var(--muted);
}

.contact-row dd {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
  margin: 0;
}

.contact-value {
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums;
}

.contact-flag {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--muted);
}

.contact-flag.is-shown {
  border-color: color-mix(in srgb, var(--coral) 55%, transparent);
  color: var(--coral-dark);
}

.contact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.contact-field {
  width: 100%;
}

.contact-toggle {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--muted);
  min-height: 44px;
}

.contact-toggle input {
  width: 16px;
  height: 16px;
  accent-color: var(--coral);
}

@media (max-width: 640px) {
  .contact-panel {
    padding: 16px;
  }

  .contact-actions .btn {
    flex: 1;
  }
}
</style>
