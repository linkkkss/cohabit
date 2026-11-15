<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const nickname = computed(() => auth.user?.nickname || '同学')
const college = computed(() => auth.user?.college || '未填写学院')

const sections = [
  { label: '基本资料', value: '20 / 20' },
  { label: '硬指标', value: '20 / 20' },
  { label: '软指标', value: '30 / 30' },
  { label: '红线确认', value: '10 / 10' },
  { label: '标签', value: '10 / 10' },
  { label: 'Prompt', value: '10 / 10' },
]
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Profile</p>
        <h1>我的画像</h1>
        <p>画像完整度达到 100 才能匹配/邀请/申请；联系方式单独存放，不出现在画像里。</p>
      </div>
      <RouterLink class="btn btn-primary" to="/onboarding">继续完善</RouterLink>
    </header>

    <div class="profile-grid">
      <section class="profile-card">
        <div class="profile-head">
          <span class="avatar avatar-lg">{{ nickname.slice(0, 1) }}</span>
          <div>
            <h2>{{ nickname }}</h2>
            <p class="candidate-meta">{{ college }} · 预览/演示数据</p>
          </div>
        </div>

        <div class="tag-list" style="margin-top: 18px">
          <span class="tag">早睡</span>
          <span class="tag">安静</span>
          <span class="tag">整洁</span>
          <span class="tag">有边界</span>
        </div>

        <h3 style="margin: 26px 0 12px; font-size: 15px">画像完成度</h3>
        <div class="completeness">
          <div class="meter">
            <span>总计</span>
            <strong>100 / 100</strong>
          </div>
          <div class="progress"><span style="width: 100%"></span></div>
          <div v-for="section in sections" :key="section.label" class="meter">
            <span>{{ section.label }}</span>
            <strong>{{ section.value }}</strong>
          </div>
        </div>

        <p class="fine" style="margin-top: 18px">
          当前页面为框架示意；真实数据将在 `/api/profiles/me/` 接入后读取。
        </p>
      </section>

      <aside class="profile-card">
        <p class="eyebrow">Prompt</p>
        <div class="quote">“周末一般怎么过？我大概率在图书馆，晚上回来会戴耳机。”</div>
        <div class="quote" style="margin-top: 18px">“最不能接受的是不打招呼带人回来过夜。”</div>
        <p class="fine" style="margin-top: 18px">Prompt 只展示，不参与匹配打分；列表取第一条，详情可展开。</p>
      </aside>
    </div>
  </div>
</template>
