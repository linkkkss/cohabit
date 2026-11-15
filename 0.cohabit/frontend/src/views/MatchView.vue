<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const demoCandidates = [
  {
    name: '林同学',
    meta: '计算机学院 · 大二 · 4 人寝',
    score: 92,
    tags: ['早睡', '安静', '整洁'],
  },
  {
    name: '周同学',
    meta: '外国语学院 · 大一 · 6 人寝',
    score: 88,
    tags: ['有边界', '周末做饭', '不吸烟'],
  },
  {
    name: '陈同学',
    meta: '计算机学院 · 大三 · 2 人寝',
    score: 84,
    tags: ['夜猫子', '游戏', '爱干净'],
  },
]
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Match</p>
        <h1>可能合拍的人</h1>
        <p>按六维契合度排序，红线冲突会封顶 59 分。候选仅限同学院、同性别、画像完整且无在途请求。</p>
      </div>
      <div class="filter-row">
        <span class="chip">本学院</span>
        <span class="chip">同性别</span>
        <span class="chip">画像 100%</span>
      </div>
    </header>

    <div class="toolbar">
      <p class="fine" style="margin: 0">
        当前为前端框架示意数据；匹配接口接入后替换为真实候选与推荐理由。
      </p>
      <button class="btn btn-small btn-primary" type="button" disabled>开始匹配（待接入）</button>
    </div>

    <div v-if="demoCandidates.length" class="candidate-grid">
      <article v-for="candidate in demoCandidates" :key="candidate.name" class="candidate-card">
        <div class="candidate-top">
          <div class="avatar avatar-lg">{{ candidate.name.slice(0, 1) }}</div>
          <div class="score">{{ candidate.score }}</div>
        </div>
        <h2 class="candidate-name">{{ candidate.name }}</h2>
        <p class="candidate-meta">{{ candidate.meta }}</p>
        <div class="tag-list">
          <span v-for="tag in candidate.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
        <div style="display: flex; gap: 8px; margin-top: 18px">
          <button class="btn btn-small btn-ghost" type="button" disabled>查看画像</button>
          <button class="btn btn-small btn-primary" type="button" disabled>发起邀请</button>
        </div>
      </article>
    </div>

    <div v-else class="empty">
      <strong>还没有候选</strong>
      完成画像后，匹配结果会出现在这里。
    </div>

    <p class="fine" style="margin-top: 20px">
      <RouterLink to="/onboarding" style="text-decoration: underline">先去完善画像</RouterLink>
      <span v-if="auth.isPreview"> · 当前为预览模式</span>
    </p>
  </div>
</template>
