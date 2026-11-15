<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const roomCode = computed(() => String(route.params.code ?? ''))

const members = [
  { name: '林同学', role: '房主', meta: '计算机学院 · 早睡' },
  { name: '周同学', role: '成员', meta: '计算机学院 · 整洁' },
  { name: '陈同学', role: '成员', meta: '计算机学院 · 安静' },
]
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Room #{{ roomCode }}</p>
        <h1>寝室详情</h1>
        <p>容量 2/4/6 成立后不可变；满员不可扩容。公开页只展示有限字段，成员/联系方式仅对成员可见。</p>
      </div>
      <RouterLink class="btn btn-ghost" to="/rooms">返回我的寝室</RouterLink>
    </header>

    <div class="profile-grid">
      <section class="profile-card">
        <div class="room-top">
          <span class="status status-recruiting">招募中</span>
          <span class="fine">3 / 4 · 1 个空位</span>
        </div>
        <h2 style="margin: 18px 0 4px; font-family: var(--font-serif); font-size: 30px; font-weight: 500">
          计算机学院 · 4 人寝
        </h2>
        <p class="muted" style="margin-top: 0">#{{ roomCode }} · 房主：林同学 · 创建于 2026-11-15</p>

        <div class="tag-list">
          <span class="tag">早睡</span>
          <span class="tag">安静</span>
          <span class="tag">整洁</span>
        </div>

        <h3 style="margin: 26px 0 12px; font-size: 15px">成员</h3>
        <div class="request-list">
          <div v-for="member in members" :key="member.name" class="request-card">
            <div class="request-main">
              <span class="avatar">{{ member.name.slice(0, 1) }}</span>
              <div>
                <strong>{{ member.name }}</strong>
                <div class="candidate-meta">{{ member.meta }}</div>
              </div>
            </div>
            <span class="chip">{{ member.role }}</span>
          </div>
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px">
          <button class="btn btn-small btn-primary" type="button" disabled>申请加入（待接入）</button>
          <button class="btn btn-small btn-ghost" type="button" disabled>联系房主</button>
        </div>
      </section>

      <aside class="profile-card">
        <p class="eyebrow">Status</p>
        <p class="fine">
          当前为框架示意。状态机、成员管理、转让、锁定/解散等操作将在 P2 接入，所有写操作必须经过 service 层与时间窗校验。
        </p>
        <div class="quote" style="margin-top: 20px">
          “先确认边界，再决定要不要成为室友。”
        </div>
      </aside>
    </div>
  </div>
</template>
