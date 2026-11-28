import { readonly, ref } from 'vue'

/** 首屏入场动画的全局状态：App 用它隐藏页头，首页用它驱动进度。 */
const active = ref(false)
const progress = ref(0)
let played = false

export function useIntro() {
  return {
    introActive: readonly(active),
    introProgress: readonly(progress),
  }
}

export function setIntro(next: boolean, value = 0) {
  active.value = next
  progress.value = value
}

export function hasIntroPlayed() {
  return played
}

export function markIntroPlayed() {
  played = true
}
