import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { routes } from 'vue-router/auto-routes'
import logger from '@/utils/logger'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// Navigation guards
router.beforeEach((to) => {
  const authStore = useAuthStore()

  // if (to.meta.requiresAuth && !authStore.isAuthenticated) {
  //   return { name: 'Login', query: { redirect: to.fullPath } }
  // }
  // if (to.meta.guest && authStore.isAuthenticated) {
  //   return { name: 'Home' }
  // }
  return true
})

// Workaround for https://github.com/vitejs/vite/issues/11804
router.onError((err, to) => {
  if (err?.message?.includes?.('Failed to fetch dynamically imported module')) {
    if (localStorage.getItem('vuetify:dynamic-reload')) {
      logger.error('Dynamic import error, reloading page did not fix it', err)
    } else {
      logger.info('Reloading page to fix dynamic import error')
      localStorage.setItem('vuetify:dynamic-reload', 'true')
      location.assign(to.fullPath)
    }
  } else {
    logger.error('Router error:', err)
  }
})

router.isReady().then(() => {
  localStorage.removeItem('vuetify:dynamic-reload')
})

export default router
