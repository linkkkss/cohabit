<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import NoticeBar from '@/components/common/NoticeBar.vue'
import StateBlock from '@/components/common/StateBlock.vue'
import RoomCard from '@/components/rooms/RoomCard.vue'
import RoomFilters, { type RoomFilterValue } from '@/components/rooms/RoomFilters.vue'
import { loadRoomTagOptions } from '@/components/rooms/tagOptions'
import { majorsForCollege } from '@/components/rooms/roomFormat'
import type { TagOption } from '@/api/profiles'
import {
  ROOM_SQUARE_PAGE_SIZE,
  fetchRoomSquare,
  roomErrorMessage,
  type RoomSummary,
} from '@/api/rooms'

/**
 * 寝室广场（docs/04 §4.3、docs/05 §7.2）。
 *
 * 只列 `RECRUITING` 且有空位的本学院同性寝室；卡片不出现联系方式，
 * 也没有「加入」按钮——组寝只能走连接确认，申请入口在组寝请求页。
 */
const auth = useAuthStore()

function emptyFilters(): RoomFilterValue {
  return { major: '', capacity: null, tags: [] }
}

const filters = ref<RoomFilterValue>(emptyFilters())
const applied = ref<RoomFilterValue>(emptyFilters())

const state = ref<'gate' | 'loading' | 'ready' | 'error'>('loading')
const errorMessage = ref('')
const rooms = ref<RoomSummary[]>([])
const count = ref(0)
const page = ref(1)
const tagOptions = ref<TagOption[]>([])

const majorOptions = computed(() => majorsForCollege(auth.user?.college ?? ''))
const college = computed(() => auth.user?.college ?? '')
const pageCount = computed(() => Math.max(1, Math.ceil(count.value / ROOM_SQUARE_PAGE_SIZE)))

async function load(pageToLoad = page.value, query = applied.value): Promise<void> {
  if (!auth.isAuthenticated) {
    // 公开页面进入时静默 refresh 还在跑：先保持加载态，别闪一下「去登录」。
    if (!auth.initialized) {
      state.value = 'loading'
      return
    }
    state.value = 'gate'
    rooms.value = []
    count.value = 0
    return
  }
  state.value = 'loading'
  errorMessage.value = ''
  try {
    const data = await fetchRoomSquare({
      major: query.major,
      capacity: query.capacity,
      tags: query.tags,
      page: pageToLoad,
    })
    rooms.value = data.results
    count.value = data.count
    page.value = pageToLoad
    state.value = 'ready'
  } catch (error) {
    errorMessage.value = roomErrorMessage(error, '广场没有加载出来，请稍后重试。')
    state.value = 'error'
  }
}

function apply(): void {
  applied.value = { ...filters.value, tags: [...filters.value.tags] }
  void load(1, applied.value)
}

function reset(): void {
  filters.value = emptyFilters()
  applied.value = emptyFilters()
  void load(1, applied.value)
}

function goPage(target: number): void {
  if (target < 1 || target > pageCount.value) {
    return
  }
  void load(target)
}

// 公开路由后台恢复会话；恢复完成后再决定加载还是展示登录引导。
watch(
  () => auth.initialized,
  (initialized) => {
    if (initialized) {
      void load(1)
    }
  },
)

onMounted(() => {
  void load(1)
  loadRoomTagOptions()
    .then((options) => {
      tagOptions.value = options
    })
    .catch(() => {
      // 词库加载失败只影响标签筛选，不阻塞广场本身。
      tagOptions.value = []
    })
})
</script>

<template>
  <section class="square">
    <header class="square-head">
      <div>
        <p class="eyebrow">Plaza</p>
        <h2 class="square-title">还在招募的寝室</h2>
      </div>
      <p v-if="state === 'ready'" class="fine square-count">
        共 {{ count }} 间 · 第 {{ page }} / {{ pageCount }} 页
      </p>
    </header>

    <NoticeBar v-if="state === 'gate'" tone="info" title="登录后查看寝室广场">
      广场只展示本学院、同性别、仍在招募的寝室；登录后才能看到编号、成员与标签。
      <div class="gate-actions">
        <RouterLink class="btn btn-primary btn-small" :to="{ name: 'login', query: { redirect: '/plaza' } }">
          去登录
        </RouterLink>
      </div>
    </NoticeBar>

    <template v-else>
      <RoomFilters
        v-model="filters"
        :major-options="majorOptions"
        :college="college"
        :tag-options="tagOptions"
        :busy="state === 'loading'"
        @submit="apply"
        @reset="reset"
      />

      <StateBlock
        v-if="state === 'loading'"
        status="loading"
        title="正在加载寝室…"
        :rows="3"
      />
      <StateBlock
        v-else-if="state === 'error'"
        status="error"
        title="广场没有加载出来"
        :message="errorMessage"
        @retry="load()"
      />
      <div v-else-if="!rooms.length" class="empty">
        <strong>还没有符合条件的寝室</strong>
        <p>
          换一组筛选，或者等同学建寝后再来看看。寝室满员或锁定后会自动从这里消失。
        </p>
        <button type="button" class="btn btn-ghost btn-small" @click="reset">清除筛选</button>
      </div>
      <div v-else class="room-grid">
        <RoomCard v-for="room in rooms" :key="room.code" :room="room" />
      </div>

      <nav v-if="state === 'ready' && pageCount > 1" class="pager" aria-label="分页">
        <button
          type="button"
          class="btn btn-ghost btn-small"
          :disabled="page <= 1"
          @click="goPage(page - 1)"
        >
          上一页
        </button>
        <span class="fine">第 {{ page }} / {{ pageCount }} 页</span>
        <button
          type="button"
          class="btn btn-ghost btn-small"
          :disabled="page >= pageCount"
          @click="goPage(page + 1)"
        >
          下一页
        </button>
      </nav>
    </template>
  </section>
</template>

<style scoped>
.square {
  display: grid;
  gap: 20px;
}

.square-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.square-head .eyebrow {
  margin: 0 0 6px;
}

.square-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: clamp(24px, 3vw, 32px);
  font-weight: 500;
}

.square-count {
  margin: 0;
  color: var(--muted);
}

.gate-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

@media (max-width: 640px) {
  .pager {
    justify-content: space-between;
  }

  .pager .btn {
    min-height: 44px;
  }
}
</style>
