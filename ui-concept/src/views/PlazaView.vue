<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import CircularCarousel from '@/components/fx/CircularCarousel.vue'
import MagneticButton from '@/components/fx/MagneticButton.vue'
import { candidates, DIM_META, type Candidate } from '@/data/mock'

const filters = [
  { id: 'all', label: '全部' },
  { id: 'same', label: '同学院' },
  { id: 'sleep', label: '作息接近' },
  { id: 'redline', label: '红线无冲突' },
  { id: 'story', label: '有自述' },
] as const

type FilterId = (typeof filters)[number]['id']

const activeFilter = ref<FilterId>('all')
const loading = ref(false)
const invited = ref<string[]>([])
const activeIndex = ref(0)
const deckHover = ref(false)
type CarouselApi = {
  focus: (index: number) => void
  next: () => void
  prev: () => void
  nudge: () => void
}

const carousel = ref<CarouselApi | null>(null)
let timer = 0

const list = computed<Candidate[]>(() => {
  const all = [...candidates].sort((a, b) => b.score - a.score)
  if (activeFilter.value === 'same') return all.filter((item) => item.college === '计算机学院')
  if (activeFilter.value === 'sleep') return all.filter((item) => Math.abs(item.dims.sleep - 84) <= 12)
  if (activeFilter.value === 'redline') return all.filter((item) => item.id !== 'su')
  if (activeFilter.value === 'story') return all.filter((item) => item.note.length > 0)
  return all
})

const active = computed<Candidate | undefined>(() => list.value[activeIndex.value] ?? list.value[0])

const cardClass = (index: number): Record<string, boolean> => {
  const total = list.value.length || 1
  const offset = (index - activeIndex.value + total) % total
  const half = total / 2
  return {
    'is-front': offset === 0,
    'is-left': offset > half,
    'is-right': offset > 0 && offset < half,
  }
}

const pad = (value: number): string => String(value).padStart(2, '0')
const ringDash = (score: number): string => `${(score / 100) * 163.4} 163.4`

const invite = (candidate: Candidate): void => {
  if (invited.value.includes(candidate.id)) return
  invited.value = [...invited.value, candidate.id]
}

const reload = (): void => {
  loading.value = true
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    loading.value = false
  }, 1100)
}

watch(list, () => {
  activeIndex.value = 0
})

onBeforeUnmount(() => window.clearTimeout(timer))
</script>

<template>
  <div class="plaza">
    <header class="container plaza__head">
      <div class="plaza__head-copy">
        <p class="eyebrow">Plaza · 广场</p>
        <h1 class="plaza__title">
          <span class="plaza__line"><span class="plaza__line-in">今天有 <em>{{ list.length }}</em> 位同学，</span></span>
          <span class="plaza__line"><span class="plaza__line-in" style="--d: 90ms">和你的习惯对得上。</span></span>
        </h1>
        <p class="plaza__lede">
          按六维与红线排序，不按活跃度。资料只展示对方愿意公开的部分；打招呼需要双方同意。
        </p>
      </div>

      <aside class="plaza__aside" aria-label="本周概览">
        <div class="plaza__stat">
          <span class="plaza__stat-value">12</span>
          <span class="plaza__stat-label">本周新画像</span>
        </div>
        <span class="plaza__stat-rule" aria-hidden="true" />
        <div class="plaza__stat">
          <span class="plaza__stat-value">4</span>
          <span class="plaza__stat-label">红线一致</span>
        </div>
        <span class="plaza__stat-rule" aria-hidden="true" />
        <div class="plaza__stat">
          <span class="plaza__stat-value">0</span>
          <span class="plaza__stat-label">公开联系方式</span>
        </div>
      </aside>
    </header>

    <div class="container toolbar">
      <div class="toolbar__filters" role="tablist" aria-label="筛选">
        <button
          v-for="filter in filters"
          :key="filter.id"
          type="button"
          role="tab"
          class="filter"
          :class="{ 'is-active': activeFilter === filter.id }"
          :aria-selected="activeFilter === filter.id"
          @click="activeFilter = filter.id"
        >
          {{ filter.label }}
        </button>
      </div>

      <div class="toolbar__right">
        <span class="toolbar__count mono">{{ loading ? '——' : list.length }} / {{ candidates.length }}</span>
        <button class="toolbar__reload" type="button" :disabled="loading" @click="reload">
          <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" :class="{ spin: loading }">
            <path
              d="M13.2 8a5.2 5.2 0 1 1-1.6-3.7M13.4 3.2v3.1h-3.1"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          {{ loading ? '加载中' : '重新排序' }}
        </button>
      </div>
    </div>

    <section class="container deck" :aria-busy="loading">
      <div v-if="loading" class="deck__grid deck__grid--loading" aria-label="正在加载">
        <div class="sk-stage">
          <span class="sk-disc" />
          <span class="sk-sweep" />
        </div>
        <div class="sk-panel">
          <span class="sk-line sk-line--title" />
          <span class="sk-line sk-line--sub" />
          <span class="sk-line" />
          <span class="sk-line" />
          <span class="sk-line sk-line--short" />
          <div class="sk-bars">
            <span v-for="bar in 6" :key="bar" />
          </div>
        </div>
      </div>

      <div v-else-if="!list.length" class="empty">
        <p class="empty__title">这个筛选下暂时没有人。</p>
        <p class="empty__text">放宽一个条件，或者去补全自己的画像——画像完整的人更容易被推荐。</p>
        <MagneticButton to="/profile" :padding="90">去补全画像</MagneticButton>
      </div>

      <div v-else class="deck__grid" @pointerenter="deckHover = true" @pointerleave="deckHover = false">
        <p class="sr-only" aria-live="polite">
          {{ active?.name }}，匹配度 {{ active?.score }}%，第 {{ activeIndex + 1 }} 位，共 {{ list.length }} 位
        </p>
        <div class="stage">
          <span class="stage__glow" aria-hidden="true" />
          <div class="stage__head">
            <span class="stage__hint mono">Drag to spin · 左右拖动</span>
            <span class="stage__tag mono">{{ active?.tags[0] ?? '匹配画像' }}</span>
          </div>

          <div class="stage__carousel">
            <CircularCarousel
              ref="carousel"
              v-model:active="activeIndex"
              :items="list"
              :card-width="250"
              :ratio="0.76"
              :gap="36"
              :tilt="-6"
              :speed="3.2"
              :autoplay="deckHover ? 'off' : 'drift'"
              :depth-fade="0.8"
              fade-color="#f3e1c6"
              aria-label="同学画像旋转木马：左右方向键切换，回车查看"
            >
              <template #default="{ item, index }">
                <div class="pcard" :class="cardClass(index)">
                  <span class="pcard__match mono">匹配度</span>
                  <span class="pcard__score mono">{{ item.score }}<em>%</em></span>
                  <div class="pcard__art">
                    <span class="pcard__rings" aria-hidden="true" />
                    <span class="pcard__initial" aria-hidden="true">{{ item.initial }}</span>
                  </div>
                  <div class="pcard__foot">
                    <p class="pcard__name">{{ item.name }}</p>
                    <p class="pcard__college">{{ item.college }} · {{ item.grade }}</p>
                  </div>
                </div>
              </template>
            </CircularCarousel>
          </div>

          <div class="stage__nav">
            <button class="stage__arrow" type="button" aria-label="上一位同学" @click="carousel?.prev()">
              <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
                <path d="M12 4 6 10l6 6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
            <span class="stage__count mono">
              {{ pad(activeIndex + 1) }} <em>/</em> {{ pad(list.length) }}
            </span>
            <button class="stage__arrow" type="button" aria-label="下一位同学" @click="carousel?.next()">
              <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
                <path d="m8 4 6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
        </div>

        <Transition name="swap" mode="out-in">
          <aside v-if="active" :key="active.id" class="panel">
            <div class="panel__top">
              <div class="panel__who">
                <h2 class="panel__name">{{ active.name }}</h2>
                <p class="panel__meta">{{ active.college }} · {{ active.grade }}</p>
              </div>
              <div class="panel__score" :aria-label="`匹配度 ${active.score}%`">
                <svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">
                  <circle cx="32" cy="32" r="26" fill="none" stroke="var(--line-soft)" stroke-width="1.6" />
                  <circle
                    cx="32"
                    cy="32"
                    r="26"
                    fill="none"
                    stroke="var(--coral)"
                    stroke-width="2.2"
                    stroke-linecap="round"
                    :stroke-dasharray="ringDash(active.score)"
                    transform="rotate(-90 32 32)"
                  />
                </svg>
                <span class="panel__score-num">{{ active.score }}<small>%</small></span>
              </div>
            </div>

            <p class="panel__headline">{{ active.headline }}</p>

            <div class="panel__tags">
              <span v-for="tag in active.tags" :key="tag" class="panel__tag">{{ tag }}</span>
            </div>

            <dl class="panel__dims">
              <div v-for="dim in DIM_META" :key="dim.key" class="pdim">
                <dt>{{ dim.label }}</dt>
                <dd>
                  <span class="pdim__track"><span class="pdim__fill" :style="{ width: `${active.dims[dim.key]}%` }" /></span>
                  <span class="pdim__num mono">{{ active.dims[dim.key] }}</span>
                </dd>
              </div>
            </dl>

            <p class="panel__note">{{ active.note }}</p>

            <p class="panel__redline"><span class="mono">红线</span>{{ active.redline }}</p>

            <div class="panel__actions">
              <MagneticButton
                variant="primary"
                size="small"
                :padding="80"
                :strength="3"
                :max-offset="10"
                :disabled="invited.includes(active.id)"
                @click="invite(active)"
              >
                {{ invited.includes(active.id) ? '已打招呼' : '打招呼' }}
              </MagneticButton>
              <RouterLink class="panel__link" to="/profile">看画像 →</RouterLink>
            </div>

            <p class="panel__fine">打招呼需要对方同意；联系方式不会随画像公开。</p>
          </aside>
        </Transition>
      </div>
    </section>

    <section class="container plaza__foot" data-reveal>
      <div class="plaza__note">
        <p class="eyebrow">A quieter way</p>
        <h2 class="plaza__note-title">没有“在线状态”，<br /><em>也没有已读不回。</em></h2>
        <p class="plaza__note-text">
          广场不显示谁刚刚来过。你可以慢慢看完一份画像，再决定要不要开口——对方也一样。
        </p>
        <MagneticButton to="/match" variant="dark" :padding="100">
          看看今天唯一的匹配
        </MagneticButton>
      </div>
      <ul class="plaza__rules">
        <li><span class="mono">01</span>打招呼消耗一次邀请，双方同意后才开放对话。</li>
        <li><span class="mono">02</span>联系方式不会随画像公开，只在确认后出现。</li>
        <li><span class="mono">03</span>任何一方都可以不解释地结束对话。</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.plaza {
  padding-bottom: 24px;
}

/* ---------------------------------------------------------------- head */
.plaza__head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: clamp(24px, 4vw, 56px);
  padding: clamp(28px, 4vw, 52px) 0 20px;
}

.plaza__title {
  margin: 12px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(30px, 4.1vw, 50px);
  font-weight: 500;
  line-height: 1.16;
  letter-spacing: -0.02em;
}

.plaza__line {
  display: block;
  overflow: hidden;
  padding-bottom: 0.06em;
}

.plaza__line-in {
  display: block;
  animation: plaza-rise 950ms var(--ease-out) var(--d, 0ms) both;
}

.plaza__title em {
  color: var(--coral);
  font-style: italic;
}

.plaza__lede {
  max-width: 34em;
  margin: 16px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}

@keyframes plaza-rise {
  from {
    opacity: 0;
    transform: translateY(110%);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.plaza__aside {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 20px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: color-mix(in srgb, var(--paper-raised) 78%, transparent);
}

.plaza__stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.plaza__stat-value {
  font-family: var(--font-serif);
  font-size: 26px;
  line-height: 1;
}

.plaza__stat-label {
  font-size: 10.5px;
  letter-spacing: 0.06em;
  color: var(--muted);
  white-space: nowrap;
}

.plaza__stat-rule {
  width: 1px;
  height: 30px;
  background: var(--line);
}

/* -------------------------------------------------------------- toolbar */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 10px 0 18px;
  border-bottom: 1px solid var(--line-soft);
}

.toolbar__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: color-mix(in srgb, var(--paper-raised) 70%, transparent);
}

.filter {
  flex: none;
  height: 32px;
  padding: 0 14px;
  border: none;
  white-space: nowrap;
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-family: inherit;
  font-size: 12.5px;
  cursor: pointer;
  transition:
    color 260ms var(--ease-out),
    background-color 260ms var(--ease-out);
}

.filter:hover {
  color: var(--ink);
}

.filter.is-active {
  background: var(--ink);
  color: var(--paper);
}

.toolbar__right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.toolbar__count {
  color: var(--muted);
  font-size: 11px;
  letter-spacing: 0.08em;
}

.toolbar__reload {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: transparent;
  color: var(--ink);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
  transition:
    border-color 260ms var(--ease-out),
    transform 360ms var(--ease-out);
}

.toolbar__reload:hover {
  border-color: var(--ink);
  transform: translateY(-1px);
}

.toolbar__reload:disabled {
  cursor: progress;
  opacity: 0.6;
}

.spin {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---------------------------------------------------------------- deck */
.deck {
  padding-top: clamp(20px, 2.6vw, 32px);
}

.deck__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.52fr) minmax(310px, 0.8fr);
  align-items: stretch;
  gap: clamp(20px, 2.6vw, 40px);
}

.stage {
  position: relative;
  display: flex;
  min-height: clamp(460px, 46vw, 560px);
  flex-direction: column;
  border-radius: 26px;
  background:
    radial-gradient(88% 96% at 50% -24%, #ffbd57 0%, #ff9414 24%, rgba(255, 138, 0, 0.62) 56%, rgba(255, 138, 0, 0.12) 82%, transparent 94%),
    radial-gradient(120% 90% at 50% 118%, rgba(0, 0, 0, 0.72), transparent 58%),
    linear-gradient(180deg, #241a12 0%, #17110c 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 220, 180, 0.16),
    0 40px 80px -52px rgba(20, 10, 0, 0.85);
  overflow: hidden;
}

.stage__glow {
  display: none;
}

.stage__head {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 0;
  z-index: 2;
}

.stage__hint,
.stage__tag {
  font-size: 9.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(255, 242, 226, 0.72);
}

.stage__tag {
  padding: 4px 10px;
  border: 1px solid rgba(255, 246, 236, 0.22);
  border-radius: 999px;
  background: rgba(255, 246, 236, 0.1);
  letter-spacing: 0.08em;
  text-transform: none;
}

.stage__carousel {
  position: relative;
  flex: 1;
  min-height: 360px;
}

.stage__nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 0 0 18px;
  z-index: 2;
}

.stage__arrow {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 1px solid rgba(255, 246, 236, 0.14);
  border-radius: 50%;
  background: rgba(24, 17, 11, 0.62);
  color: #fff4e2;
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  cursor: pointer;
  transition:
    transform 360ms var(--ease-out),
    border-color 240ms var(--ease-out),
    background-color 240ms var(--ease-out);
}

.stage__arrow:hover {
  border-color: rgba(255, 246, 236, 0.5);
  background: #fff4e2;
  color: #2e2519;
  transform: translateY(-1px);
}

.stage__arrow:active {
  transform: scale(0.94);
}

.stage__count {
  min-width: 66px;
  color: rgba(255, 244, 226, 0.86);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-align: center;
}

.stage__count em {
  color: rgba(255, 244, 226, 0.42);
  font-style: normal;
}

/* --------------------------------------------------------------- panel */
.panel {
  display: flex;
  height: 100%;
  flex-direction: column;
  gap: 14px;
  padding: clamp(20px, 2.4vw, 28px);
  border: 1px solid var(--line);
  border-radius: 28px;
  background: var(--paper-raised);
  box-shadow: 0 40px 70px -60px rgba(54, 54, 54, 0.7);
}

.panel__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel__name {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 500;
  line-height: 1.2;
}

.panel__meta {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.panel__score {
  position: relative;
  display: grid;
  flex: none;
  width: 64px;
  height: 64px;
  place-items: center;
}

.panel__score svg {
  position: absolute;
  inset: 0;
}

.panel__score-num {
  font-family: var(--font-serif);
  font-size: 19px;
  line-height: 1;
}

.panel__score-num small {
  color: var(--coral-dark);
  font-family: var(--font-sans);
  font-size: 8px;
}

.panel__headline {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 17px;
  line-height: 1.5;
  letter-spacing: -0.005em;
}

.panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.panel__tag {
  padding: 4px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: color-mix(in srgb, var(--ink) 76%, transparent);
  font-size: 10.5px;
  letter-spacing: 0.02em;
}

.panel__dims {
  display: grid;
  grid-template-columns: 1fr;
  gap: 7px;
  margin: 2px 0 0;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}

.pdim {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
}

.pdim dt {
  color: var(--muted);
  font-size: 10.5px;
}

.pdim dd {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 24px;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.pdim__track {
  height: 3px;
  border-radius: 999px;
  background: var(--line-soft);
  overflow: hidden;
}

.pdim__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, color-mix(in srgb, var(--coral) 62%, #ffffff), var(--coral));
}

.pdim__num {
  color: color-mix(in srgb, var(--ink) 66%, transparent);
  font-size: 10px;
  text-align: right;
}

.panel__note {
  margin: 0;
  color: color-mix(in srgb, var(--ink) 74%, transparent);
  font-size: 12.5px;
  line-height: 1.7;
}

.panel__redline {
  display: flex;
  gap: 8px;
  margin: 0;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
  color: color-mix(in srgb, var(--ink) 70%, transparent);
  font-size: 11.5px;
  line-height: 1.6;
}

.panel__redline .mono {
  flex: none;
  color: var(--coral-dark);
  font-size: 9px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding-top: 2px;
}

.panel__actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid var(--line-soft);
}

.panel__link {
  color: var(--ink);
  font-size: 12px;
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, var(--ink) 30%, transparent);
  text-underline-offset: 4px;
}

.panel__fine {
  margin: 0;
  margin-top: 10px;
  color: color-mix(in srgb, var(--muted) 84%, transparent);
  font-size: 10.5px;
  line-height: 1.6;
}

/* ----------------------------------------------------------- transition */
.swap-enter-active,
.swap-leave-active {
  transition:
    opacity 220ms var(--ease-out),
    transform 320ms var(--ease-out);
}

.swap-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ------------------------------------------------------------ skeleton */
.deck__grid--loading {
  min-height: 520px;
}

.sk-stage {
  position: relative;
  border: 2px solid var(--ink);
  border-radius: 26px;
  background:
    radial-gradient(88% 96% at 50% -24%, #ffb347 0%, #ff8a00 26%, rgba(255, 138, 0, 0.42) 58%, transparent 82%),
    linear-gradient(180deg, #3b3833, #211d18);
  box-shadow: 8px 8px 0 var(--ink);
  overflow: hidden;
}

.sk-disc {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 38%;
  aspect-ratio: 0.78;
  border-radius: 18px;
  border: 2px solid color-mix(in srgb, var(--paper) 92%, transparent);
  background: linear-gradient(168deg, #fff4e2 0%, #f6ddb9 58%, #e7c79a 100%);
  transform: translate(-50%, -50%) rotate(-2.4deg);
  box-shadow: 0 40px 70px -44px rgba(0, 0, 0, 0.85);
}

.sk-disc::before {
  content: "";
  position: absolute;
  left: 22%;
  right: 22%;
  top: 16%;
  aspect-ratio: 1;
  border-radius: 50%;
  border: 1.5px dashed rgba(54, 54, 54, 0.28);
}

.sk-disc::after {
  content: "";
  position: absolute;
  left: 12%;
  right: 34%;
  bottom: 16%;
  height: 16px;
  border-radius: 3px;
  background: rgba(54, 54, 54, 0.2);
  box-shadow: 0 34px 0 -2px rgba(54, 54, 54, 0.12);
}

.sk-sweep {
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 30%, rgba(255, 244, 226, 0.22) 50%, transparent 70%);
  transform: translateX(-120%);
  animation: sk-sweep 2s var(--ease-out-soft) infinite;
}

.sk-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 26px;
  border: 2px solid var(--ink);
  border-radius: 4px;
  background: var(--paper-raised);
  box-shadow: 6px 6px 0 var(--ink);
}

.sk-line {
  height: 10px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--sand) 0%, var(--sand-deep) 100%);
}

.sk-line--title {
  width: 44%;
  height: 22px;
}

.sk-line--sub {
  width: 30%;
}

.sk-line--short {
  width: 62%;
}

.sk-bars {
  display: grid;
  gap: 8px;
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid var(--line-soft);
}

.sk-bars span {
  height: 4px;
  border-radius: 999px;
  background: var(--sand);
}

@keyframes sk-sweep {
  0% {
    transform: translateX(-120%);
  }
  60%,
  100% {
    transform: translateX(120%);
  }
}

/* --------------------------------------------------------------- empty */
.empty {
  display: grid;
  justify-items: start;
  gap: 10px;
  padding: 56px 32px;
  border: 1px dashed var(--line-strong);
  border-radius: 28px;
  background: color-mix(in srgb, var(--paper-raised) 60%, transparent);
}

.empty__title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 22px;
}

.empty__text {
  max-width: 34em;
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 13px;
}

/* ----------------------------------------------------------------- foot */
.plaza__foot {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 0.9fr);
  gap: clamp(28px, 5vw, 80px);
  margin-top: clamp(56px, 8vw, 96px);
  padding-top: clamp(36px, 5vw, 56px);
  border-top: 1px solid var(--line);
}

.plaza__note-title {
  margin: 12px 0 0;
  font-family: var(--font-serif);
  font-size: clamp(26px, 3vw, 38px);
  font-weight: 500;
  line-height: 1.3;
  letter-spacing: -0.015em;
}

.plaza__note-title em {
  color: var(--coral);
  font-style: italic;
}

.plaza__note-text {
  max-width: 30em;
  margin: 16px 0 22px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.75;
}

.plaza__rules {
  display: grid;
  align-content: end;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.plaza__rules li {
  display: flex;
  gap: 14px;
  padding: 16px 0;
  border-top: 1px solid var(--line-soft);
  color: color-mix(in srgb, var(--ink) 74%, transparent);
  font-size: 12.5px;
  line-height: 1.65;
}

.plaza__rules li:first-child {
  border-top: none;
}

.plaza__rules .mono {
  flex: none;
  color: var(--coral-dark);
  font-size: 10px;
  letter-spacing: 0.12em;
  padding-top: 2px;
}

/* ------------------------------------------------------------ responsive */
@media (max-width: 1080px) {
  .deck__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .panel {
    order: 2;
  }

  .stage {
    min-height: 440px;
  }
}

@media (max-width: 900px) {
  .plaza__head {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
  }

  .plaza__aside {
    justify-self: start;
  }
}

@media (max-width: 620px) {
  .plaza__head {
    padding-top: 22px;
  }

  .plaza__aside {
    gap: 12px;
    padding: 12px 14px;
  }

  .plaza__stat-value {
    font-size: 22px;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .toolbar__filters {
    overflow-x: auto;
    flex-wrap: nowrap;
    justify-content: flex-start;
    border-radius: 18px;
    scrollbar-width: none;
  }

  .toolbar__filters::-webkit-scrollbar {
    display: none;
  }

  .filter {
    padding: 0 12px;
  }

  .toolbar__right {
    justify-content: space-between;
  }

  .stage {
    min-height: 400px;
    border-radius: 26px;
  }

  .stage__head {
    padding: 14px 16px 0;
  }

  .stage__carousel {
    min-height: 290px;
  }

  .panel {
    padding: 18px;
    border-radius: 24px;
  }

  .plaza__foot {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .plaza__line-in {
    animation: none;
  }

  .sk-sweep {
    animation: none;
  }

  .swap-enter-active,
  .swap-leave-active {
    transition: none;
  }
}
</style>
