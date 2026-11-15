<script setup lang="ts">
import { RouterLink } from 'vue-router'

const steps = [
  { title: '基本资料', body: '昵称、性别、年级、学院、专业；注册后性别不可自行修改。' },
  { title: '硬指标', body: '作息、烟酒、宠物、访客、空调与整洁频率；11 题。' },
  { title: '软指标与红线', body: '六维自评 + 不能接受的红线；红线用于降分，不用于公开羞辱。' },
  { title: '标签与 Prompt', body: '选 3–8 个标签，写 2–3 条自我介绍；不做照片上传。' },
]
</script>

<template>
  <div class="container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Onboarding</p>
        <h1>把你的“住法”说清楚</h1>
        <p>完成度达到 100 才能开始匹配/邀请/申请。所有答案只用于匹配与展示，联系方式单独存放。</p>
      </div>
      <RouterLink class="btn btn-ghost" to="/profile">查看当前画像</RouterLink>
    </header>

    <div class="panel">
      <div class="meter" style="margin-bottom: 10px">
        <span>画像完成度</span>
        <strong>0 / 100</strong>
      </div>
      <div class="progress"><span style="width: 0%"></span></div>

      <ol class="step-list">
        <li v-for="(step, index) in steps" :key="step.title">
          <span class="step-index">{{ index + 1 }}</span>
          <span><strong>{{ step.title }}</strong><br />{{ step.body }}</span>
        </li>
      </ol>

      <div class="empty" style="margin-top: 24px">
        <strong>问卷接口尚未接入</strong>
        题库与映射已冻结在 docs/03；下一步接入 `/api/profiles/me/` 后，这里会变成可逐题保存的引导流程。
      </div>
    </div>
  </div>
</template>
