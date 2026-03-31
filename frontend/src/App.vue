<template>
  <v-app>
    <top-bar />
    <task-progress-banner />
    <v-main>
        <router-view />
    </v-main>
    <v-footer app class="text-center text-medium-emphasis text-body-2 flex-column pa-4" style="gap: 4px;">
      <div class="d-flex align-center justify-center flex-wrap" style="gap: 12px;">
        <span>MaRESS &mdash; Mapping Research in Earth System Sciences &copy; {{ new Date().getFullYear() }}</span>
        <v-divider vertical class="mx-1" style="max-height: 16px;" />
        <span class="d-inline-flex align-center" style="gap: 6px;">
          Funded by
          <a href="https://www.nfdi4earth.de/" target="_blank" rel="noopener noreferrer">
            <v-img src="/logo.png" alt="NFDI4Earth" width="120" inline />
          </a>
          (DFG)
        </span>
      </div>
    </v-footer>
  </v-app>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted } from 'vue'
import TopBar from '@/components/layout/TopBar.vue'
import TaskProgressBanner from '@/components/common/TaskProgressBanner.vue'
import { useTaskStore } from '@/stores/tasks'
import { useNotificationStore } from '@/stores/notification'
import { useAuthStore } from '@/stores/auth'

const taskStore = useTaskStore()
const notificationStore = useNotificationStore()
const authStore = useAuthStore()

// Handle authentication expiration
const handleAuthExpired = (event: CustomEvent) => {
  authStore.logout()
  notificationStore.showNotification(event.detail.message, 'warning', 5000)
}

// Start polling when app mounts (if there are active tasks)
onMounted(() => {
  authStore.initializeAuth().catch(() => undefined)

  if (authStore.isAuthenticated && taskStore.hasTasks && !taskStore.isPolling) {
    taskStore.startPolling()
  }

  // Listen for authentication expiration events
  window.addEventListener('auth:expired', handleAuthExpired as EventListener)
})

// Clean up polling when app unmounts
onUnmounted(() => {
  taskStore.stopPolling()
  window.removeEventListener('auth:expired', handleAuthExpired as EventListener)
})
</script>
