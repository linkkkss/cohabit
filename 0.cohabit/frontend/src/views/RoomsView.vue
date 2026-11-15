<script setup lang="ts">
import { RouterLink } from 'vue-router'

const rooms = [
  {
    code: '482915307',
    title: '我的 4 人寝',
    status: '招募中',
    statusClass: 'status-recruiting',
    meta: '3 / 4 · 房主',
    tags: ['早睡', '安静'],
  },
  {
    code: '730184625',
    title: '周末一起做饭',
    status: '已锁定',
    statusClass: 'status-locked',
    meta: '4 / 4 · 成员',
    tags: ['有边界', '周末做饭'],
  },
]
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Rooms</p>
        <h1>我的寝室</h1>
        <p>一人同时只能在一个 ACTIVE 寝室；寝室状态、成员、转让与解散都在详情页操作。</p>
      </div>
      <RouterLink class="btn btn-ghost" to="/plaza">去广场看看</RouterLink>
    </header>

    <div v-if="rooms.length" class="room-grid">
      <RouterLink v-for="room in rooms" :key="room.code" :to="`/rooms/${room.code}`" class="room-card">
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

    <div v-else class="empty">
      <strong>还没有加入寝室</strong>
      可以从匹配发起邀请，或申请加入广场里的寝室。
    </div>

    <p class="fine" style="margin-top: 18px">当前为框架示意数据；寝室接口接入后替换。</p>
  </div>
</template>
