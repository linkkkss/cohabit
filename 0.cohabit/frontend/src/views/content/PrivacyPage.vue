<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * 隐私说明（/privacy，公开页）：收集什么、怎么用、联系方式分级、保留与删除。
 * 静态内容，来源 docs/02 §8/§9、docs/03、docs/04；不在页面里收集任何联系方式。
 */
const CONTACT_LEVELS = [
  {
    title: '公开页面',
    detail: '匹配卡片、寝室广场、公开摘要里只有昵称、年级、学院、专业、标签和自述，不包含 QQ、微信、手机号。',
  },
  {
    title: '本人查看',
    detail: '设置页里的联系方式只对你自己可见，并始终脱敏展示；可以随时修改或关闭某一项的公开开关。',
  },
  {
    title: '连接解锁',
    detail: '只有双方同意、进入联系方式阶段后，对方才能看到你勾选公开的那几项；请求关闭或过期后立即隐藏。',
  },
  {
    title: '通知与导出',
    detail: '通知内容不包含联系方式；管理员导出用户与画像时排除邮箱、密码和联系方式。',
  },
]
</script>

<template>
  <article class="container content-page privacy-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Privacy</p>
        <h1>隐私说明</h1>
        <p class="lede">
          我们只收集组寝需要的信息：你是谁、你的生活习惯、你们怎么联系。联系方式默认不公开，只在双方同意后出现。
        </p>
      </div>
    </header>

    <nav class="content-toc" aria-label="页内导航">
      <a href="#collect">收集什么</a>
      <a href="#use">用来做什么</a>
      <a href="#contact">联系方式分级</a>
      <a href="#retention">保留与删除</a>
      <a href="#choices">你的选择</a>
      <a href="#tech">技术说明</a>
    </nav>

    <section id="collect" class="card content-card">
      <h2>我们收集什么</h2>
      <ul class="rules-list">
        <li><strong>账号</strong>：邮箱（用于登录与验证码）、密码摘要、账号状态。</li>
        <li><strong>基础资料</strong>：昵称、性别、年级、学院、专业。</li>
        <li><strong>画像</strong>：问卷答案、六维分数、标签、红线、自述。</li>
        <li><strong>可选联系方式</strong>：QQ、微信、手机号，以及每一项是否对解锁后的对方展示。</li>
        <li><strong>组寝记录</strong>：请求、寝室、成员关系、状态变化。</li>
        <li><strong>安全记录</strong>：举报内容、拉黑关系、管理员处理与审计记录。</li>
      </ul>
      <p class="fine">不收集身份证号、学号、通讯录、精确位置或相册内容。</p>
    </section>

    <section id="use" class="card content-card">
      <h2>用来做什么</h2>
      <ul class="rules-list">
        <li>计算六维契合度、生成匹配理由与红线冲突提示。</li>
        <li>完成邀请、申请、联系方式解锁、确认同住等流程。</li>
        <li>发送与组寝有关的站内通知，例如收到请求、窗口即将结束。</li>
        <li>处理举报、拉黑与账号安全问题。</li>
        <li>排查故障和统计产品使用情况；统计结果不包含联系方式。</li>
      </ul>
      <p>不把信息用于广告投放，也不出售给第三方。</p>
    </section>

    <section id="contact" class="card content-card">
      <h2>联系方式分级</h2>
      <div class="level-list">
        <article v-for="level in CONTACT_LEVELS" :key="level.title" class="level-item">
          <h3>{{ level.title }}</h3>
          <p>{{ level.detail }}</p>
        </article>
      </div>
      <p class="fine">
        请勿在自述、留言或举报里填写联系方式。看到别人这样做，可以举报；这是平台目前识别联系方式泄漏的主要方式。
      </p>
    </section>

    <section id="retention" class="card content-card">
      <h2>保留与删除</h2>
      <ul class="rules-list">
        <li>已读通知保留 90 天，未读通知保留 180 天，之后由定时任务清理。</li>
        <li>组寝请求与寝室状态记录会保留，用于处理纠纷和审计。</li>
        <li>管理员操作审计永久保留，不随账号注销删除。</li>
        <li>注销账号会停用登录、清理联系方式、关闭进行中的请求；房主注销时会解散其寝室。</li>
        <li>注销无法在页面内恢复；如需重新使用，需要联系管理员。</li>
      </ul>
    </section>

    <section id="choices" class="card content-card">
      <h2>你的选择</h2>
      <ul class="rules-list">
        <li>在设置页修改昵称、年级、学院和专业。</li>
        <li>在联系方式区块修改 QQ、微信、手机号，或关闭某一项的展示开关。</li>
        <li>在设置页查看拉黑列表并解除拉黑。</li>
        <li>遇到骚扰、索要联系方式或广告，直接举报或拉黑。</li>
        <li>随时注销账号，或联系管理员处理无法自助完成的事项。</li>
      </ul>
      <p>
        <RouterLink class="text-link" to="/settings">打开设置</RouterLink>
        ·
        <RouterLink class="text-link" to="/rules">查看规则说明</RouterLink>
      </p>
    </section>

    <section id="tech" class="card content-card">
      <h2>技术说明</h2>
      <ul class="rules-list">
        <li>登录凭证使用 HttpOnly Cookie 保存刷新令牌，访问令牌只放在页面内存里，不写入浏览器存储。</li>
        <li>页面通过 HTTPS 传输；生产环境不在前端日志里输出个人信息。</li>
        <li>不使用第三方广告或行为追踪脚本。</li>
        <li>公开接口只返回公开展示所需的字段，通知内容同样不携带联系方式。</li>
      </ul>
    </section>

    <footer class="content-foot">
      <p class="fine">本说明随产品调整更新；有疑问可以通过站内举报入口留言给管理员。</p>
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

.rules-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 20px;
  font-size: 15px;
  line-height: 1.7;
}

.level-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.level-item {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
}

.level-item h3 {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
}

.level-item p {
  margin: 0;
  color: var(--muted);
  font-size: 14px !important;
  line-height: 1.7;
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
  .level-list {
    grid-template-columns: 1fr;
  }

  .content-foot {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
