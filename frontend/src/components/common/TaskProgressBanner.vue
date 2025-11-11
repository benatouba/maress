<template>
  <v-expand-transition>
    <v-banner
      v-if="taskStore.hasTasks"
      color="info"
      icon="mdi-cog-sync"
      sticky
      elevation="4"
      class="task-progress-banner clickable"
      @click="navigateToTasks"
    >
      <template #text>
        <div class="d-flex align-center justify-space-between flex-wrap">
          <div class="d-flex align-center">
            <v-progress-circular
              :model-value="progressPercentage"
              :size="32"
              :width="3"
              color="white"
              class="mr-3"
            >
              <span class="text-caption">{{ taskStore.completedCount }}/{{ taskStore.taskCount }}</span>
            </v-progress-circular>

            <div>
              <div class="text-subtitle-2 font-weight-bold">
                Processing Study Site Extractions
                <v-icon size="small" class="ml-1">mdi-arrow-right</v-icon>
              </div>
              <div class="text-caption">
                {{ taskStore.completedCount }} of {{ taskStore.taskCount }} tasks completed
                <span v-if="taskStore.successCount > 0" class="ml-2">
                  <v-icon size="x-small" color="success">mdi-check-circle</v-icon>
                  {{ taskStore.successCount }} succeeded
                </span>
                <span v-if="taskStore.failedCount > 0" class="ml-2">
                  <v-icon size="x-small" color="error">mdi-alert-circle</v-icon>
                  {{ taskStore.failedCount }} failed
                </span>
              </div>
            </div>
          </div>

          <div class="d-flex align-center gap-2" @click.stop>
            <v-tooltip text="Cancel pending tasks" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon
                  size="small"
                  variant="text"
                  color="warning"
                  @click.stop="handleCancelPending"
                  :disabled="taskStore.pendingCount === 0"
                  :loading="cancelling"
                >
                  <v-icon>mdi-cancel</v-icon>
                </v-btn>
              </template>
            </v-tooltip>

            <v-tooltip text="Clear completed tasks" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon
                  size="small"
                  variant="text"
                  @click.stop="taskStore.clearCompletedTasks"
                  :disabled="taskStore.completedCount === 0"
                >
                  <v-icon>mdi-broom</v-icon>
                </v-btn>
              </template>
            </v-tooltip>

            <v-tooltip text="Dismiss all" location="bottom">
              <template #activator="{ props }">
                <v-btn
                  v-bind="props"
                  icon
                  size="small"
                  variant="text"
                  @click.stop="taskStore.clearAllTasks"
                >
                  <v-icon>mdi-close</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
          </div>
        </div>
      </template>

      <template #actions>
        <!-- Empty to prevent default action slot -->
      </template>
    </v-banner>
  </v-expand-transition>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/tasks'

const router = useRouter()
const taskStore = useTaskStore()
const cancelling = ref(false)

const progressPercentage = computed(() => {
  if (taskStore.taskCount === 0) return 0
  return Math.round((taskStore.completedCount / taskStore.taskCount) * 100)
})

const navigateToTasks = () => {
  router.push('/tasks')
}

const handleCancelPending = async () => {
  cancelling.value = true
  try {
    await taskStore.cancelPendingTasks()
  } finally {
    cancelling.value = false
  }
}

// Ensure polling is active when banner is visible
onMounted(() => {
  if (taskStore.hasTasks && !taskStore.isPolling) {
    taskStore.startPolling()
  }
})

// Watch for task changes and ensure polling continues
watch(() => taskStore.hasTasks, (hasTasks) => {
  if (hasTasks && !taskStore.isPolling) {
    taskStore.startPolling()
  }
})
</script>

<style scoped>
.task-progress-banner {
  position: fixed;
  top: 64px; /* Height of v-app-bar */
  left: 0;
  right: 0;
  z-index: 999; /* Below app-bar (1000) but above content */
  margin: 0;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.task-progress-banner.clickable {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.task-progress-banner.clickable:hover {
  filter: brightness(1.1);
}

:deep(.v-banner__wrapper) {
  padding: 12px 16px;
}

:deep(.v-banner__text) {
  flex: 1;
}

.gap-2 {
  gap: 8px;
}

/* Ensure banner is visible above main content */
:deep(.v-banner) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}
</style>
