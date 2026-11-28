import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('./views/HomeView.vue') },
    { path: '/plaza', name: 'plaza', component: () => import('./views/PlazaView.vue') },
    { path: '/match', name: 'match', component: () => import('./views/MatchView.vue') },
    { path: '/profile', name: 'profile', component: () => import('./views/ProfileView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to) {
    if (to.hash) return { el: to.hash, top: 96 }
    return { top: 0 }
  },
})

export default router
