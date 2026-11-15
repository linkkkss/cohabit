<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiErrorCode, apiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { resolveAuthRedirect } from '@/router/redirect'
import { toFieldErrors, validationSummary } from '@/views/auth/form'

const props = defineProps<{ active: boolean }>()
const emit = defineEmits<{
  (event: 'switch', mode: 'register'): void
}>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({ email: '', password: '' })
const fieldErrors = ref<Record<string, string>>({})
const formError = ref('')
const submitting = ref(false)
const emailInput = ref<HTMLInputElement | null>(null)

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

async function submit(): Promise<void> {
  formError.value = ''
  fieldErrors.value = {}
  submitting.value = true
  try {
    await auth.login(form.email.trim(), form.password)
    await router.push(resolveAuthRedirect(auth, route.query.redirect))
  } catch (caught) {
    if (apiErrorCode(caught) === 'VALIDATION_ERROR') {
      fieldErrors.value = toFieldErrors(caught)
      formError.value = validationSummary(fieldErrors.value)
    } else {
      formError.value = apiErrorMessage(caught)
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="form-grid" :aria-busy="submitting" @submit.prevent="submit">
    <p v-if="auth.sessionExpired" class="auth-notice" role="status">登录已过期，请重新登录。</p>

    <div class="field">
      <label for="login-email">邮箱</label>
      <input
        id="login-email"
        ref="emailInput"
        v-model.trim="form.email"
        type="email"
        name="email"
        autocomplete="email"
        inputmode="email"
        placeholder="name@stu.edu.cn"
        required
        :aria-invalid="Boolean(fieldErrors.email)"
        :aria-describedby="fieldErrors.email ? 'login-email-error' : undefined"
      />
      <p v-if="fieldErrors.email" id="login-email-error" class="field-error">
        {{ fieldErrors.email }}
      </p>
    </div>

    <div class="field">
      <label for="login-password">密码</label>
      <input
        id="login-password"
        v-model="form.password"
        type="password"
        name="password"
        autocomplete="current-password"
        placeholder="至少 8 位"
        required
        :aria-invalid="Boolean(fieldErrors.password)"
        :aria-describedby="fieldErrors.password ? 'login-password-error' : undefined"
      />
      <p v-if="fieldErrors.password" id="login-password-error" class="field-error">
        {{ fieldErrors.password }}
      </p>
    </div>

    <p v-if="formError" class="error-box" role="alert">{{ formError }}</p>

    <button class="btn btn-primary btn-block" type="submit" :disabled="submitting">
      {{ submitting ? '登录中…' : '登录' }}
    </button>
  </form>

  <p class="fine auth-switch">
    还没有账号？
    <button class="link-button" type="button" @click="emit('switch', 'register')">
      用校园邮箱注册
    </button>
  </p>
</template>
