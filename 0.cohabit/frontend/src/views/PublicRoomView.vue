<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AvatarBadge from '@/components/common/AvatarBadge.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import TagChips from '@/components/common/TagChips.vue'
import { apiErrorStatus } from '@/api/client'
import {
  fetchPublicRoom,
  isRoomReadOnly,
  roomErrorMessage,
  roomSeatsText,
  roomStatusClass,
  roomStatusLabel,
  type PublicRoom,
} from '@/api/rooms'

/**
 * 公开寝室分享页（docs/05 §7.1 `/r/:code`，P4 新增，无鉴权）。
 *
 * 只展示编号、标题、状态、容量、学院、标签与成员昵称——没有 uid、房主、
 * 联系方式；ARCHIVED / DISSOLVED 由后端直接 404，这里也不做「已归档」的猜测。
 */
const route = useRoute()
const auth = useAuthStore()

const code = computed(() => String(route.params.code ?? ''))
const state = ref<'loading' | 'ready' | 'error'>('loading')
const room = ref<PublicRoom | null>(null)
const errorMessage = ref('')

const seats = computed(() => (room.value ? roomSeatsText(room.value) : ''))
const closed = computed(() => Boolean(room.value && isRoomReadOnly(room.value.status)))

async function load(): Promise<void> {
  state.value = 'loading'
  errorMessage.value = ''
  try {
    room.value = await fetchPublicRoom(code.value)
    state.value = 'ready'
  } catch (error) {
    errorMessage.value =
      apiErrorStatus(error) === 404
        ? '这个页面不存在，或者你没有权限查看。'
        : roomErrorMessage(error, '寝室没有加载出来，请稍后重试。')
    state.value = 'error'
  }
}

watch(code, () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="public-room">
    <RouterLink class="back-link fine" :to="{ name: 'home' }">← 回到 Cohabit</RouterLink>

    <StateBlock v-if="state === 'loading'" status="loading" title="正在打开分享页…" :rows="2" />

    <div v-else-if="state === 'error'" class="public-error">
      <StateBlock
        status="error"
        title="打不开这个寝室页"
        :message="errorMessage"
        @retry="load()"
      />
      <RouterLink class="btn btn-ghost btn-small" :to="{ name: 'plaza' }">去寝室广场</RouterLink>
    </div>

    <article v-else-if="room" class="public-card">
      <header class="public-head">
        <p class="eyebrow">公开寝室页</p>
        <h1 class="public-title">{{ room.title || '未命名寝室' }}</h1>
        <p class="public-meta">
          <span class="status" :class="roomStatusClass(room.status)">{{ roomStatusLabel(room.status) }}</span>
          <span>{{ seats }}</span>
          <span>{{ room.college }}</span>
        </p>
        <p class="public-code">编号 {{ room.code }}</p>
      </header>

      <section class="public-section">
        <h2 class="public-section-title">标签</h2>
        <TagChips :tags="room.tags" :max="0" empty-text="这间寝室还没有标签。" />
      </section>

      <section class="public-section">
        <div class="public-section-head">
          <h2 class="public-section-title">成员</h2>
          <span class="fine">{{ room.member_count }} / {{ room.capacity }} 人</span>
        </div>
        <ul v-if="room.members.length" class="public-members">
          <li v-for="(member, index) in room.members" :key="`${member.nickname}-${index}`" class="public-member">
            <AvatarBadge :name="member.nickname" size="sm" />
            <span>{{ member.nickname }}</span>
          </li>
        </ul>
        <p v-else class="fine">这间寝室还没有成员。</p>
      </section>

      <p class="fine public-note">
        公开页只展示寝室概况和成员昵称；联系方式只在双方同意后可见。
        <template v-if="closed">这间寝室已经不再接收新成员。</template>
      </p>

      <div class="public-actions">
        <RouterLink v-if="!auth.isAuthenticated" class="btn btn-primary" :to="{ name: 'login', query: { redirect: '/plaza' } }">
          登录后查看完整信息
        </RouterLink>
        <RouterLink v-else class="btn btn-primary" :to="{ name: 'plaza' }">去寝室广场看看</RouterLink>
      </div>
    </article>
  </div>
</template>

<style scoped>
.public-room {
  display: grid;
  gap: 16px;
  width: min(720px, 100%);
  margin: 0 auto;
  padding: 40px 0 64px;
}

.back-link {
  width: fit-content;
  color: var(--muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--ink);
}

.public-error {
  display: grid;
  gap: 12px;
  justify-items: start;
}

.public-card {
  display: grid;
  gap: 22px;
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 28px;
  background: var(--paper);
}

.public-head {
  display: grid;
  gap: 10px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 20px;
}

.public-head .eyebrow {
  margin: 0;
}

.public-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(28px, 4vw, 38px);
  font-weight: 500;
  line-height: 1.1;
  overflow-wrap: anywhere;
}

.public-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.public-code {
  margin: 0;
  color: var(--muted);
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.public-section {
  display: grid;
  gap: 10px;
}

.public-section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.public-section-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 500;
}

.public-members {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.public-member {
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding: 10px 0;
  font-size: 15px;
}

.public-member:first-child {
  border-top: 0;
}

.public-note {
  margin: 0;
  color: var(--muted);
  line-height: 1.75;
}

.public-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 640px) {
  .public-room {
    padding: 20px 0 48px;
  }

  .public-card {
    padding: 20px;
  }

  .public-actions .btn {
    width: 100%;
    min-height: 44px;
  }
}
</style>
