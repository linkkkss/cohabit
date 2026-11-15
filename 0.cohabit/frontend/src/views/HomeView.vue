<script setup lang="ts">
import { RouterLink } from 'vue-router'

const steps = [
  {
    number: '01',
    title: '把话说在前面',
    body: '六维画像 + 红线：作息、整洁、社交、噪声、边界、消费，先对齐再见面。',
  },
  {
    number: '02',
    title: '双向确认，不尴尬',
    body: '邀请或申请都需对方同意；联系方式只在双方确认后出现，不公开、不群发。',
  },
  {
    number: '03',
    title: '确认，再一起住',
    body: '线下聊清楚后回站二次确认，才正式建寝/入寝；任何一步都能体面退出。',
  },
]
</script>

<template>
  <div>
    <section class="hero">
      <div class="container hero-grid">
        <div>
          <p class="eyebrow">Cohabit · 校园组寝</p>
          <h1 class="display">先聊清楚，<br /><em>再住一起。</em></h1>
          <p class="lede">
            室友不是随机分配。用一份认真的画像，找到作息合拍、边界清楚的人；在交换联系方式之前，先把不能妥协的事讲明白。
          </p>
          <div class="hero-actions">
            <RouterLink class="btn btn-primary" to="/onboarding">开始完善画像</RouterLink>
            <RouterLink class="btn btn-ghost" to="/plaza">先看看广场</RouterLink>
          </div>
          <p class="fine">仅限同学院、同性别；不采集真实姓名；联系方式在双方同意后可见。</p>
        </div>

        <div class="hero-art" aria-hidden="true">
          <div class="portrait-card">
            <div class="portrait-top">
              <span class="avatar">林</span>
              <div>
                <div class="portrait-name">早睡 · 安静</div>
                <div class="portrait-meta">计算机学院 · 4 人寝</div>
              </div>
            </div>
            <div class="portrait-lines">
              <span class="portrait-line"></span>
              <span class="portrait-line short"></span>
              <span class="portrait-line"></span>
            </div>
          </div>
          <div class="portrait-card">
            <div class="portrait-top">
              <span class="avatar">周</span>
              <div>
                <div class="portrait-name">整洁 · 有边界</div>
                <div class="portrait-meta">外国语学院 · 6 人寝</div>
              </div>
            </div>
            <div class="portrait-lines">
              <span class="portrait-line"></span>
              <span class="portrait-line"></span>
              <span class="portrait-line short"></span>
            </div>
          </div>
          <div class="portrait-card">
            <div class="portrait-top">
              <span class="avatar">陈</span>
              <div>
                <div class="portrait-name">周末一起做饭</div>
                <div class="portrait-meta">计算机学院 · 2 人寝</div>
              </div>
            </div>
            <div class="portrait-lines">
              <span class="portrait-line short"></span>
              <span class="portrait-line"></span>
            </div>
          </div>
          <div class="hero-stamp">less<br />small talk</div>
        </div>
      </div>
    </section>

    <section class="section container">
      <div class="section-head">
        <div>
          <p class="eyebrow">How it works</p>
          <h2>三步，把“合不合”说清楚</h2>
        </div>
        <p class="fine" style="max-width: 260px">每一步都可以退出；不制造“必须成”的压力。</p>
      </div>
      <div class="step-grid">
        <article v-for="step in steps" :key="step.number" class="step-card">
          <div class="step-number">{{ step.number }}</div>
          <h3>{{ step.title }}</h3>
          <p>{{ step.body }}</p>
        </article>
      </div>
    </section>

    <section class="section-tight container">
      <blockquote class="quote">
        “先把不能接受的说出来，比住进去以后互相忍着更体面。”
      </blockquote>
    </section>
  </div>
</template>
