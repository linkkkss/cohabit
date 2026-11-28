<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import MagneticButton from '@/components/fx/MagneticButton.vue'
import ScrollFloat from '@/components/fx/ScrollFloat.vue'
import FoldText from '@/components/fx/FoldText.vue'
import ShinyText from '@/components/fx/ShinyText.vue'
import ProfileCard from '@/components/profile/ProfileCard.vue'
import { hasIntroPlayed, markIntroPlayed, setIntro } from '@/composables/useIntro'

const router = useRouter()

const facts = [
  { value: '6', unit: '维', label: '画像维度' },
  { value: '3', unit: '分钟', label: '写完基础画像' },
  { value: '2', unit: '次', label: '双向确认' },
  { value: '0', unit: '条', label: '公开联系方式' },
]

const steps = [
  {
    number: '01',
    title: '把话说在前面',
    body: '六维画像 + 红线：作息、整洁、社交、噪声、边界、消费，先对齐再见面。',
    hint: '约 3 分钟',
  },
  {
    number: '02',
    title: '双向确认，不尴尬',
    body: '邀请或申请都需对方同意；联系方式只在双方确认后出现，不公开、不群发。',
    hint: '双方各点一次',
  },
  {
    number: '03',
    title: '确认，再一起住',
    body: '线下聊清楚后回站二次确认，才正式建寝/入寝；任何一步都能体面退出。',
    hint: '可随时退出',
  },
]

const previewPoints = [
  {
    index: '01',
    title: '六维画像',
    body: '作息、整洁、社交、噪声、边界、消费——一个雷达图说清生活习惯，不用逐条盘问。',
  },
  {
    index: '02',
    title: '三条红线',
    body: '哪些事不能妥协，提前写明白。红线会先于寒暄出现，省掉后面所有的为难。',
  },
  {
    index: '03',
    title: '逐项公开',
    body: '每一块内容都能单独决定谁能看到；只有自己可见的部分，不会出现在任何页面。',
  },
]

/* ---------------------------------------------------------------- 入场 */
const skipIntro = ref(
  hasIntroPlayed() ||
    (typeof window !== 'undefined' &&
      (window.matchMedia('(prefers-reduced-motion: reduce)').matches || window.innerWidth <= 900)),
)

const frameEl = ref<HTMLElement | null>(null)
const posterInnerEl = ref<HTMLElement | null>(null)
const hintEl = ref<HTMLElement | null>(null)

const clamp01 = (value: number) => Math.min(1, Math.max(0, value))
const smooth = (from: number, to: number, value: number) => {
  const t = clamp01((value - from) / (to - from || 1e-6))
  return t * t * (3 - 2 * t)
}

let raf = 0
let current = 0
let target = 0
let raw = 0

function applyProgress(p: number) {
  const e = smooth(0, 0.84, p)

  if (frameEl.value) {
    frameEl.value.style.setProperty('--ix', `${28 * (1 - e)}%`)
    frameEl.value.style.setProperty('--iy', `${19 * (1 - e)}%`)
    frameEl.value.style.setProperty('--fr', `${3 * (1 - e)}px`)
    const edge = clamp01(1 - smooth(0.72, 0.84, p) * 1.4)
    frameEl.value.style.setProperty('--edge', edge.toFixed(3))
    frameEl.value.style.setProperty('--shade', (edge * 0.9).toFixed(3))
  }

  const post = smooth(0.9, 1.15, raw)
  if (posterInnerEl.value) {
    posterInnerEl.value.style.opacity = `${1 - post}`
    posterInnerEl.value.style.transform = `scale(${1 + 0.16 * e}) translate3d(0, ${-18 * post}px, 0)`
  }

  const gone = smooth(0, 0.12, p)
  if (hintEl.value) {
    hintEl.value.style.opacity = `${1 - gone}`
    hintEl.value.style.transform = `translate3d(0, ${10 * gone}px, 0)`
  }

  setIntro(p < 0.78, p)
}

function readProgress() {
  const vh = window.innerHeight || 1
  raw = window.scrollY / vh
  return clamp01(raw / 0.85)
}

function tick() {
  raf = 0
  current += (target - current) * 0.12
  if (Math.abs(target - current) < 0.0005) current = target
  else raf = requestAnimationFrame(tick)
  applyProgress(current)
}

function onIntroScroll() {
  target = readProgress()
  if (!raf) raf = requestAnimationFrame(tick)
}

function onIntroResize() {
  target = readProgress()
  current = target
  applyProgress(current)
}

onMounted(() => {
  if (skipIntro.value) {
    markIntroPlayed()
    applyProgress(1)
    setIntro(false, 1)
    return
  }
  markIntroPlayed()
  setIntro(true, 0)
  target = current = readProgress()
  applyProgress(current)
  window.addEventListener('scroll', onIntroScroll, { passive: true })
  window.addEventListener('resize', onIntroResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onIntroScroll)
  window.removeEventListener('resize', onIntroResize)
  if (raf) cancelAnimationFrame(raf)
  setIntro(false, 0)
})
</script>

<template>
  <div class="home">
    <section v-if="!skipIntro" class="entry" data-reveal="none">
      <div class="entry__stage">
        <div ref="frameEl" class="entry__frame">
          <div class="entry__poster" aria-hidden="true">
            <div ref="posterInnerEl" class="entry__poster-inner">
            <span class="entry__kicker mono">Cohabit · 校园组寝</span>
            <svg class="entry__logo" viewBox="0 0 48 48" role="presentation">
              <rect x="1" y="1" width="46" height="46" rx="2" fill="#ff8a00" stroke="#363636" stroke-width="2" />
              <path d="M35 15H17V33H35" fill="none" stroke="#fff4e2" stroke-width="8" />
            </svg>
            <p class="entry__title">先聊清楚，<br /><em>再住一起。</em></p>
            <p class="entry__sub">用一份认真的画像，找到作息合拍、边界清楚的人。</p>
            </div>
          </div>
        </div>

        <div ref="hintEl" class="entry__hint">
          <span class="mono">SCROLL</span>
          <span>向下滚动，进入网站</span>
        </div>
      </div>
    </section>

    <section class="hero" data-reveal="none">
      <div class="hero__glow" aria-hidden="true" />
      <div class="container hero__grid">
        <div class="hero__copy">
          <p class="hero__kicker">
            <span class="hero__live"><span class="hero__dot" aria-hidden="true" />Cohabit · 校园组寝</span>
            <span class="hero__season mono">2026 秋季</span>
          </p>

          <h1 class="hero__title">
            <span class="hero__line"><span class="hero__line-inner">先聊清楚，</span></span>
            <span class="hero__line hero__line--accent">
              <span class="hero__line-inner" style="--d: 90ms">
                <ShinyText
                  text="再住一起。"
                  color="#ff8a00"
                  shine-color="#ffc4a0"
                  :speed="4.4"
                  :shine-width="14"
                  :softness="0.86"
                  :glow="0.1"
                  trigger="loop"
                />
              </span>
            </span>
          </h1>

          <p class="hero__lede">
            室友不是随机分配。用一份认真的画像，找到作息合拍、边界清楚的人；在交换联系方式之前，先把不能妥协的事讲明白。
          </p>

          <div class="hero__actions">
            <MagneticButton to="/onboarding" :padding="110" :strength="2.4" :max-offset="18">
              开始完善画像
              <svg viewBox="0 0 18 18" width="16" height="16" aria-hidden="true">
                <path
                  d="M3.5 9h11M10 4.5 14.5 9 10 13.5"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </MagneticButton>
            <MagneticButton to="/plaza" variant="ghost" :padding="90" :strength="3" :max-offset="12">
              先看看广场
            </MagneticButton>
          </div>

          <ul class="hero__ticks">
            <li>仅同学院、同性别</li>
            <li>不采集真实姓名</li>
            <li>联系方式确认后可见</li>
          </ul>
        </div>

        <div class="hero__stage">
          <span class="stage__halo" aria-hidden="true" />
          <span class="stage__ring" aria-hidden="true" />

          <ProfileCard
            class="stage__card"
            name="林同学"
            title="计算机学院 · 4 人寝"
            handle="@lin · 大三"
            status="早睡 · 安静 · 有边界"
            contact-text="看看她的画像"
            :holo="0.62"
            :glare="0.7"
            :tilt-strength="10"
            :parallax="12"
            initial="林"
            @contact="router.push('/plaza')"
          />

          <div class="stage__chip stage__chip--score">
            <span class="stage__chip-label mono">匹配度</span>
            <span class="stage__score">92<small>%</small></span>
            <span class="stage__chip-foot">作息 / 边界 高度重合</span>
          </div>

          <div class="stage__chip stage__chip--tag">
            <span class="stage__tag-dot" aria-hidden="true" />
            <span>23:30 熄灯</span>
          </div>

          <div class="stage__stamp" aria-hidden="true">
            <span>less</span>
            <span>small talk</span>
          </div>
        </div>
      </div>
    </section>

    <section class="facts" data-reveal="none">
      <div class="container facts__inner">
        <div v-for="fact in facts" :key="fact.label" class="fact">
          <span class="fact__value">{{ fact.value }}<small>{{ fact.unit }}</small></span>
          <span class="fact__label">{{ fact.label }}</span>
        </div>
      </div>
    </section>

    <section class="works">
      <div class="container">
        <div class="works__head">
          <div>
            <p class="eyebrow">How it works</p>
            <ScrollFloat
              as="h2"
              class="works__title"
              text="三步，把合不合说清楚"
              effect="float"
              split-by="words"
              :stagger="0.055"
              :distance="0.9"
            />
          </div>
          <p class="works__aside">
            每一步都可以退出；<br />
            不制造“必须成”的压力。
          </p>
        </div>

        <div class="works__grid">
          <article v-for="step in steps" :key="step.number" class="work" data-reveal>
            <span class="work__ghost" aria-hidden="true">{{ step.number }}</span>
            <header class="work__top">
              <span class="work__index mono">{{ step.number }}</span>
              <span class="work__hint mono">{{ step.hint }}</span>
            </header>
            <h3 class="work__title">{{ step.title }}</h3>
            <p class="work__body">{{ step.body }}</p>
            <span class="work__arrow" aria-hidden="true">
              <svg viewBox="0 0 18 18" width="15" height="15">
                <path
                  d="M4.5 13.5 13.5 4.5M6 4.5h7.5V12"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </span>
          </article>
        </div>
      </div>
    </section>

    <section class="preview">
      <div class="container preview__grid">
        <div class="preview__copy">
          <p class="eyebrow">The profile</p>
          <h2 class="preview__title">你的画像，<br /><em>比简历更诚实。</em></h2>
          <p class="preview__lede">
            别人看到的，只有你愿意公开的部分。真实姓名、学号、联系方式都不在其中——直到双方都点了确认。
          </p>

          <ul class="preview__list">
            <li v-for="point in previewPoints" :key="point.index" class="preview__item">
              <span class="preview__item-index mono">{{ point.index }}</span>
              <div>
                <h3>{{ point.title }}</h3>
                <p>{{ point.body }}</p>
              </div>
            </li>
          </ul>

          <MagneticButton to="/onboarding" :padding="100" :strength="2.6">
            完善我的画像
          </MagneticButton>
        </div>

        <div class="preview__stage">
          <span class="preview__orb" aria-hidden="true" />
          <span class="preview__label mono">画像示例 · 非真实用户</span>
          <ProfileCard
            class="preview__card"
            theme="dark"
            name="周同学"
            title="外国语学院 · 6 人寝"
            handle="@zhou · 大二"
            status="整洁 · 有边界 · 周末做饭"
            status-color="#ffb45e"
            contact-text="看看她的画像"
            :holo="0.7"
            :glare="0.55"
            :tilt-strength="8"
            :parallax="14"
            initial="周"
            @contact="router.push('/plaza')"
          />
          <p class="preview__caption">
            <span class="mono">划重点</span>
            红线条目先于寒暄出现，省掉后面所有的为难。
          </p>
        </div>
      </div>
    </section>

    <section class="voices">
      <div class="container">
        <blockquote class="voices__quote">
          <span class="voices__mark" aria-hidden="true">“</span>
          <p>先把不能接受的说出来，比住进去以后互相忍着更体面。</p>
          <footer class="voices__foot mono">来自一次真实的组寝对话 · 计算机学院</footer>
        </blockquote>
      </div>
    </section>

    <section class="cta" data-reveal>
      <span class="cta__glow" aria-hidden="true" />
      <span class="cta__grid-lines" aria-hidden="true" />
      <div class="container cta__inner">
        <p class="eyebrow eyebrow--light">Ready when you are</p>
        <FoldText
          as="h2"
          class="cta__title"
          text="把话说在前面，住得舒服一点。"
          split-by="char"
          hinge="top"
          trigger="scroll"
          :fold-angle="96"
          :stagger="0.028"
          :duration="0.7"
          :perspective="760"
        />
        <p class="cta__lede">三分钟写完画像，剩下的交给双向确认。不合适也没关系，退出永远体面。</p>
        <div class="cta__actions">
          <MagneticButton to="/onboarding" :padding="120" :strength="2.3" :max-offset="20">
            开始完善画像
          </MagneticButton>
          <MagneticButton to="/plaza" variant="ghost" :padding="100" :strength="3">
            先看看广场
          </MagneticButton>
        </div>
        <p class="cta__note">不需要真实姓名 · 画像随时可删 · 仅限同学院同性别</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  padding-bottom: 0;
}

/* ---------------------------------------------------------------- hero */
.hero {
  position: relative;
  padding: clamp(40px, 5.6vw, 78px) 0 clamp(44px, 5vw, 76px);
}

.hero__glow {
  position: absolute;
  top: -18%;
  right: -8%;
  width: min(720px, 70vw);
  height: min(720px, 70vw);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 138, 0, 0.16) 0%, rgba(255, 180, 94, 0.08) 45%, transparent 68%);
  filter: blur(10px);
  pointer-events: none;
}

.hero__grid {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.04fr) minmax(0, 0.96fr);
  align-items: center;
  gap: clamp(28px, 4vw, 64px);
}

.hero__copy {
  min-width: 0;
}

.hero__kicker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 20px;
  margin: 0 0 clamp(20px, 2.4vw, 30px);
  font-size: 12px;
  letter-spacing: 0.02em;
  animation: hero-soft 760ms var(--ease-out) both;
}

.hero__live {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 13px 6px 10px;
  border: 1px solid color-mix(in srgb, var(--line-strong) 70%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--paper-raised) 70%, transparent);
  color: var(--ink);
  font-weight: 500;
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}

.hero__dot {
  position: relative;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--coral);
  box-shadow: 0 0 0 4px rgba(255, 138, 0, 0.14);
}

.hero__dot::after {
  position: absolute;
  inset: -4px;
  border: 1px solid var(--coral);
  border-radius: 50%;
  content: '';
  opacity: 0;
  animation: dot-ping 2.8s var(--ease-out) infinite;
}

.hero__season {
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.hero__title {
  display: flex;
  flex-direction: column;
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(46px, 6.4vw, 88px);
  font-weight: 400;
  letter-spacing: -0.03em;
  line-height: 1.02;
}

.hero__line {
  display: block;
  overflow: hidden;
  padding-bottom: 0.06em;
}

.hero__line-inner {
  display: inline-block;
  animation: hero-rise 1080ms var(--ease-out) both;
  animation-delay: var(--d, 0ms);
}

.hero__line--accent {
  margin-top: 0.02em;
}

.hero__line--accent :deep(.shiny) {
  font-style: italic;
}

.hero__lede {
  max-width: 34em;
  margin: clamp(20px, 2.4vw, 28px) 0 0;
  color: var(--muted);
  font-size: clamp(14.5px, 1.15vw, 16.5px);
  line-height: 1.78;
  animation: hero-soft 900ms var(--ease-out) 260ms both;
}

.hero__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: clamp(24px, 3vw, 34px);
  animation: hero-soft 900ms var(--ease-out) 380ms both;
}

.hero__actions :deep(.btn) {
  gap: 8px;
}

.hero__ticks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  margin: clamp(22px, 2.6vw, 30px) 0 0;
  padding: 0;
  color: var(--muted);
  font-size: 12px;
  list-style: none;
  animation: hero-soft 900ms var(--ease-out) 480ms both;
}

.hero__ticks li {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.hero__ticks li::before {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--coral);
  content: '';
}

/* --------------------------------------------------------------- stage */
.hero__stage {
  position: relative;
  display: grid;
  min-height: clamp(520px, 48vw, 610px);
  padding-bottom: 30px;
  place-items: center;
}

.stage__halo {
  position: absolute;
  inset: 8% 2%;
  border-radius: 50%;
  background: radial-gradient(circle at 52% 42%, rgba(255, 138, 0, 0.2), transparent 62%);
  filter: blur(18px);
  pointer-events: none;
}

.stage__ring {
  position: absolute;
  width: min(430px, 82%);
  aspect-ratio: 1;
  border: 1px dashed color-mix(in srgb, var(--coral) 28%, transparent);
  border-radius: 50%;
  animation: ring-spin 90s linear infinite;
  pointer-events: none;
}

.stage__card {
  position: relative;
  z-index: 2;
  width: min(302px, 76%);
  transform: rotate(-2.4deg) translate(24px, -8px);
  transition: transform 900ms var(--ease-out);
}

.stage__card:hover {
  transform: rotate(0deg) translate(24px, -14px);
}

.stage__chip {
  position: absolute;
  z-index: 3;
  border: 1px solid color-mix(in srgb, var(--line) 82%, transparent);
  border-radius: 16px;
  background: color-mix(in srgb, var(--paper-raised) 74%, transparent);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 22px 44px -30px rgba(54, 54, 54, 0.55);
  -webkit-backdrop-filter: blur(16px) saturate(1.4);
  backdrop-filter: blur(16px) saturate(1.4);
  animation: float-soft 9s ease-in-out infinite alternate;
}

.stage__chip--score {
  top: 3%;
  left: -1%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 126px;
  padding: 12px 15px 11px;
}

.stage__chip-label {
  color: var(--muted);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.stage__score {
  font-family: var(--font-serif);
  font-size: 38px;
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.05;
}

.stage__score small {
  margin-left: 2px;
  color: var(--coral);
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 600;
}

.stage__chip-foot {
  color: var(--muted);
  font-size: 10.5px;
  white-space: nowrap;
}

.stage__chip--tag {
  top: 26%;
  right: -2%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 500;
  animation-delay: -3.4s;
}

.stage__tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--amber);
}

.stage__stamp {
  position: absolute;
  right: 0;
  bottom: 6px;
  z-index: 3;
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--ink) 26%, transparent);
  border-radius: 4px;
  background: color-mix(in srgb, var(--paper) 60%, transparent);
  color: var(--ink);
  font-family: var(--font-serif);
  font-size: 13.5px;
  font-style: italic;
  letter-spacing: 0.01em;
  line-height: 1.1;
  text-align: center;
  transform: rotate(-6deg);
  opacity: 0.85;
}

/* --------------------------------------------------------------- facts */
.facts {
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--paper-raised) 55%, transparent);
}

.facts__inner {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.fact {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 22px clamp(12px, 2vw, 28px);
  border-left: 1px solid var(--line-soft);
}

.fact:first-child {
  border-left: 0;
  padding-left: 0;
}

.fact__value {
  font-family: var(--font-serif);
  font-size: clamp(28px, 3vw, 38px);
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1;
}

.fact__value small {
  margin-left: 3px;
  color: var(--coral-dark);
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
}

.fact__label {
  color: var(--muted);
  font-size: 12px;
}

/* --------------------------------------------------------------- works */
.works {
  padding: clamp(64px, 8vw, 108px) 0 clamp(56px, 7vw, 96px);
}

.works__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: clamp(28px, 3.4vw, 44px);
}

.works__title {
  display: block;
  margin-top: 10px;
  font-family: var(--font-serif);
  font-size: clamp(30px, 4vw, 50px);
  font-weight: 400;
  letter-spacing: -0.025em;
  line-height: 1.12;
}

.works__aside {
  margin: 0;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
  text-align: right;
}

.works__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.work {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 250px;
  padding: 24px 24px 22px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: var(--paper-raised);
  overflow: hidden;
  transition:
    transform 620ms var(--ease-out),
    border-color 620ms var(--ease-out),
    box-shadow 620ms var(--ease-out);
}

.work::after {
  position: absolute;
  inset: auto -30% -60% -30%;
  height: 70%;
  background: radial-gradient(circle at 50% 0%, rgba(255, 138, 0, 0.14), transparent 70%);
  content: '';
  opacity: 0;
  transition: opacity 620ms var(--ease-out);
  pointer-events: none;
}

.work:hover {
  transform: translateY(-6px);
  border-color: color-mix(in srgb, var(--coral) 34%, var(--line));
  box-shadow: 0 30px 50px -40px rgba(54, 54, 54, 0.55);
}

.work:hover::after {
  opacity: 1;
}

.work__ghost {
  position: absolute;
  right: 12px;
  bottom: -26px;
  color: color-mix(in srgb, var(--coral) 9%, transparent);
  font-family: var(--font-serif);
  font-size: 132px;
  font-weight: 500;
  line-height: 1;
  pointer-events: none;
  transition: transform 720ms var(--ease-out);
}

.work:hover .work__ghost {
  transform: translateY(-8px) rotate(-3deg);
}

.work__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.work__index {
  color: var(--coral-dark);
  font-size: 11px;
  letter-spacing: 0.18em;
}

.work__hint {
  color: var(--muted);
  font-size: 10px;
  letter-spacing: 0.08em;
}

.work__title {
  margin: 26px 0 0;
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
  letter-spacing: -0.01em;
}

.work__body {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.72;
}

.work__arrow {
  display: grid;
  width: 30px;
  height: 30px;
  margin-top: auto;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  color: var(--ink);
  opacity: 0;
  transform: translate(-6px, 6px);
  transition:
    opacity 480ms var(--ease-out),
    transform 480ms var(--ease-out);
}

.work:hover .work__arrow {
  opacity: 1;
  transform: none;
}

/* ------------------------------------------------------------- preview */
.preview {
  position: relative;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  background:
    radial-gradient(80% 60% at 88% 10%, rgba(255, 180, 94, 0.14), transparent 62%),
    linear-gradient(180deg, var(--paper-deep), color-mix(in srgb, var(--paper-deep) 42%, var(--paper)));
  padding: clamp(56px, 7vw, 96px) 0;
}

.preview__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  align-items: center;
  gap: clamp(32px, 5vw, 76px);
}

.preview__title {
  margin: 12px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(30px, 4.2vw, 52px);
  font-weight: 400;
  letter-spacing: -0.028em;
  line-height: 1.14;
}

.preview__title em {
  color: var(--coral);
  font-style: italic;
}

.preview__lede {
  max-width: 32em;
  margin: 18px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.78;
}

.preview__list {
  margin: 30px 0 32px;
  padding: 0;
  border-top: 1px solid color-mix(in srgb, var(--line-strong) 60%, transparent);
  list-style: none;
}

.preview__item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 8px;
  padding: 16px 0;
  border-bottom: 1px solid color-mix(in srgb, var(--line-strong) 60%, transparent);
}

.preview__item-index {
  padding-top: 3px;
  color: var(--coral-dark);
  font-size: 10.5px;
  letter-spacing: 0.14em;
}

.preview__item h3 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.preview__item p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}

.preview__stage {
  position: relative;
  display: grid;
  min-height: 640px;
  place-items: center;
}

.preview__orb {
  position: absolute;
  width: min(400px, 78%);
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 42% 36%, rgba(255, 170, 110, 0.5), rgba(255, 138, 0, 0.16) 52%, transparent 70%);
  filter: blur(6px);
}

.preview__label {
  position: absolute;
  top: 0;
  left: 2%;
  z-index: 3;
  padding: 5px 10px;
  border: 1px solid color-mix(in srgb, var(--line-strong) 60%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--paper-raised) 72%, transparent);
  color: color-mix(in srgb, var(--ink) 62%, transparent);
  font-size: 8.6px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
}

.preview__card {
  position: relative;
  z-index: 2;
  width: min(330px, 84%);
  transform: rotate(2.4deg);
  transition: transform 900ms var(--ease-out);
}

.preview__card:hover {
  transform: rotate(0deg) translateY(-4px);
}

.preview__caption {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 3;
  max-width: 250px;
  margin: 0;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.65;
  text-align: right;
}

.preview__caption .mono {
  display: block;
  margin-bottom: 4px;
  color: var(--coral-dark);
  font-size: 9.5px;
  letter-spacing: 0.18em;
}

/* -------------------------------------------------------------- voices */
.voices {
  padding: clamp(44px, 5vw, 72px) 0;
}

.voices__quote {
  position: relative;
  max-width: 720px;
  margin: 0 auto;
  padding-left: clamp(0px, 4vw, 56px);
  text-align: center;
}

.voices__mark {
  display: block;
  margin-bottom: -8px;
  color: var(--coral);
  font-family: var(--font-serif);
  font-size: 76px;
  line-height: 1;
  opacity: 0.5;
}

.voices__quote p {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(22px, 3.1vw, 34px);
  font-weight: 400;
  letter-spacing: -0.02em;
  line-height: 1.5;
}

.voices__foot {
  margin-top: 20px;
  color: var(--muted);
  font-size: 10.5px;
  letter-spacing: 0.12em;
}

/* ----------------------------------------------------------------- cta */
.cta {
  position: relative;
  padding: clamp(64px, 8vw, 110px) 0 clamp(56px, 7vw, 96px);
  background: var(--ink);
  color: var(--paper);
  overflow: hidden;
}

.cta__glow {
  position: absolute;
  top: -40%;
  left: 50%;
  width: min(880px, 120vw);
  height: min(880px, 120vw);
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 138, 0, 0.42), rgba(184, 95, 0, 0.12) 46%, transparent 68%);
  transform: translateX(-50%);
  filter: blur(20px);
  pointer-events: none;
}

.cta__grid-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(251, 246, 238, 0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(251, 246, 238, 0.05) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: radial-gradient(circle at 50% 20%, #000 0%, transparent 72%);
  -webkit-mask-image: radial-gradient(circle at 50% 20%, #000 0%, transparent 72%);
  pointer-events: none;
}

.cta__inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.cta .eyebrow--light,
.eyebrow--light {
  color: rgba(251, 246, 238, 0.55);
}

.cta__title {
  display: block;
  max-width: 18em;
  margin-top: 14px;
  font-family: var(--font-serif);
  font-size: clamp(32px, 4.6vw, 60px);
  font-weight: 400;
  letter-spacing: -0.03em;
  line-height: 1.14;
  color: var(--paper);
}

.cta__title :deep(.ft__piece),
.cta__title :deep(.ft__space) {
  color: var(--paper);
}

.cta__lede {
  max-width: 32em;
  margin: 20px 0 0;
  color: rgba(251, 246, 238, 0.66);
  font-size: 14px;
  line-height: 1.78;
}

.cta__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 32px;
}

.cta__actions :deep(.btn-ghost) {
  border-color: rgba(251, 246, 238, 0.26);
  background: rgba(251, 246, 238, 0.06);
  color: var(--paper);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14);
}

.cta__actions :deep(.btn-ghost:hover) {
  border-color: rgba(251, 246, 238, 0.5);
  background: rgba(251, 246, 238, 0.12);
}

.cta__note {
  margin: 26px 0 0;
  color: rgba(251, 246, 238, 0.42);
  font-size: 11.5px;
  letter-spacing: 0.04em;
}

/* ------------------------------------------------------------ keyframes */
@keyframes hero-rise {
  from {
    opacity: 0.001;
    transform: translateY(112%);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes hero-soft {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes dot-ping {
  0% {
    opacity: 0.5;
    transform: scale(0.7);
  }
  70%,
  100% {
    opacity: 0;
    transform: scale(2.2);
  }
}

@keyframes ring-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes float-soft {
  from {
    transform: translateY(-5px);
  }
  to {
    transform: translateY(5px);
  }
}

/* ---------------------------------------------------------- responsive */
@media (max-width: 1024px) {
  .hero__grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 44px;
  }

  .hero__stage {
    width: 100%;
    max-width: 620px;
    margin: 0 auto;
    min-height: 0;
    padding: 18px 0 8px;
  }

  .stage__card {
    transform: rotate(-2deg) translate(0, -4px);
  }

  .stage__card:hover {
    transform: rotate(0deg) translate(0, -10px);
  }

  .hero__lede {
    max-width: 40em;
  }

  .preview__grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 44px;
  }

  .preview__stage {
    min-height: 480px;
  }
}

@media (max-width: 820px) {
  .facts__inner {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fact {
    border-left: 0;
    border-top: 1px solid var(--line-soft);
    padding-inline: 0;
  }

  .fact:nth-child(-n + 2) {
    border-top: 0;
  }

  .fact:nth-child(even) {
    padding-left: 18px;
    border-left: 1px solid var(--line-soft);
  }

  .works__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .works__aside {
    text-align: left;
  }

  .works__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .work {
    min-height: 0;
  }

  .work__title {
    margin-top: 18px;
  }

  .preview__caption {
    position: static;
    max-width: none;
    margin-top: 18px;
    text-align: left;
  }

  .preview__stage {
    min-height: 0;
    padding: 14px 0 8px;
  }

  .preview__label {
    position: static;
    justify-self: start;
    margin-bottom: 4px;
  }
}

@media (max-width: 620px) {
  .hero {
    padding-top: 26px;
  }

  .hero__stage {
    min-height: 440px;
  }

  .stage__card {
    width: min(288px, 88%);
  }

  .stage__chip--score {
    top: 0;
    left: -2%;
    min-width: 112px;
    padding: 10px 13px;
  }

  .stage__score {
    font-size: 30px;
  }

  .stage__chip--tag {
    top: 20%;
    right: -2%;
  }

  .stage__stamp {
    display: none;
  }

  .stage__chip--tag {
    top: 14%;
  }

  .hero__ticks {
    gap: 6px 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero__kicker,
  .hero__lede,
  .hero__actions,
  .hero__ticks,
  .hero__line-inner {
    animation: none;
  }

  .hero__dot::after,
  .stage__ring,
  .stage__chip {
    animation: none;
  }

  .stage__card,
  .preview__card,
  .work,
  .work__ghost {
    transition: none;
  }
}

/* ---------------------------------------------------------------- 包豪斯 */
.hero__glow {
  background: var(--coral);
  filter: none;
  opacity: 0.09;
}

.stage__halo {
  inset: 11% 5%;
  border: 2px solid var(--ink);
  background: var(--coral-soft);
  filter: none;
}

.stage__ring {
  border: 1.5px dashed var(--ink);
  opacity: 0.55;
}

.stage__chip {
  border: 2px solid var(--ink);
  border-radius: 2px;
  background: var(--paper-raised);
  box-shadow: 4px 4px 0 var(--ink);
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
  animation: none;
}

.stage__stamp {
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  background: var(--paper-raised);
  box-shadow: 3px 3px 0 var(--ink);
  font-family: var(--font-display);
  font-style: normal;
  opacity: 1;
}

.stage__score {
  font-family: var(--font-display);
  font-weight: 700;
}

.facts {
  border-top: 2px solid var(--ink);
  border-bottom: 2px solid var(--ink);
  background: transparent;
}

.fact {
  border-left: 1.5px solid var(--ink);
}

.fact__value {
  font-family: var(--font-display);
  font-weight: 700;
}

.work {
  border: 2px solid var(--ink);
  border-radius: 3px;
  background: var(--paper-raised);
  box-shadow: 6px 6px 0 rgba(54, 54, 54, 0.12);
  transition:
    transform 200ms var(--ease-out),
    box-shadow 200ms var(--ease-out);
}

.work::after {
  display: none;
}

.work:hover {
  transform: translate(-3px, -3px);
  border-color: var(--ink);
  box-shadow: 9px 9px 0 var(--ink);
}

.work__ghost {
  color: color-mix(in srgb, var(--coral) 16%, transparent);
  font-family: var(--font-display);
  font-weight: 700;
}

.work__arrow {
  border: 1.5px solid var(--ink);
  border-radius: 2px;
}

.preview {
  border-top: 2px solid var(--ink);
  border-bottom: 2px solid var(--ink);
  background: var(--paper-deep);
}

.preview__list,
.preview__item {
  border-color: var(--ink);
}

.preview__item {
  border-bottom: 1.5px solid var(--ink);
}

.preview__list {
  border-top: 1.5px solid var(--ink);
}

.preview__item-index {
  color: var(--ink);
  font-weight: 700;
}

.preview__orb {
  background: var(--coral-soft);
  border: 2px solid var(--ink);
  filter: none;
}

.preview__label {
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  background: var(--paper-raised);
  color: var(--ink);
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
}

.voices__mark {
  font-family: var(--font-display);
  font-weight: 700;
  opacity: 0.35;
}

.voices__quote p {
  font-family: var(--font-display);
  font-weight: 500;
}

.cta__glow {
  background: var(--coral);
  filter: none;
  opacity: 0.18;
}

.hero__live {
  border: 1.5px solid var(--ink);
  border-radius: 2px;
  background: var(--paper-raised);
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
}

.hero__dot {
  border-radius: 0;
  box-shadow: none;
}

.hero__dot::after {
  display: none;
}

.hero__title {
  font-weight: 700;
  letter-spacing: -0.035em;
}

.works__title,
.preview__title {
  font-family: var(--font-display);
  font-weight: 700;
  letter-spacing: -0.03em;
}

.work__title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.work__ghost {
  opacity: 0.7;
}

.cta__glow {
  background: transparent;
  border: 2px solid rgba(255, 138, 0, 0.55);
  filter: none;
  opacity: 1;
}

.cta .eyebrow {
  border-color: rgba(255, 246, 232, 0.45);
  background: transparent;
  color: var(--paper);
}

/* ---------------------------------------------------------------- 入场 */
.entry {
  position: relative;
  height: 170vh;
  margin-top: calc(var(--shell-header-h, 76px) * -1);
  padding-top: var(--shell-header-h, 76px);
  background-color: var(--paper-deep);
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.055) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.055) 1px, transparent 1px);
  background-size: 56px 56px;
}

.entry__stage {
  position: sticky;
  top: var(--shell-header-h, 76px);
  display: block;
  height: calc(100vh - var(--shell-header-h, 76px));
  overflow: hidden;
  background-color: var(--paper-deep);
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.055) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.055) 1px, transparent 1px);
  background-size: 56px 56px;
}

.entry__frame {
  position: absolute;
  top: var(--iy, 19%);
  right: var(--ix, 28%);
  bottom: var(--iy, 19%);
  left: var(--ix, 28%);
  overflow: hidden;
  border: 2px solid rgba(54, 54, 54, var(--edge, 1));
  border-radius: var(--fr, 3px);
  background-color: var(--paper);
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.05) 1px, transparent 1px);
  background-size: 56px 56px;
  box-shadow: 8px 8px 0 rgba(54, 54, 54, var(--shade, 0.9));
  will-change: top, right, bottom, left;
}

.entry__poster {
  position: absolute;
  inset: 0;
  z-index: 2;
  overflow: hidden;
  display: flex;
  background-color: var(--paper);
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.05) 1px, transparent 1px);
  background-size: 56px 56px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 6% 8%;
  text-align: center;
  will-change: opacity, transform;
}

.entry__poster-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  width: 100%;
  min-height: 100%;
  will-change: opacity, transform;
}

.entry__kicker {
  border: 1.5px solid var(--ink);
  background: var(--paper-raised);
  padding: 5px 10px;
  font-size: 9.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.entry__logo {
  width: clamp(52px, 5.6vw, 76px);
  height: auto;
  border-radius: 2px;
  box-shadow: 4px 4px 0 var(--ink);
}

.entry__title {
  margin: 2px 0 0;
  font-family: var(--font-display);
  font-size: clamp(34px, 4.6vw, 66px);
  font-weight: 700;
  line-height: 1.04;
  letter-spacing: -0.045em;
  color: var(--ink);
}

.entry__title em {
  font-style: normal;
  color: var(--coral);
}

.entry__sub {
  margin: 0;
  max-width: 30ch;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}

.entry__hint {
  position: absolute;
  right: 0;
  bottom: 18px;
  left: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.1em;
  will-change: opacity, transform;
}

.entry__hint::before {
  content: '';
  width: 22px;
  height: 2px;
  background: var(--ink);
}

@media (max-width: 900px) {
  .entry {
    height: auto;
  }

  .entry__stage {
    position: relative;
    top: auto;
    height: auto;
    min-height: 0;
    background: transparent;
  }

  .entry__frame {
    position: relative;
    inset: auto;
    border: 0;
    box-shadow: none;
    background: transparent;
  }
}

@media (prefers-reduced-motion: reduce) {
  .entry {
    height: auto;
  }
}
</style>
