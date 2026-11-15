<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ALLOW_PREVIEW, useAuthStore } from '@/stores/auth'
import { resolveAuthRedirect } from '@/router/redirect'
import LoginPanel from '@/views/auth/LoginPanel.vue'
import RegisterPanel from '@/views/auth/RegisterPanel.vue'

type Mode = 'login' | 'register'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const mode = ref<Mode>('login')
const showPreview = ALLOW_PREVIEW

function selectMode(next: Mode): void {
  mode.value = next
}

function onTabKeydown(event: KeyboardEvent, current: Mode): void {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
    return
  }
  event.preventDefault()
  const next: Mode = current === 'login' ? 'register' : 'login'
  selectMode(next)
  void nextTick(() => {
    document.getElementById(next === 'login' ? 'auth-tab-login' : 'auth-tab-register')?.focus()
  })
}

async function enterPreview(): Promise<void> {
  auth.startPreview()
  await router.push(resolveAuthRedirect(auth, route.query.redirect))
}
</script>

<template>
  <div class="auth-wrap container">
    <div class="auth-card">
      <p class="eyebrow">{{ mode === 'login' ? 'Welcome back' : 'Join Cohabit' }}</p>
      <h1>{{ mode === 'login' ? '登录 Cohabit' : '用校园邮箱开始' }}</h1>
      <p class="lede">
        {{
          mode === 'login'
            ? '用校园邮箱登录；登录状态只保存在当前页面的内存里，刷新后会自动恢复。'
            : '先留下基本资料；注册完成后，用两三分钟把你的“住法”说清楚。'
        }}
      </p>

      <div class="tabs auth-tabs" role="tablist" aria-label="登录或注册">
        <button
          id="auth-tab-login"
          class="tab"
          :class="{ active: mode === 'login' }"
          type="button"
          role="tab"
          :aria-selected="mode === 'login'"
          aria-controls="auth-panel-login"
          :tabindex="mode === 'login' ? 0 : -1"
          @click="selectMode('login')"
          @keydown="onTabKeydown($event, 'login')"
        >
          登录
        </button>
        <button
          id="auth-tab-register"
          class="tab"
          :class="{ active: mode === 'register' }"
          type="button"
          role="tab"
          :aria-selected="mode === 'register'"
          aria-controls="auth-panel-register"
          :tabindex="mode === 'register' ? 0 : -1"
          @click="selectMode('register')"
          @keydown="onTabKeydown($event, 'register')"
        >
          注册
        </button>
      </div>

      <div
        id="auth-panel-login"
        role="tabpanel"
        aria-labelledby="auth-tab-login"
        v-show="mode === 'login'"
      >
        <LoginPanel :active="mode === 'login'" @switch="selectMode" />
      </div>

      <div
        id="auth-panel-register"
        role="tabpanel"
        aria-labelledby="auth-tab-register"
        v-show="mode === 'register'"
      >
        <RegisterPanel :active="mode === 'register'" @switch="selectMode" />
      </div>

      <p class="fine auth-home-link">
        <RouterLink to="/">先回首页看看</RouterLink>
      </p>

      <div v-if="showPreview" class="preview-note">
        <p class="preview-copy">
          后端未启动时，可进入前端预览模式查看页面框架；预览不写入数据，也不会保存登录状态。
        </p>
        <button class="btn btn-small btn-ghost" type="button" @click="enterPreview">
          前端预览模式
        </button>
      </div>
    </div>
  </div>
</template>
