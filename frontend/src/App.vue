<template>
  <v-app>
    <top-bar />
    <task-progress-banner />
    <v-main class="app-main">
      <router-view />
    </v-main>
    <v-footer class="app-footer text-center text-medium-emphasis text-body-2 py-2 px-4">
      <div class="d-flex align-center justify-center flex-wrap" style="gap: 10px;">
        <span>MaRESS &mdash; Mapping Research in Earth System Sciences &copy; {{ new Date().getFullYear() }}</span>
        <v-divider vertical class="mx-1" style="max-height: 16px;" />
        <span class="d-inline-flex align-center" style="gap: 6px;">
          Funded by
          <a href="https://www.nfdi4earth.de/" target="_blank" rel="noopener noreferrer">
            <v-img src="/logo.png" alt="NFDI4Earth" width="96" inline />
          </a>
          (DFG)
        </span>
      </div>
    </v-footer>
    <v-snackbar
      :model-value="!!notification"
      :color="notification?.type || 'info'"
      :timeout="-1"
      location="top right"
      @update:model-value="handleNotificationVisibility"
    >
      {{ notification?.message || '' }}
      <template #actions>
        <v-btn
          variant="text"
          @click="notificationStore.clearNotification()"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-app>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import TopBar from '@/components/layout/TopBar.vue'
import TaskProgressBanner from '@/components/common/TaskProgressBanner.vue'
import { useTaskStore } from '@/stores/tasks'
import { useNotificationStore } from '@/stores/notification'
import { useAuthStore } from '@/stores/auth'

const taskStore = useTaskStore()
const notificationStore = useNotificationStore()
const authStore = useAuthStore()
const { notification } = storeToRefs(notificationStore)

// Handle authentication expiration
const handleAuthExpired = (event: CustomEvent) => {
  authStore.logout()
  notificationStore.showNotification(event.detail.message, 'warning', 5000)
}

const handleNotificationVisibility = (isVisible: boolean) => {
  if (!isVisible) {
    notificationStore.clearNotification()
  }
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

<style scoped>
.app-main {
  min-height: 0;
}

.app-footer {
  min-height: 48px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}
</style>
