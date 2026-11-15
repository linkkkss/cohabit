import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { onSessionExpired } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { resolveAuthRedirect } from '@/router/redirect'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    /** 需要登录；未登录跳 /login 并带上 redirect。 */
    requiresAuth?: boolean
    /** 需要画像 100%；未完成跳 /onboarding。 */
    requiresProfile?: boolean
    /** 已入寝用户不能进入（如匹配页），跳 /rooms。 */
    requiresNoRoom?: boolean
    /** 仅游客可见（登录页）；已登录用户直接回到落点。 */
    guestOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '先聊清楚，再住一起' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', guestOnly: true },
  },
  {
    path: '/onboarding',
    name: 'onboarding',
    component: () => import('@/views/OnboardingView.vue'),
    meta: { title: '完善画像', requiresAuth: true },
  },
  {
    path: '/match',
    name: 'match',
    component: () => import('@/views/MatchView.vue'),
    meta: {
      title: '匹配',
      requiresAuth: true,
      requiresProfile: true,
      requiresNoRoom: true,
    },
  },
  {
    path: '/plaza',
    name: 'plaza',
    component: () => import('@/views/PlazaView.vue'),
    meta: { title: '寝室广场' },
  },
  {
    path: '/connections',
    name: 'connections',
    component: () => import('@/views/ConnectionsView.vue'),
    meta: { title: '组寝请求', requiresAuth: true },
  },
  {
    path: '/rooms',
    name: 'rooms',
    component: () => import('@/views/RoomsView.vue'),
    meta: { title: '我的寝室', requiresAuth: true },
  },
  {
    path: '/rooms/:code',
    name: 'room-detail',
    component: () => import('@/views/RoomDetailView.vue'),
    meta: { title: '寝室详情' },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { title: '我的画像', requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const needsSession = Boolean(
    to.meta.requiresAuth || to.meta.requiresProfile || to.meta.requiresNoRoom || to.meta.guestOnly,
  )

  // 受保护页面必须等静默 refresh 完成；公开页面后台恢复，避免后端不可用时首屏被拖住。
  if (needsSession) {
    await auth.ensureReady()
  } else {
    void auth.ensureReady()
  }

  if (to.meta.guestOnly && auth.isAuthenticated) {
    return resolveAuthRedirect(auth, to.query.redirect)
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresProfile && !auth.isProfileComplete) {
    return { name: 'onboarding', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresNoRoom && auth.hasRoom) {
    return { name: 'rooms' }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · Cohabit` : 'Cohabit · 校园舍友匹配'
})

// 单航班刷新失败后：清空内存会话，并保证只跳一次登录页。
let redirectingToLogin = false
onSessionExpired(() => {
  const auth = useAuthStore()
  const current = router.currentRoute.value
  auth.handleSessionExpired()

  const needsRedirect = Boolean(current.meta.requiresAuth || current.meta.requiresProfile)
  if (!needsRedirect || redirectingToLogin) {
    return
  }
  redirectingToLogin = true
  void router
    .replace({ name: 'login', query: { redirect: current.fullPath } })
    .catch(() => undefined)
    .finally(() => {
      redirectingToLogin = false
    })
})

export default router
