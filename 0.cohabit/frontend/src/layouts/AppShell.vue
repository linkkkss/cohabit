<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const navItems = [
  { to: '/plaza', label: '广场' },
  { to: '/match', label: '匹配' },
  { to: '/connections', label: '请求' },
  { to: '/rooms', label: '寝室' },
] as const

const userLabel = computed(() => auth.user?.nickname || '我的')

function signOut(): void {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="container header-inner">
        <RouterLink class="brand" to="/" aria-label="Cohabit 首页">
          <span class="brand-mark">C</span>
          <span class="brand-name">Cohabit</span>
        </RouterLink>

        <nav class="primary-nav" aria-label="主导航">
          <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="header-actions">
          <template v-if="auth.isAuthenticated">
            <span v-if="auth.isPreview" class="chip chip-warn">预览模式</span>
            <RouterLink class="nav-link user-link" to="/profile">{{ userLabel }}</RouterLink>
            <button class="btn btn-small btn-ghost" type="button" @click="signOut">退出</button>
          </template>
          <template v-else>
            <RouterLink class="btn btn-small btn-primary" to="/login">登录</RouterLink>
          </template>
        </div>
      </div>
    </header>

    <main class="site-main">
      <RouterView />
    </main>

    <footer class="site-footer">
      <div class="container footer-inner">
        <span>Cohabit · 校园舍友匹配</span>
        <span class="muted">仅限同学院、同性别；联系方式在双方同意后可见。</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
}

.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--paper) 92%, transparent);
  backdrop-filter: blur(12px);
}

.header-inner {
  display: flex;
  min-height: 72px;
  align-items: center;
  gap: 28px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-serif);
  font-size: 22px;
  letter-spacing: -0.02em;
}

.brand-mark {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 700;
}

.brand-name {
  font-weight: 600;
}

.primary-nav {
  display: flex;
  flex: 1;
  gap: 20px;
}

.nav-link {
  color: var(--muted);
  font-size: 14px;
  transition: color 160ms ease;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: var(--ink);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-link {
  font-weight: 600;
}

.chip-warn {
  border-color: #e8c9a8;
  background: #fbf1e6;
  color: #8a5a2b;
}

.site-main {
  flex: 1;
}

.site-footer {
  border-top: 1px solid var(--line);
  padding: 28px 0;
  color: var(--muted);
  font-size: 13px;
}

.footer-inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px 24px;
}

@media (max-width: 820px) {
  .header-inner {
    flex-wrap: wrap;
    min-height: 64px;
    gap: 12px 20px;
    padding: 12px 0;
  }

  .primary-nav {
    order: 3;
    flex-basis: 100%;
    justify-content: space-between;
    gap: 8px;
  }

  .header-actions {
    margin-left: auto;
  }
}
</style>
