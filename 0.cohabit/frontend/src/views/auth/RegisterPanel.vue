<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorCode, apiErrorMessage } from '@/api/client'
import { useAuthStore, type Gender } from '@/stores/auth'
import { resolveAuthRedirect } from '@/router/redirect'
import { isEmailLike, toFieldErrors, validationSummary } from '@/views/auth/form'

const props = defineProps<{ active: boolean }>()
const emit = defineEmits<{
  (event: 'switch', mode: 'login'): void
}>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({
  email: '',
  code: '',
  password: '',
  nickname: '',
  gender: 'MALE' as Gender,
  grade: 1,
  college: '',
  major: '',
  invite_code: '',
})

const fieldErrors = ref<Record<string, string>>({})
const formError = ref('')
const submitting = ref(false)
const sending = ref(false)
const countdown = ref(0)
const codeNotice = ref('')
const devCodeHint = ref('')
const emailTaken = ref(false)
const emailInput = ref<HTMLInputElement | null>(null)

const sendLabel = computed(() => {
  if (sending.value) {
    return '发送中…'
  }
  if (countdown.value > 0) {
    return `${countdown.value}s 后重发`
  }
  return '发送验证码'
})

let timer: ReturnType<typeof setInterval> | null = null

function stopTimer(): void {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

function startCountdown(seconds = 60): void {
  stopTimer()
  countdown.value = seconds
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      countdown.value = 0
      stopTimer()
    }
  }, 1000)
}

onUnmounted(stopTimer)

function focusEmail(): void {
  void nextTick(() => emailInput.value?.focus())
}

onMounted(() => {
  if (props.active) {
    focusEmail()
  }
})

watch(
  () => props.active,
  (active) => {
    if (active) {
      focusEmail()
    }
  },
)

function applyServerError(caught: unknown): void {
  const code = apiErrorCode(caught)
  if (code === 'VALIDATION_ERROR') {
    fieldErrors.value = { ...fieldErrors.value, ...toFieldErrors(caught) }
    formError.value = validationSummary(fieldErrors.value)
    return
  }
  if (code === 'EMAIL_TAKEN') {
    const message = '这个邮箱已经注册过了，直接登录？'
    fieldErrors.value = { ...fieldErrors.value, email: message }
    emailTaken.value = true
    formError.value = message
    return
  }
  if (code === 'INVITE_INVALID' || code === 'INVITE_REQUIRED') {
    const message = apiErrorMessage(caught)
    fieldErrors.value = { ...fieldErrors.value, invite_code: message }
    formError.value = message
    return
  }
  if (code === 'CODE_INVALID' || code === 'CODE_EXPIRED') {
    const message = apiErrorMessage(caught)
    fieldErrors.value = { ...fieldErrors.value, code: message }
    formError.value = message
    return
  }
  formError.value = apiErrorMessage(caught)
}

async function sendCode(): Promise<void> {
  formError.value = ''
  codeNotice.value = ''
  devCodeHint.value = ''
  const email = form.email.trim()
  if (!isEmailLike(email)) {
    fieldErrors.value = { ...fieldErrors.value, email: '请输入校园邮箱，例如 name@stu.edu.cn。' }
    return
  }
  sending.value = true
  try {
    const devCode = await auth.sendCode(email)
    if (devCode) {
      devCodeHint.value = `开发环境验证码：${devCode}（不会自动填入）`
    } else {
      codeNotice.value = '验证码已发送，请查收邮箱，10 分钟内有效。'
    }
    startCountdown()
  } catch (caught) {
    applyServerError(caught)
  } finally {
    sending.value = false
  }
}

async function submit(): Promise<void> {
  formError.value = ''
  fieldErrors.value = {}
  emailTaken.value = false

  const email = form.email.trim()
  const nickname = form.nickname.trim()
  const college = form.college.trim()
  const major = form.major.trim()
  const invite = form.invite_code.trim()
  const errors: Record<string, string> = {}

  if (!isEmailLike(email)) {
    errors.email = '请输入校园邮箱，例如 name@stu.edu.cn。'
  }
  if (!/^\d{6}$/.test(form.code.trim())) {
    errors.code = '请输入 6 位数字验证码。'
  }
  if (form.password.length < 8) {
    errors.password = '密码至少 8 位。'
  } else if (form.password.length > 64) {
    errors.password = '密码最多 64 位。'
  }
  if (!nickname) {
    errors.nickname = '请填写昵称。'
  } else if (nickname.length > 20) {
    errors.nickname = '昵称最多 20 个字。'
  }
  if (!college) {
    errors.college = '请填写学院。'
  } else if (college.length > 50) {
    errors.college = '学院最多 50 个字。'
  }
  if (!Number.isInteger(form.grade) || form.grade < 1 || form.grade > 5) {
    errors.grade = '请选择年级。'
  }

  if (Object.keys(errors).length > 0) {
    fieldErrors.value = errors
    formError.value = validationSummary(errors)
    return
  }

  submitting.value = true
  try {
    await auth.register({
      email,
      code: form.code.trim(),
      password: form.password,
      nickname,
      gender: form.gender,
      grade: form.grade,
      college,
      major,
      invite_code: invite,
    })
    await router.push(resolveAuthRedirect(auth, route.query.redirect))
  } catch (caught) {
    applyServerError(caught)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form-grid" :aria-busy="submitting" @submit.prevent="submit">
    <p v-if="formError" class="error-box" role="alert">{{ formError }}</p>

    <div class="field">
      <label for="reg-email">校园邮箱</label>
      <div class="code-row">
        <input
          id="reg-email"
          ref="emailInput"
          v-model.trim="form.email"
          type="email"
          name="email"
          autocomplete="email"
          inputmode="email"
          placeholder="name@stu.edu.cn"
          required
          :aria-invalid="Boolean(fieldErrors.email)"
          :aria-describedby="fieldErrors.email ? 'reg-email-error' : undefined"
        />
        <button
          class="btn btn-ghost btn-small"
          type="button"
          :disabled="sending || countdown > 0"
          @click="sendCode"
        >
          {{ sendLabel }}
        </button>
      </div>
      <p v-if="fieldErrors.email" id="reg-email-error" class="field-error">
        {{ fieldErrors.email }}
      </p>
      <button
        v-if="emailTaken"
        class="link-button"
        type="button"
        @click="emit('switch', 'login')"
      >
        直接登录
      </button>
      <p v-if="devCodeHint" class="fine dev-hint" role="status">{{ devCodeHint }}</p>
      <p v-else-if="codeNotice" class="fine" role="status">{{ codeNotice }}</p>
    </div>

    <div class="field">
      <label for="reg-code">验证码</label>
      <input
        id="reg-code"
        v-model.trim="form.code"
        type="text"
        name="one-time-code"
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        placeholder="6 位数字"
        required
        :aria-invalid="Boolean(fieldErrors.code)"
        :aria-describedby="fieldErrors.code ? 'reg-code-error' : undefined"
      />
      <p v-if="fieldErrors.code" id="reg-code-error" class="field-error">
        {{ fieldErrors.code }}
      </p>
    </div>

    <div class="field">
      <label for="reg-password">密码</label>
      <input
        id="reg-password"
        v-model="form.password"
        type="password"
        name="new-password"
        autocomplete="new-password"
        placeholder="8–64 位，避免纯数字或常见密码"
        required
        :aria-invalid="Boolean(fieldErrors.password)"
        :aria-describedby="fieldErrors.password ? 'reg-password-error' : undefined"
      />
      <p v-if="fieldErrors.password" id="reg-password-error" class="field-error">
        {{ fieldErrors.password }}
      </p>
    </div>

    <div class="form-row">
      <div class="field">
        <label for="reg-nickname">昵称</label>
        <input
          id="reg-nickname"
          v-model.trim="form.nickname"
          type="text"
          name="nickname"
          autocomplete="nickname"
          maxlength="20"
          placeholder="别人怎么称呼你"
          required
          :aria-invalid="Boolean(fieldErrors.nickname)"
          :aria-describedby="fieldErrors.nickname ? 'reg-nickname-error' : undefined"
        />
        <p v-if="fieldErrors.nickname" id="reg-nickname-error" class="field-error">
          {{ fieldErrors.nickname }}
        </p>
      </div>

      <div class="field">
        <label for="reg-grade">年级</label>
        <select id="reg-grade" v-model.number="form.grade" name="grade" required>
          <option :value="1">大一</option>
          <option :value="2">大二</option>
          <option :value="3">大三</option>
          <option :value="4">大四</option>
          <option :value="5">大五</option>
        </select>
        <p v-if="fieldErrors.grade" class="field-error">{{ fieldErrors.grade }}</p>
      </div>
    </div>

    <fieldset class="field choice-field">
      <legend class="field-legend">性别</legend>
      <div class="choice-group">
        <label class="choice" :class="{ selected: form.gender === 'MALE' }">
          <input v-model="form.gender" type="radio" name="gender" value="MALE" />
          <span>男</span>
        </label>
        <label class="choice" :class="{ selected: form.gender === 'FEMALE' }">
          <input v-model="form.gender" type="radio" name="gender" value="FEMALE" />
          <span>女</span>
        </label>
      </div>
      <p class="fine">为了同性别组寝，注册后不能修改。</p>
    </fieldset>

    <div class="form-row">
      <div class="field">
        <label for="reg-college">学院</label>
        <input
          id="reg-college"
          v-model.trim="form.college"
          type="text"
          name="organization"
          autocomplete="organization"
          maxlength="50"
          placeholder="计算机学院"
          required
          :aria-invalid="Boolean(fieldErrors.college)"
          :aria-describedby="fieldErrors.college ? 'reg-college-error' : undefined"
        />
        <p v-if="fieldErrors.college" id="reg-college-error" class="field-error">
          {{ fieldErrors.college }}
        </p>
      </div>

      <div class="field">
        <label for="reg-major">专业（选填）</label>
        <input
          id="reg-major"
          v-model.trim="form.major"
          type="text"
          name="major"
          maxlength="50"
          placeholder="软件工程"
        />
      </div>
    </div>

    <div class="field">
      <label for="reg-invite">邀请码（如有）</label>
      <input
        id="reg-invite"
        v-model.trim="form.invite_code"
        type="text"
        name="invite-code"
        autocomplete="off"
        maxlength="12"
        placeholder="没有可留空"
        :aria-invalid="Boolean(fieldErrors.invite_code)"
        :aria-describedby="fieldErrors.invite_code ? 'reg-invite-error' : undefined"
      />
      <p v-if="fieldErrors.invite_code" id="reg-invite-error" class="field-error">
        {{ fieldErrors.invite_code }}
      </p>
    </div>

    <button class="btn btn-primary btn-block" type="submit" :disabled="submitting">
      {{ submitting ? '正在创建账号…' : '用校园邮箱开始' }}
    </button>

    <p class="fine">
      资料只用于同学院、同性别的舍友匹配；联系方式默认不可见，双方同意后才展示。
    </p>
  </form>

  <p class="fine auth-switch">
    已有账号？
    <button class="link-button" type="button" @click="emit('switch', 'login')">直接登录</button>
  </p>
</template>
