<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

const tabs = ['全部', '待处理', '已互见', '待确认', '已成立'] as const
const activeTab = ref<(typeof tabs)[number]>('全部')
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Connections</p>
        <h1>组寝请求</h1>
        <p>邀请、申请、联系方式互见、二次确认都在这里完成；任何一步都可以体面拒绝或退出。</p>
      </div>
      <RouterLink class="btn btn-ghost" to="/match">去看看匹配</RouterLink>
    </header>

    <div class="tabs" role="tablist" aria-label="请求状态">
      <button
        v-for="tab in tabs"
        :key="tab"
        class="tab"
        :class="{ active: activeTab === tab }"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <div class="empty">
      <strong>{{ activeTab }}的请求会出现在这里</strong>
      接口接入后支持：同意/拒绝、联系方式解锁、第一次确认、第二次确认、撤回与超时倒计时。
    </div>

    <div class="panel" style="margin-top: 18px">
      <p class="eyebrow" style="margin-bottom: 8px">Privacy</p>
      <p class="fine" style="margin: 0">
        联系方式只在 `CONTACT_SHARED` 及之后对请求双方可见；列表、通知、审计日志都不会出现 QQ/微信/手机号。
      </p>
    </div>
  </div>
</template>
