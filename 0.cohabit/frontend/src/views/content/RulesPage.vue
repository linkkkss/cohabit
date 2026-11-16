<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * 规则说明（/rules，公开页）：匹配规则、红线、兜底与隐私承诺。
 * 静态内容，来源 docs/02、docs/03 §5/§8、docs/05 §7；不收集任何联系方式。
 */
const DIM_WEIGHTS = [
  { label: '作息', value: 20 },
  { label: '整洁', value: 20 },
  { label: '社交', value: 15 },
  { label: '声音', value: 15 },
  { label: '边界', value: 15 },
  { label: '开销', value: 15 },
]

const TIMELINE = [
  { step: '邀请 / 申请', detail: '看到合适的人或寝室后发起请求，留言里不要写联系方式。' },
  { step: '对方回应', detail: '请求在 48 小时内有效；接受后进入联系方式阶段，拒绝则关闭。' },
  { step: '联系方式', detail: '双方同意后，各自勾选公开的联系方式才会对对方可见，7 天内有效。' },
  { step: '确认同住', detail: '双方在 48 小时内确认，寝室成立；任何一方超时未确认，请求自动关闭。' },
]
</script>

<template>
  <article class="container content-page rules-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Rules</p>
        <h1>规则说明</h1>
        <p class="lede">
          Cohabit 只做一件事：让同校学生在搬进同一间寝室之前，把作息、整洁、声音和边界聊清楚。下面是匹配与安全规则。
        </p>
      </div>
    </header>

    <nav class="content-toc" aria-label="页内导航">
      <a href="#match">匹配规则</a>
      <a href="#redline">红线</a>
      <a href="#timeline">组寝流程</a>
      <a href="#safety">举报与拉黑</a>
      <a href="#fallback">找不到人时</a>
      <a href="#privacy">隐私承诺</a>
    </nav>

    <section id="match" class="card content-card">
      <h2>匹配分怎么算</h2>
      <p>
        六维画像来自问卷，每一项换算成 0–100 的分数。两个人的同一维度越接近，这一项得分越高；再按权重加总，得到基础分。
      </p>
      <ul class="weight-list">
        <li v-for="dim in DIM_WEIGHTS" :key="dim.label">
          <span>{{ dim.label }}</span>
          <span class="weight-value">{{ dim.value }}%</span>
        </li>
      </ul>
      <p>
        有共同标签时，每个标签加 2 分，最多加 6 分。标签只加分，不扣分；边界分歧交给红线单独提示。
      </p>
      <p class="fine">
        匹配分只是参考，不是录取线。分数高不代表一定合得来，分数低也不代表不能聊；最终由你们自己决定。
      </p>
    </section>

    <section id="redline" class="card content-card">
      <h2>红线：先说不接受什么</h2>
      <p>
        红线是你主动声明的“不可接受项”，例如不能接受吸烟、打鼾、频繁带人回寝。它不是系统替你做的判断，也不会把你不想看到的人直接藏起来。
      </p>
      <ul class="rules-list">
        <li>对方踩中你的红线时，匹配分会被扣减，并且分数最高只到 59。</li>
        <li>列表和详情会用琥珀色提示冲突原因，但不会替你拉黑对方。</li>
        <li>红线冲突时发起请求会再次确认，避免手滑。</li>
        <li>已经同住的寝室，不会因为后来发现红线冲突而自动解散。</li>
      </ul>
      <p class="fine">空着不选，表示目前没有红线；之后可以在画像里补充。</p>
    </section>

    <section id="timeline" class="card content-card">
      <h2>一次组寝的完整流程</h2>
      <ol class="timeline-list">
        <li v-for="item in TIMELINE" :key="item.step">
          <p class="timeline-step">{{ item.step }}</p>
          <p class="timeline-detail">{{ item.detail }}</p>
        </li>
      </ol>
      <p class="fine">
        所有请求都有时间窗。窗口结束会自动关闭并留下记录，避免“挂着不回”消耗双方。
      </p>
    </section>

    <section id="safety" class="card content-card">
      <h2>举报与拉黑</h2>
      <p>
        遇到骚扰、索要联系方式、广告或让你不舒服的留言，可以直接举报或拉黑，不需要先解释。
      </p>
      <ul class="rules-list">
        <li>举报会提交给管理员，对方不会收到“你举报了我”的通知。</li>
        <li>每个账号每天最多举报 10 次，超过后会提示稍后再试。</li>
        <li>拉黑会立即关闭双方进行中的组寝请求，并阻止对方再次邀请你。</li>
        <li>拉黑不会解散已经成立的寝室；同住问题请先联系房主或管理员处理。</li>
        <li>拉黑可以随时在设置页解除；解除后不会自动恢复之前关闭的请求。</li>
      </ul>
      <p>
        <RouterLink class="text-link" to="/settings">去设置页管理拉黑列表</RouterLink>
      </p>
    </section>

    <section id="fallback" class="card content-card">
      <h2>找不到合适的人时</h2>
      <ul class="rules-list">
        <li>去组寝广场看看还有空位的寝室，直接申请加入。</li>
        <li>补全画像：标签、自述和红线越完整，匹配理由越具体。</li>
        <li>调整筛选条件，别把年级、学院或性别卡得太窄。</li>
        <li>仍然没有结果时，可以先向合适的人发起邀请；双方确认后会自动成立新的寝室。</li>
      </ul>
      <p class="fine">平台不保证一定匹配成功，也不替双方做同住决定。</p>
    </section>

    <section id="privacy" class="card content-card">
      <h2>隐私承诺</h2>
      <ul class="rules-list">
        <li>联系方式只在双方同意后可见，且只展示你勾选公开的那几项。</li>
        <li>公开摘要、匹配卡片、寝室广场和通知里都不会出现 QQ、微信或手机号。</li>
        <li>请勿在自述、留言或举报内容里填写联系方式；看到别人这样做，可以举报。</li>
        <li>注销账号会停用登录、关闭进行中的请求并清理联系方式。</li>
      </ul>
      <p>
        更细的数据用途和删除方式见
        <RouterLink class="text-link" to="/privacy">隐私说明</RouterLink>。
      </p>
    </section>

    <footer class="content-foot">
      <p class="fine">规则可能随产品调整；有疑问可以通过站内举报入口留言给管理员。</p>
      <RouterLink class="btn btn-ghost" to="/">返回首页</RouterLink>
    </footer>
  </article>
</template>

<style scoped>
.content-page {
  display: grid;
  gap: 16px;
  padding-bottom: 56px;
}

.content-page .page-head {
  margin-bottom: 0;
}

.content-toc {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  border-block: 1px solid var(--line);
  padding: 10px 0;
}

.content-toc a {
  color: var(--muted);
  font-size: 13px;
  text-decoration: none;
}

.content-toc a:hover {
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.content-card {
  display: grid;
  gap: 12px;
  margin: 0;
}

.content-card h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(22px, 3vw, 28px);
  font-weight: 500;
  letter-spacing: normal;
}

.content-card p {
  margin: 0;
  font-size: 15px;
  line-height: 1.75;
}

.weight-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.weight-list li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 10px;
  font-size: 13px;
}

.weight-value {
  color: var(--coral-dark);
  font-variant-numeric: tabular-nums;
}

.rules-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 20px;
  font-size: 15px;
  line-height: 1.7;
}

.timeline-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: step;
}

.timeline-list li {
  position: relative;
  border-left: 1px solid var(--line);
  padding: 0 0 16px 20px;
  counter-increment: step;
}

.timeline-list li:last-child {
  padding-bottom: 0;
}

.timeline-list li::before {
  position: absolute;
  top: 2px;
  left: -11px;
  display: grid;
  place-items: center;
  width: 21px;
  height: 21px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--paper);
  color: var(--coral-dark);
  font-size: 11px;
  content: counter(step);
}

.timeline-step {
  font-family: var(--font-serif);
  font-size: 17px;
}

.timeline-detail {
  color: var(--muted);
  font-size: 14px !important;
}

.text-link {
  color: var(--coral-dark);
  text-underline-offset: 3px;
}

.content-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.content-foot .fine {
  margin: 0;
}

@media (max-width: 640px) {
  .weight-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-card p,
  .rules-list {
    font-size: 15px;
  }

  .content-foot {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
