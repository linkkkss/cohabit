<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import MagneticButton from '@/components/fx/MagneticButton.vue'
import ProfileCard from '@/components/profile/ProfileCard.vue'
import SwingTag from '@/components/profile/SwingTag.vue'
import ScrollFloat from '@/components/fx/ScrollFloat.vue'
import ShinyText from '@/components/fx/ShinyText.vue'
import { candidates, DIM_META, me, dimAverage } from '@/data/mock'

const router = useRouter()
const match = candidates[0]!
const skipped = ref(false)
const sent = ref(false)
const mineAvg = computed(() => dimAverage(me.dims))

const reasons = computed(() => [
  {
    key: 'sleep',
    title: '作息几乎重合',
    copy: '你填 23:30 熄灯，对方填 23:00–23:45。这类差异通常一周内就会暴露，先对上更省事。',
    mine: me.dims.sleep,
    theirs: match.dims.sleep,
  },
  {
    key: 'boundary',
    title: '边界感在同一档',
    copy: '“不翻别人东西、不带人回寝要先说”两条你们选得一样，冲突概率最低。',
    mine: me.dims.boundary,
    theirs: match.dims.boundary,
  },
  {
    key: 'redline',
    title: '三条红线没有交叉',
    copy: '你最在意“凌晨打游戏开麦”，对方恰好也不接受；没有需要谁让一步的地方。',
    mine: 100,
    theirs: 100,
  },
])

const sendInvite = (): void => {
  sent.value = true
}

const editMine = (): void => {
  void router.push('/profile')
}
</script>

<template>
  <div class="match">
    <header class="container match__head">
      <div>
        <p class="eyebrow">Today · 今日匹配</p>
        <h1 class="match__title">
          <span>今天只推<ShinyText text="一个" color="#ff8a00" shine-color="#ffc39e" :speed="4.2" :shine-width="16" :softness="0.85" :glow="0.1" />，</span>
          <span>省点力气。</span>
        </h1>
        <p class="match__lede">
          每周一、四各更新一次。匹配不是打分排名，只是把“先聊谁”这件事变得不需要纠结。
        </p>
      </div>
      <p class="match__stamp mono">MATCH · 11 / 25 · 92%</p>
    </header>

    <section class="container match__stage" aria-label="今日匹配结果">
      <template v-if="!skipped">
        <div class="match__pair">
          <div class="match__side match__side--me">
            <p class="match__label">你</p>
            <ProfileCard
              :name="me.name"
              :title="`${me.college} · ${me.grade}`"
              :handle="`@${me.handle}`"
              status="本周被查看 12 次"
              contact-text="完善画像"
              :initial="me.initial"
              theme="light"
              :radius="20"
              :holo="0.4"
              :glare="0.5"
              :tilt-strength="7"
              @contact="editMine"
            >
              <template #portrait>
                <div class="portrait portrait--me">
                  <span class="portrait__grid" aria-hidden="true" />
                  <span class="portrait__init">{{ me.initial }}</span>
                  <span class="portrait__tag mono">YOU · {{ mineAvg }} AVG</span>
                </div>
              </template>
            </ProfileCard>
          </div>

          <div class="match__dial">
            <div class="match__score">
              <svg viewBox="0 0 128 128" width="128" height="128" aria-hidden="true" class="match__ring">
                <circle cx="64" cy="64" r="56" fill="none" stroke="var(--line-soft)" stroke-width="1.2" />
                <circle
                  cx="64"
                  cy="64"
                  r="56"
                  fill="none"
                  stroke="var(--coral)"
                  stroke-width="2.4"
                  stroke-linecap="round"
                  stroke-dasharray="352 352"
                  transform="rotate(-90 64 64)"
                  class="match__ring-arc"
                />
              </svg>
              <span class="match__score-num">{{ match.score }}<small>%</small></span>
              <span class="match__score-label mono">FIT</span>
            </div>
            <p class="match__dial-copy">六维加权后<br />高于 94% 的同学</p>
          </div>

          <div class="match__side match__side--them">
            <p class="match__label">对方</p>
            <SwingTag
              :name="match.name"
              :initial="match.initial"
              :score="match.score"
              :college="match.college"
              :grade="match.grade"
              tone="ink"
            />
          </div>
        </div>

        <div class="match__reasons">
          <article v-for="(reason, index) in reasons" :key="reason.key" class="reason" :style="{ '--i': index }">
            <span class="reason__index mono">0{{ index + 1 }}</span>
            <div class="reason__body">
              <h2 class="reason__title">{{ reason.title }}</h2>
              <p class="reason__copy">{{ reason.copy }}</p>
            </div>
            <div class="reason__compare">
              <div class="reason__row">
                <span class="reason__who">你</span>
                <span class="reason__track"><span class="reason__fill" :style="{ width: `${reason.mine}%` }" /></span>
                <span class="reason__num mono">{{ reason.mine }}</span>
              </div>
              <div class="reason__row">
                <span class="reason__who">对方</span>
                <span class="reason__track"><span class="reason__fill reason__fill--dot" :style="{ width: `${reason.theirs}%` }" /></span>
                <span class="reason__num mono">{{ reason.theirs }}</span>
              </div>
            </div>
          </article>

          <div v-if="!sent" class="match__actions">
            <MagneticButton :padding="120" :strength="2.4" @click="sendInvite">发起邀请</MagneticButton>
            <MagneticButton to="/plaza" variant="ghost" :padding="100">我想先看看广场</MagneticButton>
            <button class="match__skip" type="button" @click="skipped = true">今天先不看了</button>
          </div>
          <div v-else class="match__sent" role="status">
            <span class="match__sent-icon" aria-hidden="true">
              <svg viewBox="0 0 16 16" width="13" height="13">
                <path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <div class="match__sent-copy">
              <strong>邀请已发出</strong>
              <p>等对方确认后，对话会自动出现在「请求」里。在那之前不会开放任何联系方式。</p>
            </div>
            <RouterLink to="/plaza" class="match__sent-link">回广场 →</RouterLink>
          </div>
          <p class="match__fine">
            邀请会先发到对方那里，双方都同意后才会开放对话与联系方式。今天不选也不会影响下次匹配。
          </p>
        </div>
      </template>

      <div v-else class="match__empty">
        <p class="eyebrow">Skipped</p>
        <h2 class="match__empty-title">好，今天就不推了。</h2>
        <p class="match__empty-text">
          跳过不会降低你的匹配权重。周四会有一份新的画像匹配；你也可以先去广场，按自己的节奏看。
        </p>
        <div class="match__empty-actions">
          <MagneticButton to="/plaza" variant="dark">去广场看看</MagneticButton>
          <button class="match__skip" type="button" @click="skipped = false">还是看一下今天的</button>
        </div>
      </div>
    </section>

    <section class="container how">
      <div class="how__head">
        <p class="eyebrow">How it works</p>
        <ScrollFloat
          as="h2"
          class="how__title"
          text="匹配只做三件事"
          effect="float"
          split-by="words"
          :stagger="0.05"
        />
      </div>
      <div class="how__grid">
        <article class="how__card">
          <span class="how__num mono">01</span>
          <h3>六维加权</h3>
          <p>作息、整洁、社交、噪声、边界、消费各有权重，按你在问卷里标过的“在意程度”加权，而不是平均分。</p>
          <div class="how__bars" aria-hidden="true">
            <span
              v-for="dim in DIM_META"
              :key="dim.key"
              :style="{ height: `${10 + Number(me.dims[dim.key]) * 0.38}px` }"
            />
          </div>
        </article>
        <article class="how__card">
          <span class="how__num mono">02</span>
          <h3>红线一票否决</h3>
          <p>三条绝对不能接受的事只要交叉一条，这份匹配就不会出现在今天的结果里——不管你其他维度多高。</p>
          <div class="how__flag" aria-hidden="true"><span />红线 · 0 交叉</div>
        </article>
        <article class="how__card">
          <span class="how__num mono">03</span>
          <h3>双向确认</h3>
          <p>邀请不是“加好友”。只有两个人都点了同意，对话才会打开；在那之前，双方都看不到联系方式。</p>
          <div class="how__pair-dots" aria-hidden="true"><span /><span /><em>handshake</em></div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.match {
  padding-bottom: 24px;
}

.match__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: clamp(36px, 5vw, 64px) 0 clamp(22px, 3vw, 34px);
}

.match__title {
  margin: 12px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(34px, 5vw, 58px);
  font-weight: 400;
  letter-spacing: -0.03em;
  line-height: 1.16;
}

.match__title > span {
  display: block;
}

.match__lede {
  max-width: 34em;
  margin: 16px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.78;
}

.match__stamp {
  flex: none;
  align-self: flex-end;
  padding: 6px 12px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  color: var(--muted);
  font-size: 9px;
  letter-spacing: 0.16em;
}

.match__stage {
  padding: clamp(20px, 3vw, 30px);
  border: 1px solid var(--line);
  border-radius: 30px;
  background:
    radial-gradient(120% 90% at 50% -10%, rgba(255, 138, 0, 0.09), transparent 58%),
    linear-gradient(180deg, var(--paper-raised), color-mix(in srgb, var(--paper-deep) 70%, var(--paper)));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 40px 80px -70px rgba(54, 54, 54, 0.6);
}

.match__pair {
  display: grid;
  max-width: 900px;
  margin: 0 auto;
  grid-template-columns: minmax(0, 1fr) minmax(120px, 0.46fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(16px, 3vw, 30px);
}

.match__side {
  display: grid;
  justify-items: center;
  gap: 10px;
  min-width: 0;
}

.match__side :deep(.profile-card) {
  width: min(300px, 100%);
}

.match__label {
  margin: 0;
  color: var(--muted);
  font-size: 10.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.match__dial {
  display: grid;
  justify-items: center;
  gap: 12px;
  text-align: center;
}

.match__score {
  position: relative;
  display: grid;
  width: 128px;
  height: 128px;
  place-items: center;
}

.match__ring {
  position: absolute;
  inset: 0;
}

.match__ring-arc {
  stroke-dasharray: 352 352;
  animation: ring-in 1400ms var(--ease-out) both;
}

.match__score-num {
  font-family: var(--font-serif);
  font-size: 34px;
  letter-spacing: -0.03em;
  line-height: 1;
}

.match__score-num small {
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--muted);
}

.match__score-label {
  position: absolute;
  bottom: 26px;
  color: var(--muted);
  font-size: 8px;
  letter-spacing: 0.2em;
}

.match__dial-copy {
  margin: 0;
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.6;
}

.match__reasons {
  display: grid;
  gap: 0;
  margin-top: clamp(22px, 3vw, 30px);
  border-top: 1px solid var(--line);
}

.reason {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr) minmax(180px, 0.55fr);
  gap: 18px;
  padding: 20px 0;
  border-bottom: 1px solid var(--line-soft);
}

.reason__index {
  color: var(--coral-dark);
  font-size: 9.5px;
  letter-spacing: 0.16em;
  padding-top: 3px;
}

.reason__title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 500;
}

.reason__copy {
  max-width: 40em;
  margin: 6px 0 12px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.72;
}

.reason__compare {
  display: grid;
  align-content: center;
  gap: 7px;
  grid-column: 3;
  min-width: 0;
  padding-left: clamp(0px, 1vw, 14px);
}

.reason__compare-label {
  color: var(--muted);
  font-size: 8.6px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 2px;
}

.reason__row {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) 22px;
  align-items: center;
  gap: 9px;
}

.reason__who,
.reason__num {
  color: var(--muted);
  font-size: 9.5px;
}

.reason__num {
  text-align: right;
}

.reason__track {
  height: 3px;
  border-radius: 999px;
  background: var(--line-soft);
  overflow: hidden;
}

.reason__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ffb083, var(--coral));
}

.reason__fill--dot {
  background: linear-gradient(90deg, var(--ink-soft), var(--ink));
}

.reason__body {
  grid-column: 2;
}

.match__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 26px 0 0;
}

.match__skip {
  border: 0;
  background: none;
  color: var(--muted);
  font-size: 12px;
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, var(--line-strong) 70%, transparent);
  text-underline-offset: 4px;
  transition: color 260ms var(--ease-out);
}

.match__skip:hover {
  color: var(--ink);
}

.match__fine {
  max-width: 50em;
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.7;
}

.match__sent {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  margin-top: 26px;
  padding: 16px 18px;
  border: 1px solid color-mix(in srgb, var(--coral) 30%, var(--line));
  border-radius: 16px;
  background: color-mix(in srgb, var(--coral-soft) 62%, var(--paper-raised));
  animation: sent-in 620ms var(--ease-out) both;
}

.match__sent-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--coral);
  color: #fff6e8;
  box-shadow: 0 6px 14px -8px rgba(255, 138, 0, 0.9);
}

.match__sent-copy {
  flex: 1;
  min-width: min(280px, 100%);
}

.match__sent-copy strong {
  display: block;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.match__sent-copy p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}

.match__sent-link {
  color: var(--coral-dark);
  font-size: 11.5px;
  text-decoration: none;
  border-bottom: 1px solid color-mix(in srgb, var(--coral) 45%, transparent);
  padding-bottom: 1px;
  transition: color 220ms var(--ease-out);
}

.match__sent-link:hover {
  color: var(--ink);
}

@keyframes sent-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.match__empty {
  display: grid;
  justify-items: start;
  gap: 10px;
  padding: clamp(28px, 5vw, 56px);
}

.match__empty-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(26px, 4vw, 38px);
  font-weight: 400;
  letter-spacing: -0.02em;
}

.match__empty-text {
  max-width: 34em;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.75;
}

.match__empty-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  margin-top: 8px;
}

/* portraits */
.portrait {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.portrait--me {
  background: var(--coral-soft);
}

.portrait--them {
  background: var(--ink);
}

.portrait__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.08) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.08) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at 50% 70%, #000 12%, transparent 72%);
}

.portrait--them .portrait__grid {
  background-image:
    linear-gradient(to right, rgba(255, 238, 220, 0.09) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 238, 220, 0.09) 1px, transparent 1px);
}

.portrait__init {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--ink);
  font-family: var(--font-display);
  font-size: clamp(72px, 9vw, 108px);
  font-style: normal;
  font-weight: 700;
  line-height: 1;
  transform: translateY(-4%);
}

.portrait--them .portrait__init {
  color: var(--paper);
}

.portrait__rings {
  position: absolute;
  inset: 18%;
  border: 1.5px dashed rgba(54, 54, 54, 0.35);
  border-radius: 50%;
}

.portrait__rings::after {
  position: absolute;
  inset: 16%;
  border: 1.5px dashed rgba(54, 54, 54, 0.2);
  border-radius: 50%;
  content: '';
}

.portrait--them .portrait__rings,
.portrait--them .portrait__rings::after {
  border-color: rgba(255, 246, 232, 0.28);
}

.portrait__tag {
  position: absolute;
  left: 14px;
  bottom: 12px;
  color: rgba(54, 54, 54, 0.5);
  font-size: 7.5px;
  letter-spacing: 0.18em;
}

.portrait--them .portrait__tag {
  color: rgba(246, 232, 216, 0.5);
}

/* how */
.how {
  margin-top: clamp(54px, 7vw, 92px);
  padding-top: clamp(30px, 4vw, 46px);
  border-top: 1px solid var(--line);
}

.how__head {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.how__title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(24px, 3.2vw, 34px);
  font-weight: 400;
  letter-spacing: -0.02em;
}

.how__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 22px;
}

.how__card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: color-mix(in srgb, var(--paper-raised) 72%, transparent);
  transition:
    transform 560ms var(--ease-out),
    border-color 560ms var(--ease-out),
    background-color 560ms var(--ease-out);
}

.how__card:hover {
  transform: translateY(-4px);
  border-color: color-mix(in srgb, var(--coral) 40%, var(--line));
  background: var(--paper-raised);
}

.how__num {
  color: var(--coral-dark);
  font-size: 9px;
  letter-spacing: 0.18em;
}

.how__card h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 500;
}

.how__card p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.72;
}

.how__bars {
  display: flex;
  align-items: flex-end;
  gap: 5px;
  height: 46px;
  margin-top: auto;
  padding-top: 14px;
}

.how__bars span {
  width: 7px;
  border-radius: 999px 999px 0 0;
  background: linear-gradient(180deg, var(--coral), color-mix(in srgb, var(--coral) 30%, var(--paper)));
  opacity: 0.75;
}

.how__flag {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: auto;
  padding-top: 14px;
  color: var(--muted);
  font-size: 10px;
}

.how__flag span {
  width: 16px;
  height: 1px;
  background: var(--coral);
}

.how__pair-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: auto;
  padding-top: 14px;
  color: var(--muted);
}

.how__pair-dots span {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 1px solid var(--line-strong);
}

.how__pair-dots span:nth-child(2) {
  background: var(--coral);
  border-color: var(--coral);
}

.how__pair-dots em {
  margin-left: 6px;
  font-family: var(--font-serif);
  font-size: 11px;
  font-style: italic;
}

@keyframes ring-in {
  from {
    stroke-dasharray: 0 300;
  }
}

@media (max-width: 980px) {
  .match__pair {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .match__side {
    width: min(320px, 100%);
  }

  .match__dial {
    padding: 2px 0 10px;
  }

  .match__dial-rule {
    display: none;
  }

  .match__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .match__stamp {
    writing-mode: horizontal-tb;
  }

  .reason {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .reason__body {
    grid-column: 2;
  }

  .reason__compare {
    grid-column: 2;
    margin-top: 10px;
  }

  .how__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .match__dial {
    display: flex;
    align-items: center;
    gap: 16px;
    text-align: left;
  }

  .match__dial-copy {
    font-size: 11px;
  }

  .match__stage {
    padding: 14px;
    border-radius: 24px;
  }

  .match__side :deep(.profile-card) {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .match__ring-arc {
    animation: none;
    stroke-dasharray: 300 300;
  }

  .how__card {
    transition: none;
  }
}
</style>
