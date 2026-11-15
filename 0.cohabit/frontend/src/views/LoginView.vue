<script setup lang="ts">
import { computed, reactive } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const showPreview = import.meta.env.VITE_ALLOW_PREVIEW === 'true'
const form = reactive({ email: '', password: '' })
const submitting = computed(() => auth.loading)

async function submit(): Promise<void> {
  try {
    await auth.login(form.email.trim(), form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/plaza'
    await router.push(redirect)
  } catch {
    // The store exposes a user-facing message.
  }
}

async function enterPreview(): Promise<void> {
  auth.startPreview()
  await router.push('/plaza')
}
</script>

<template>
  <div class="auth-wrap container">
    <div class="auth-card">
      <p class="eyebrow">Welcome back</p>
      <h1>登录 Cohabit</h1>
      <p class="lede">用校园邮箱登录。开发期验证码固定为 123456；正式环境会切换为邮件验证。</p>

      <form class="form-grid" @submit.prevent="submit">
        <div class="field">
          <label for="email">邮箱</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            autocomplete="email"
            placeholder="demo001@stu.edu.cn"
            required
          />
        </div>
        <div class="field">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            placeholder="至少 8 位"
            required
          />
        </div>

        <p v-if="auth.error" class="error-box" role="alert">{{ auth.error }}</p>

        <button class="btn btn-primary" type="submit" :disabled="submitting">
          {{ submitting ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="fine" style="margin-top: 16px">
        还没有账号？注册入口将在后端认证接口接入后开放。
        <RouterLink to="/" style="text-decoration: underline">先回首页</RouterLink>
      </p>

      <div v-if="showPreview" class="preview-note">
        <p style="margin: 0 0 10px">后端未启动时，可进入前端预览模式查看页面框架；预览不写入数据。</p>
        <button class="btn btn-small btn-ghost" type="button" @click="enterPreview">
          前端预览模式
        </button>
      </div>
    </div>
  </div>
</template>
