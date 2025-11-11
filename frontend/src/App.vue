<template>
  <v-app>
    <top-bar />
    <task-progress-banner />
    <v-main>
      <v-container centered class="pa-4">
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted } from 'vue'
import TopBar from '@/components/layout/TopBar.vue'
import TaskProgressBanner from '@/components/common/TaskProgressBanner.vue'
import { useTaskStore } from '@/stores/tasks'
import { useNotificationStore } from '@/stores/notification'

const taskStore = useTaskStore()
const notificationStore = useNotificationStore()

// Handle authentication expiration
const handleAuthExpired = (event: CustomEvent) => {
  notificationStore.showNotification(event.detail.message, 'warning', 5000)
}

// Start polling when app mounts (if there are active tasks)
onMounted(() => {
  if (taskStore.hasTasks && !taskStore.isPolling) {
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
