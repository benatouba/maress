import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { routes } from 'vue-router/auto-routes'
import logger from '@/utils/logger'

const normalizeRoutesToLowercase = (records: Readonly<RouteRecordRaw[]>): RouteRecordRaw[] => {
  return records.map((record) => {
    const normalizedPath = record.path === '/' ? '/' : record.path.toLowerCase()
    const aliases = Array.isArray(record.alias)
      ? [...record.alias]
      : record.alias
        ? [record.alias]
        : []

    if (record.path !== normalizedPath && !aliases.includes(record.path)) {
      aliases.push(record.path)
    }

    return {
      ...record,
      path: normalizedPath,
      alias: aliases.length > 0 ? aliases : undefined,
      children: record.children ? normalizeRoutesToLowercase(record.children) : undefined,
    } as RouteRecordRaw
  })
}

const normalizedRoutes = normalizeRoutesToLowercase(routes)

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: normalizedRoutes,
})

// Navigation guards
router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.matched.length === 0) {
    const caseInsensitiveMatch = router
      .getRoutes()
      .find((route) => route.path.toLowerCase() === to.path.toLowerCase())

    if (caseInsensitiveMatch) {
      logger.warn('Redirecting route with path casing mismatch', {
        requestedPath: to.path,
        resolvedPath: caseInsensitiveMatch.path,
      })

      return {
        path: caseInsensitiveMatch.path,
        query: to.query,
        hash: to.hash,
        replace: true,
      }
    }

    logger.warn('No route matched, redirecting to not found page', {
      requestedPath: to.path,
    })
    return { path: '/NotFound', query: { from: to.fullPath }, replace: true }
  }

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
