import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
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
    meta: { title: '登录' },
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
    meta: { title: '匹配', requiresAuth: true },
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

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'plaza' }
  }
  document.title = to.meta.title ? `${to.meta.title} · Cohabit` : 'Cohabit · 校园舍友匹配'
  return true
})

export default router
