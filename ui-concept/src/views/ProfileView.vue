<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import MagneticButton from '@/components/fx/MagneticButton.vue'
import ProfileCard from '@/components/profile/ProfileCard.vue'
import { DIM_META, dimAverage, me } from '@/data/mock'

const mounted = ref(false)
onMounted(() => {
  requestAnimationFrame(() => {
    mounted.value = true
  })
})

const todos = ref([
  { id: 'noise', label: '补一条“你能接受的最大噪声”', done: false },
  { id: 'spend', label: '补一条消费习惯（AA / 轮流请）', done: false },
])
const justSaved = ref('')
let savedTimer = 0

const completeness = computed(() => {
  const bonus = todos.value.filter((item) => item.done).length * 4
  return Math.min(100, me.completeness + bonus)
})

const remaining = computed(() => todos.value.filter((item) => !item.done).length)
const avg = computed(() => dimAverage(me.dims))

const complete = (id: string): void => {
  const target = todos.value.find((item) => item.id === id)
  if (!target || target.done) return
  target.done = true
  justSaved.value = '已保存，画像完整度更新了'
  window.clearTimeout(savedTimer)
  savedTimer = window.setTimeout(() => {
    justSaved.value = ''
  }, 2600)
}

const RING = 2 * Math.PI * 54
const ringOffset = computed(() => (mounted.value ? RING * (1 - completeness.value / 100) : RING))

const visibility = ref<Record<string, string>>({
  dims: '公开',
  redlines: '仅自己',
  contact: '确认后',
})

const cycle = (key: string): void => {
  const order = ['公开', '仅自己', '确认后']
  const current = order.indexOf(visibility.value[key] ?? '公开')
  visibility.value[key] = order[(current + 1) % order.length] as string
}
</script>

<template>
  <div class="profile">
    <section class="container identity">
      <header class="identity__head">
        <p class="eyebrow">My profile · 我的画像</p>
        <h1 class="identity__title">别人看到的，<br /><em>和你看到的。</em></h1>
        <p class="identity__lede">
          画像不是简历。它只回答一个问题：和你住在一起，日常会是什么样。红色标注的内容永远不会出现在别人的页面上。
        </p>

        <div class="identity__actions">
          <MagneticButton :padding="110" :strength="2.4" @click="complete(todos[0]!.id)">
            继续完善画像
          </MagneticButton>
          <RouterLink class="identity__link" to="/plaza">看看别人怎么写 →</RouterLink>
        </div>

        <ul class="identity__todo">
          <li v-for="item in todos" :key="item.id" :class="{ 'is-done': item.done }">
            <span class="todo__dot" aria-hidden="true" />
            <span class="todo__label">{{ item.label }}</span>
            <button v-if="!item.done" type="button" class="todo__btn" @click="complete(item.id)">补上</button>
            <span v-else class="todo__done mono">DONE</span>
          </li>
        </ul>
        <p class="identity__saved" role="status" aria-live="polite">{{ justSaved }}</p>
      </header>

      <div class="identity__card">
        <span class="identity__orb" aria-hidden="true" />
        <ProfileCard
          :name="me.name"
          :title="`${me.college} · ${me.grade}`"
          :handle="`@${me.handle}`"
          :status="`画像完成度 ${completeness}%`"
          contact-text="编辑画像"
          :initial="me.initial"
          theme="light"
          :radius="22"
          :holo="0.45"
          :glare="0.5"
          :tilt-strength="7"
          :parallax="12"
          @contact="complete(todos[0]!.id)"
        >
          <template #portrait>
            <div class="idcard">
              <span class="idcard__grid" aria-hidden="true" />
              <span class="idcard__ring" aria-hidden="true" />
              <span class="idcard__ring idcard__ring--in" aria-hidden="true" />
              <span class="idcard__mono mono">ANONYMOUS · COHABIT</span>
              <span class="idcard__init">{{ me.initial }}</span>
            </div>
          </template>
        </ProfileCard>
        <p class="identity__caption mono">真实姓名不外露 · 联系方式需双方同意</p>
      </div>
    </section>

    <section class="container stats" aria-label="画像概览">
      <article class="stat stat--ring">
        <div class="stat__ring">
          <svg viewBox="0 0 120 120" width="120" height="120" aria-hidden="true">
            <circle cx="60" cy="60" r="54" fill="none" stroke="var(--line-soft)" stroke-width="2" />
            <circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke="var(--coral)"
              stroke-width="2.4"
              stroke-linecap="round"
              :stroke-dasharray="RING"
              :stroke-dashoffset="ringOffset"
              transform="rotate(-90 60 60)"
              class="stat__arc"
            />
          </svg>
          <span class="stat__ring-num">{{ completeness }}<small>%</small></span>
        </div>
        <div class="stat__copy">
          <p class="stat__label mono">COMPLETENESS</p>
          <h2 class="stat__title">还差 {{ remaining }} 项，就能被别人搜到。</h2>
          <p class="stat__note">完整度低于 70% 时不会进入广场推荐。补充自述比补数字更有效。</p>
        </div>
      </article>

      <article class="stat-stat">
        <div class="stat__mini">
          <span class="stat__mini-num">{{ avg }}</span>
          <span class="stat__mini-label">六维均分</span>
        </div>
        <span class="stat__rule" aria-hidden="true" />
        <div class="stat__mini">
          <span class="stat__mini-num">12</span>
          <span class="stat__mini-label">本周被查看</span>
        </div>
        <span class="stat__rule" aria-hidden="true" />
        <div class="stat__mini">
          <span class="stat__mini-num">2</span>
          <span class="stat__mini-label">收到的邀请</span>
        </div>
      </article>
    </section>

    <section class="container dims" data-reveal>
      <div class="block-head">
        <div>
          <p class="eyebrow">Six dimensions</p>
          <h2 class="block-title">六维画像</h2>
        </div>
        <p class="block-note">越靠右代表越接近“你希望室友做到的样子”，不是你自评的绝对分。</p>
      </div>

      <div class="dims__grid">
        <div v-for="(dim, index) in DIM_META" :key="dim.key" class="dim" :style="{ '--i': index }">
          <div class="dim__top">
            <span class="dim__label">{{ dim.label }}</span>
            <span class="dim__num mono">{{ me.dims[dim.key] }}</span>
          </div>
          <span class="dim__track">
            <span class="dim__fill" :style="{ width: mounted ? `${me.dims[dim.key]}%` : '0%' }" />
          </span>
          <span class="dim__hint">{{ dim.key === 'sleep' ? '23:30 熄灯' : dim.key === 'clean' ? '一周两次值日' : '由问卷推算' }}</span>
        </div>
      </div>
    </section>

    <section class="container public" data-reveal>
      <div class="block-head">
        <div>
          <p class="eyebrow">Visible to others</p>
          <h2 class="block-title">公开内容</h2>
        </div>
        <span class="block-state block-state--open">别人能看到</span>
      </div>

      <div class="public__grid">
        <div class="public__tags">
          <p class="public__label mono">TAGS</p>
          <div class="tags">
            <span v-for="tag in me.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </div>

        <div class="prompts">
          <article v-for="(prompt, index) in me.prompts" :key="prompt.title" class="prompt" :style="{ '--i': index }">
            <p class="prompt__index mono">0{{ index + 1 }}</p>
            <h3 class="prompt__title">{{ prompt.title }}</h3>
            <p class="prompt__text">{{ prompt.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="container private" data-reveal>
      <div class="block-head">
        <div>
          <p class="eyebrow">Only you</p>
          <h2 class="block-title">只有自己可见</h2>
        </div>
        <span class="block-state block-state--closed">不会出现在别人的页面</span>
      </div>

      <div class="private__grid">
        <div class="redlines">
          <p class="public__label mono">RED LINES · 一票否决</p>
          <ol class="redline-list">
            <li v-for="(line, index) in me.redlines" :key="line">
              <span class="mono">0{{ index + 1 }}</span>{{ line }}
            </li>
          </ol>
          <p class="redlines__note">红线只用于匹配计算，对方永远不会看到你的红线原文。</p>
        </div>

        <div class="contact">
          <p class="public__label mono">CONTACT</p>
          <div class="contact__masked" aria-label="联系方式在双方确认后显示">
            <span class="contact__blur" aria-hidden="true">wxid_linzhixia_2026</span>
            <span class="contact__lock">
              <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
                <rect x="3" y="7" width="10" height="7" rx="2" fill="none" stroke="currentColor" stroke-width="1.3" />
                <path d="M5.5 7V5.4a2.5 2.5 0 0 1 5 0V7" fill="none" stroke="currentColor" stroke-width="1.3" />
              </svg>
              双方同意后显示
            </span>
          </div>
          <p class="contact__note">对话框里也会再确认一次，避免误发。</p>
        </div>
      </div>

      <div class="visibility">
        <div v-for="row in [
          { key: 'dims', label: '六维画像', hint: '只显示维度，不显示原始答案' },
          { key: 'redlines', label: '三条红线', hint: '仅用于匹配，不对外展示' },
          { key: 'contact', label: '联系方式', hint: '默认在双方同意后出现' },
        ]" :key="row.key" class="visibility__row">
          <span class="visibility__label">{{ row.label }}<small>{{ row.hint }}</small></span>
          <button type="button" class="visibility__pill" @click="cycle(row.key)">
            {{ visibility[row.key] }}
            <span class="visibility__swap mono">切换</span>
          </button>
        </div>
      </div>
    </section>

    <section class="container profile__foot">
      <p class="profile__foot-text">资料随时可以改，改完立刻生效。对方看到的是最新版本。</p>
      <MagneticButton to="/plaza" variant="dark" :padding="110">看看谁和你对得上</MagneticButton>
    </section>
  </div>
</template>

<style scoped>
.profile {
  padding-bottom: 40px;
}

.identity {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(280px, 0.7fr);
  align-items: start;
  gap: clamp(28px, 5vw, 64px);
  padding: clamp(34px, 5vw, 60px) 0 clamp(24px, 3vw, 36px);
}

.identity__head {
  padding-top: 6px;
}

.identity__title {
  margin: 12px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(34px, 4.6vw, 56px);
  font-weight: 400;
  letter-spacing: -0.03em;
  line-height: 1.12;
}

.identity__title em {
  color: var(--coral);
  font-style: italic;
}

.identity__lede {
  max-width: 34em;
  margin: 16px 0 0;
  color: var(--muted);
  font-size: 13.5px;
  line-height: 1.78;
}

.identity__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-top: 22px;
}

.identity__link {
  color: var(--muted);
  font-size: 12px;
  transition: color 260ms var(--ease-out);
}

.identity__link:hover {
  color: var(--coral-dark);
}

.identity__todo {
  display: grid;
  gap: 0;
  max-width: 30em;
  margin: 24px 0 0;
  padding: 0;
  border-top: 1px solid var(--line);
  list-style: none;
}

.identity__todo li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--line-soft);
  color: var(--muted);
  font-size: 12px;
  transition: opacity 320ms var(--ease-out);
}

.identity__todo li.is-done {
  opacity: 0.55;
}

.todo__dot {
  width: 5px;
  height: 5px;
  flex: none;
  border-radius: 50%;
  background: var(--coral);
}

.is-done .todo__dot {
  background: var(--line-strong);
}

.todo__label {
  flex: 1;
  min-width: 0;
}

.is-done .todo__label {
  text-decoration: line-through;
  text-decoration-color: var(--line-strong);
}

.todo__btn {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 10px;
  background: transparent;
  color: var(--ink);
  font-size: 10.5px;
  transition: border-color 240ms var(--ease-out), background-color 240ms var(--ease-out);
}

.todo__btn:hover {
  border-color: var(--coral);
  background: var(--coral-soft);
}

.todo__done {
  color: var(--coral-dark);
  font-size: 8.5px;
  letter-spacing: 0.16em;
}

.identity__saved {
  height: 16px;
  margin: 8px 0 0;
  color: var(--coral-dark);
  font-size: 11px;
}

.identity__card {
  position: relative;
  display: grid;
  justify-items: center;
  padding: clamp(18px, 3vw, 30px) 0;
}

.identity__card :deep(.profile-card) {
  width: min(296px, 100%);
}

.identity__caption {
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 9.4px;
  letter-spacing: 0.1em;
  text-align: center;
}

.identity__orb {
  position: absolute;
  top: 4%;
  left: 50%;
  width: 76%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 34%, rgba(255, 138, 0, 0.22), rgba(255, 138, 0, 0) 68%);
  filter: blur(6px);
  transform: translateX(-50%);
  pointer-events: none;
}

.idcard {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--coral-soft);
}

.idcard__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(54, 54, 54, 0.07) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(54, 54, 54, 0.07) 1px, transparent 1px);
  background-size: 26px 26px;
  mask-image: radial-gradient(circle at 50% 66%, #000 14%, transparent 74%);
}

.idcard__ring {
  position: absolute;
  top: 16%;
  left: 50%;
  width: 58%;
  aspect-ratio: 1;
  border: 1.5px dashed rgba(54, 54, 54, 0.4);
  border-radius: 50%;
  transform: translateX(-50%);
}

.idcard__ring--in {
  top: 24%;
  width: 42%;
  border-color: rgba(54, 54, 54, 0.12);
}

.idcard__mono {
  position: absolute;
  top: 14px;
  left: 16px;
  color: color-mix(in srgb, var(--ink) 52%, transparent);
  font-size: 7px;
  letter-spacing: 0.2em;
}

.idcard__init {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--ink);
  font-family: var(--font-display);
  font-size: clamp(76px, 9vw, 104px);
  font-style: normal;
  font-weight: 700;
  line-height: 1;
  transform: translateY(-6%);
}

/* stats */
.stats {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 14px;
}

.stat--ring {
  display: flex;
  align-items: center;
  gap: clamp(16px, 3vw, 26px);
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: var(--paper-raised);
}

.stat__ring {
  position: relative;
  display: grid;
  width: 120px;
  height: 120px;
  flex: none;
  place-items: center;
}

.stat__ring svg {
  position: absolute;
  inset: 0;
}

.stat__arc {
  transition: stroke-dashoffset 1400ms var(--ease-out);
}

.stat__ring-num {
  font-family: var(--font-serif);
  font-size: 28px;
  letter-spacing: -0.03em;
}

.stat__ring-num small {
  color: var(--muted);
  font-family: var(--font-sans);
  font-size: 10px;
}

.stat__label {
  margin: 0;
  color: var(--muted);
  font-size: 8.5px;
  letter-spacing: 0.18em;
}

.stat__title {
  margin: 6px 0 6px;
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 500;
  line-height: 1.4;
}

.stat__note {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.66;
}

.stat-stat {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 8px;
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: color-mix(in srgb, var(--paper-deep) 44%, var(--paper));
}

.stat__mini {
  display: grid;
  justify-items: center;
  gap: 3px;
}

.stat__mini-num {
  font-family: var(--font-serif);
  font-size: 26px;
  letter-spacing: -0.02em;
}

.stat__mini-label {
  color: var(--muted);
  font-size: 10px;
  white-space: nowrap;
}

.stat__rule {
  width: 1px;
  height: 30px;
  background: var(--line);
}

/* shared blocks */
.block-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}

.block-title {
  margin: 6px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(22px, 2.8vw, 30px);
  font-weight: 400;
  letter-spacing: -0.02em;
}

.block-note {
  max-width: 26em;
  margin: 0;
  color: var(--muted);
  font-size: 10.5px;
  line-height: 1.66;
  text-align: right;
}

.block-state {
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 10px;
  white-space: nowrap;
}

.block-state--open {
  background: var(--ink);
  color: var(--paper);
}

.block-state--closed {
  border: 1px solid var(--line-strong);
  color: var(--muted);
}

/* dims */
.dims {
  margin-top: clamp(44px, 6vw, 72px);
}

.dims__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 34px;
  padding-top: 22px;
}

.dim__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.dim__label {
  font-size: 12.5px;
}

.dim__num {
  color: var(--muted);
  font-size: 10px;
}

.dim__track {
  display: block;
  height: 4px;
  margin-top: 8px;
  border-radius: 999px;
  background: var(--line-soft);
  overflow: hidden;
}

.dim__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ffc178, var(--coral) 78%, var(--coral-dark));
  transition: width 1200ms var(--ease-out);
  transition-delay: calc(var(--i) * 70ms + 200ms);
}

.dim__hint {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: 9.5px;
}

/* public */
.public {
  margin-top: clamp(44px, 6vw, 72px);
}

.public__grid {
  display: grid;
  gap: 22px;
  padding-top: 18px;
}

.public__label {
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 8.5px;
  letter-spacing: 0.18em;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.tag {
  padding: 5px 12px;
  border: 1px solid color-mix(in srgb, var(--line-strong) 64%, transparent);
  border-radius: 999px;
  background: color-mix(in srgb, var(--paper-raised) 60%, transparent);
  font-size: 11.5px;
  transition:
    border-color 300ms var(--ease-out),
    background-color 300ms var(--ease-out),
    transform 380ms var(--ease-out);
}

.tag:hover {
  border-color: var(--coral);
  background: var(--coral-soft);
  transform: translateY(-2px);
}

.prompts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid var(--line);
}

.prompt {
  padding: 18px 18px 4px 0;
  border-right: 1px solid var(--line-soft);
}

.prompt:last-child {
  border-right: 0;
}

.prompt__index {
  margin: 0;
  color: var(--coral-dark);
  font-size: 8.5px;
  letter-spacing: 0.18em;
}

.prompt__title {
  margin: 8px 0 6px;
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 500;
  line-height: 1.45;
}

.prompt__text {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.72;
}

/* private */
.private {
  margin-top: clamp(44px, 6vw, 72px);
}

.private__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: 18px;
  padding: 22px 0 0;
}

.redlines,
.contact {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: color-mix(in srgb, var(--paper-deep) 40%, var(--paper));
}

.redline-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: none;
}

.redline-list li {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid var(--line-soft);
  font-size: 12.5px;
}

.redline-list li:last-child {
  border-bottom: 0;
}

.redline-list .mono {
  color: var(--coral-dark);
  font-size: 8.5px;
  letter-spacing: 0.14em;
}

.redlines__note,
.contact__note {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.6;
}

.contact__masked {
  position: relative;
  display: grid;
  min-height: 78px;
  place-items: center;
  border: 1px dashed var(--line-strong);
  border-radius: 14px;
  overflow: hidden;
}

.contact__blur {
  color: var(--muted);
  font-family: var(--font-mono, monospace);
  font-size: 15px;
  letter-spacing: 0.04em;
  filter: blur(5px);
  opacity: 0.6;
  user-select: none;
}

.contact__lock {
  position: absolute;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--paper-raised) 88%, transparent);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.9) inset;
  font-size: 10px;
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}

.visibility {
  margin-top: 18px;
  border-top: 1px solid var(--line);
}

.visibility__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 0;
  border-bottom: 1px solid var(--line-soft);
}

.visibility__label {
  display: grid;
  gap: 2px;
  font-size: 12.5px;
}

.visibility__label small {
  color: var(--muted);
  font-size: 10px;
}

.visibility__pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--paper-raised);
  font-size: 11px;
  transition:
    border-color 300ms var(--ease-out),
    transform 380ms var(--ease-spring);
}

.visibility__pill:hover {
  border-color: var(--coral);
}

.visibility__pill:active {
  transform: scale(0.95);
}

.visibility__swap {
  color: var(--muted);
  font-size: 8px;
  letter-spacing: 0.14em;
}

.profile__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: clamp(44px, 6vw, 70px);
  padding-top: 26px;
  border-top: 1px solid var(--line);
}

.profile__foot-text {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 980px) {
  .identity {
    grid-template-columns: 1fr;
  }

  .identity__card {
    padding-top: 4px;
  }

  .identity__card :deep(.profile-card) {
    width: min(280px, 84%);
  }

  .stats {
    grid-template-columns: 1fr;
  }

  .prompts {
    grid-template-columns: 1fr;
  }

  .prompt {
    padding: 16px 0;
    border-right: 0;
    border-bottom: 1px solid var(--line-soft);
  }

  .private__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 620px) {
  .dims__grid {
    grid-template-columns: 1fr;
  }

  .block-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .block-note {
    text-align: left;
  }

  .stat--ring {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dim__fill,
  .stat__arc {
    transition: none;
  }
}
</style>
