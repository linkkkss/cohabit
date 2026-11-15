<script setup lang="ts">
/**
 * 路由入口（`@/views/OnboardingView.vue`，路由表由 F1 维护，不在本页改写范围内）。
 * 具体实现放在 `views/onboarding/`，这里只做薄壳，保证路由 target 不变。
 */
import OnboardingWizard from '@/views/onboarding/OnboardingWizard.vue'
</script>

<template>
  <OnboardingWizard />
</template>
