<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MyRoomPanel from '@/components/rooms/MyRoomPanel.vue'
import RoomSquare from '@/components/rooms/RoomSquare.vue'

/**
 * 寝室页（docs/05 §7.1 `/rooms`）：我的寝室 + 寝室广场两个视图。
 * 广场同时是 `/plaza` 的主体（`PlazaView.vue` 复用同一组件），
 * 这里用 `?tab=square` 让导航可以直接落到广场。
 */
type TabKey = 'mine' | 'square'

const route = useRoute()
const router = useRouter()

const tab = computed<TabKey>(() => (route.query.tab === 'square' ? 'square' : 'mine'))

function selectTab(next: TabKey): void {
  void router.replace({
    path: '/rooms',
    query: next === 'square' ? { tab: 'square' } : {},
  })
}
</script>

<template>
  <div class="rooms-view container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Rooms</p>
        <h1>寝室</h1>
        <p>
          一人同时只能在一个有效寝室。满员、锁定或解散后，可用的动作会跟着变；容量建立后不可修改。
        </p>
      </div>
    </header>

    <div class="tabs" role="tablist" aria-label="寝室视图">
      <button
        type="button"
        class="tab"
        :class="{ active: tab === 'mine' }"
        role="tab"
        :aria-selected="tab === 'mine'"
        @click="selectTab('mine')"
      >
        我的寝室
      </button>
      <button
        type="button"
        class="tab"
        :class="{ active: tab === 'square' }"
        role="tab"
        :aria-selected="tab === 'square'"
        @click="selectTab('square')"
      >
        寝室广场
      </button>
    </div>

    <MyRoomPanel v-if="tab === 'mine'" />
    <RoomSquare v-else />
  </div>
</template>
