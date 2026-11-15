<script setup lang="ts">
import { RouterLink } from 'vue-router'

const demoRooms = [
  {
    code: '482915307',
    title: '计算机学院 · 4 人寝',
    status: '招募中',
    statusClass: 'status-recruiting',
    meta: '3 / 4 · 有空位',
    tags: ['早睡', '安静', '整洁'],
  },
  {
    code: '730184625',
    title: '外国语学院 · 6 人寝',
    status: '招募中',
    statusClass: 'status-recruiting',
    meta: '4 / 6 · 有空位',
    tags: ['有边界', '周末做饭'],
  },
  {
    code: '165903842',
    title: '计算机学院 · 2 人寝',
    status: '已满员',
    statusClass: 'status-full',
    meta: '2 / 2',
    tags: ['夜猫子', '游戏'],
  },
]
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Plaza</p>
        <h1>寝室广场</h1>
        <p>只展示本学院、同性别、仍在招募的寝室；未登录可看有限字段，加入/申请需登录并完成画像。</p>
      </div>
      <RouterLink class="btn btn-primary" to="/rooms">我的寝室</RouterLink>
    </header>

    <div class="filter-row" style="margin-bottom: 20px">
      <span class="chip chip-coral">全部</span>
      <span class="chip">有空位</span>
      <span class="chip">2 人寝</span>
      <span class="chip">4 人寝</span>
      <span class="chip">6 人寝</span>
    </div>

    <div class="room-grid">
      <RouterLink
        v-for="room in demoRooms"
        :key="room.code"
        :to="`/rooms/${room.code}`"
        class="room-card"
      >
        <div class="room-top">
          <span class="room-code">#{{ room.code }}</span>
          <span class="status" :class="room.statusClass">{{ room.status }}</span>
        </div>
        <h3>{{ room.title }}</h3>
        <p class="candidate-meta">{{ room.meta }}</p>
        <div class="tag-list">
          <span v-for="tag in room.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </RouterLink>
    </div>

    <p class="fine" style="margin-top: 18px">
      当前为框架示意数据；广场接口接入后按学院/性别/容量/状态过滤。
    </p>
  </div>
</template>
