<script setup lang="ts">
/**
 * 404 兜底页：统一说明 + 三个出口（首页 / 广场 / 上一页）+ 当前地址回显。
 * 中文标题按 docs/05 §2.2 保持 0 字距，长地址可断行，移动端不横向溢出。
 */
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const attemptedPath = computed(() => route.fullPath || route.path || '/')

function goBack() {
  // 直接打开链接时 history 里没有上一页，退化成去广场。
  if (window.history.length > 1) router.back()
  else void router.push({ name: 'plaza' })
}
</script>

<template>
  <section class="container not-found" aria-labelledby="not-found-title">
    <p class="eyebrow">404 · 页面不存在</p>
    <h1 id="not-found-title" class="not-found-title">走错门了。</h1>
    <p class="lede not-found-lede">
      这个页面不存在，或者对应寝室已经被归档、解散。<br />
      可能是地址打错了，也可能是链接已经过期。
    </p>

    <p class="not-found-path">
      <span class="not-found-label">你访问的地址</span>
      <code>{{ attemptedPath }}</code>
    </p>

    <div class="not-found-actions">
      <RouterLink class="btn btn-primary" to="/">回到首页</RouterLink>
      <RouterLink class="btn btn-ghost" to="/plaza">去寝室广场</RouterLink>
      <button type="button" class="btn btn-ghost" @click="goBack">返回上一页</button>
    </div>

    <p class="fine not-found-help">
      还在找自己的寝室？在<RouterLink to="/rooms">我的寝室</RouterLink>里可以重新进入；<br />
      如果链接来自学院通知，可以联系学院管理员确认是否仍然有效。
    </p>
  </section>
</template>

<style scoped>
.not-found {
  max-width: 760px;
  margin-inline: auto;
  padding: 88px 0 72px;
}

.not-found-title {
  margin: 10px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(40px, 8vw, 76px);
  font-weight: 500;
  letter-spacing: 0;
  line-height: 1.02;
}

.not-found-lede {
  margin-top: 16px;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.7;
}

.not-found-path {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 10px;
  margin: 24px 0 0;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: color-mix(in srgb, var(--sand) 45%, transparent);
  font-size: 13px;
}

.not-found-label {
  color: var(--muted);
}

.not-found-path code {
  min-width: 0;
  font-family: var(--font-sans);
  overflow-wrap: anywhere;
}

.not-found-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.not-found-help {
  margin-top: 36px;
  line-height: 1.8;
}

.not-found-help a {
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
}

@media (max-width: 640px) {
  .not-found {
    padding: 64px 0 56px;
  }

  .not-found-actions .btn {
    flex: 1 1 100%;
    justify-content: center;
  }
}
</style>
