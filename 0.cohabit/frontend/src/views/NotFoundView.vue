<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="container" style="padding: 96px 0; text-align: center">
    <p class="eyebrow">404</p>
    <h1 class="display" style="font-size: clamp(40px, 8vw, 80px)">走错门了。</h1>
    <p class="lede" style="margin-inline: auto">这个页面不存在，或者已经被归档/解散。</p>
    <div style="margin-top: 28px">
      <RouterLink class="btn btn-primary" to="/">回到首页</RouterLink>
    </div>
  </div>
</template>
