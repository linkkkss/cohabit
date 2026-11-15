<script setup lang="ts">
import RoomSquare from '@/components/rooms/RoomSquare.vue'

/**
 * 寝室广场首页（docs/05 §7.2）：只列 `RECRUITING` 且有空位的寝室，
 * 卡片显示编号、标题、人数/容量、状态、标签；没有联系方式，也没有加入按钮。
 */
</script>

<template>
  <div class="plaza-view container">
    <header class="page-head">
      <div>
        <p class="eyebrow">Plaza</p>
        <h1>寝室广场</h1>
        <p>
          同学院、同性别、还在招募的寝室。点开看看成员和标签，觉得合适再在组寝请求里申请——
          组寝要双方确认，广场这里不直接加入。
        </p>
      </div>
    </header>

    <RoomSquare />
  </div>
</template>
