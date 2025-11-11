<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <div>
            <h1 class="text-h4 font-weight-bold">Task Monitor</h1>
            <p class="text-subtitle-1 text-medium-emphasis">
              Monitor and manage study site extraction tasks
            </p>
          </div>
          <div class="d-flex gap-2">
            <v-btn
              color="primary"
              variant="outlined"
              prepend-icon="mdi-refresh"
              @click="taskStore.fetchTaskStatuses"
              :disabled="!taskStore.hasTasks"
            >
              Refresh
            </v-btn>
            <v-btn
              color="warning"
              variant="outlined"
              prepend-icon="mdi-cancel"
              @click="handleCancelPending"
              :disabled="taskStore.pendingCount === 0"
              :loading="cancelling"
            >
              Cancel Pending ({{ taskStore.pendingCount }})
            </v-btn>
            <v-btn
              color="info"
              variant="outlined"
              prepend-icon="mdi-restart"
              @click="handleRetryAllFailed"
              :disabled="taskStore.failedCount === 0"
              :loading="retryingAll"
            >
              Retry All Failed ({{ taskStore.failedCount }})
            </v-btn>
            <v-btn
              color="error"
              variant="outlined"
              prepend-icon="mdi-delete"
              @click="handleClearFailed"
              :disabled="taskStore.failedCount === 0"
            >
              Delete All Failed ({{ taskStore.failedCount }})
            </v-btn>
            <v-btn
              color="error"
              variant="outlined"
              prepend-icon="mdi-close-circle"
              @click="handleClearAll"
              :disabled="!taskStore.hasTasks"
            >
              Clear All
            </v-btn>
          </div>
        </div>

        <!-- Summary Cards -->
        <v-row class="mb-4">
          <v-col cols="12" sm="6" md="3">
            <v-card>
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-overline text-medium-emphasis">Total Tasks</div>
                    <div class="text-h4 font-weight-bold">{{ taskStore.taskCount }}</div>
                  </div>
                  <v-icon size="48" color="primary">mdi-cog-outline</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-card>
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-overline text-medium-emphasis">Pending</div>
                    <div class="text-h4 font-weight-bold">{{ taskStore.pendingCount }}</div>
                  </div>
                  <v-icon size="48" color="warning">mdi-clock-outline</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-card>
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-overline text-medium-emphasis">Succeeded</div>
                    <div class="text-h4 font-weight-bold text-success">
                      {{ taskStore.successCount }}
                    </div>
                  </div>
                  <v-icon size="48" color="success">mdi-check-circle-outline</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-card>
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-overline text-medium-emphasis">Failed</div>
                    <div class="text-h4 font-weight-bold text-error">
                      {{ taskStore.failedCount }}
                    </div>
                  </div>
                  <v-icon size="48" color="error">mdi-alert-circle-outline</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Tasks Table -->
        <v-card>
          <v-card-title>
            <div class="d-flex align-center justify-space-between">
              <span>Active Tasks</span>
              <v-chip v-if="taskStore.isPolling" color="success" size="small">
                <v-icon start size="small">mdi-sync</v-icon>
                Auto-refreshing
              </v-chip>
            </div>
          </v-card-title>

          <v-card-text v-if="!taskStore.hasTasks" class="text-center py-8">
            <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-checkbox-marked-circle-outline</v-icon>
            <div class="text-h6 text-medium-emphasis">No active tasks</div>
            <p class="text-body-2 text-medium-emphasis mt-2">
              Start an extraction from the Papers page to see tasks here
            </p>
            <v-btn color="primary" class="mt-4" to="/items">
              Go to Papers
            </v-btn>
          </v-card-text>

          <v-data-table
            v-else
            :items="taskStore.getAllTasks"
            :headers="headers"
            item-value="task_id"
            :items-per-page="20"
            :items-per-page-options="[10, 20, 50, 100]"
          >
            <!-- Status Column -->
            <template #item.status="{ item }">
              <v-chip
                :color="getStatusColor(item.status)"
                size="small"
                :prepend-icon="getStatusIcon(item.status)"
              >
                {{ item.status }}
              </v-chip>
            </template>

            <!-- Progress Column -->
            <template #item.progress="{ item }">
              <div class="d-flex align-center" style="min-width: 150px">
                <v-progress-linear
                  :model-value="item.ready ? 100 : (item.status === 'STARTED' ? 50 : 10)"
                  :color="item.successful === true ? 'success' : item.successful === false ? 'error' : 'primary'"
                  height="8"
                  rounded
                  class="flex-grow-1"
                />
                <span class="ml-2 text-caption">
                  {{ item.ready ? '100%' : (item.status === 'STARTED' ? '50%' : '10%') }}
                </span>
              </div>
            </template>

            <!-- Result Column -->
            <template #item.result="{ item }">
              <div v-if="item.ready">
                <div v-if="item.successful === true" class="d-flex align-center">
                  <v-icon color="success" size="small" class="mr-1">mdi-check-circle</v-icon>
                  <span v-if="item.study_site_count !== undefined">
                    {{ item.study_site_count }} site(s) found
                  </span>
                  <span v-else class="text-success">Success</span>
                </div>
                <div v-else-if="item.successful === false" class="d-flex align-center">
                  <v-icon color="error" size="small" class="mr-1">mdi-alert-circle</v-icon>
                  <v-tooltip v-if="item.error" location="top">
                    <template #activator="{ props }">
                      <span v-bind="props" class="text-error text-truncate" style="max-width: 200px">
                        {{ item.error }}
                      </span>
                    </template>
                    <span>{{ item.error }}</span>
                  </v-tooltip>
                  <span v-else class="text-error">Failed</span>
                </div>
              </div>
              <span v-else class="text-medium-emphasis">Processing...</span>
            </template>

            <!-- Time Column -->
            <template #item.timestamp="{ item }">
              <span class="text-caption">{{ formatTimestamp(item.timestamp) }}</span>
            </template>

            <!-- Actions Column -->
            <template #item.actions="{ item }">
              <div class="d-flex gap-1">
                <v-tooltip text="View Details" location="top">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon
                      size="x-small"
                      variant="text"
                      @click="viewTaskDetails(item)"
                    >
                      <v-icon>mdi-information-outline</v-icon>
                    </v-btn>
                  </template>
                </v-tooltip>

                <v-tooltip v-if="item.item_id" text="View Item" location="top">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon
                      size="x-small"
                      variant="text"
                      :to="`/items/${item.item_id}`"
                    >
                      <v-icon>mdi-file-document-outline</v-icon>
                    </v-btn>
                  </template>
                </v-tooltip>

                <v-tooltip
                  v-if="item.ready && item.successful === false && item.item_id"
                  text="Retry Task"
                  location="top"
                >
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon
                      size="x-small"
                      variant="text"
                      color="info"
                      @click="handleRetryTask(item.task_id)"
                      :loading="retryingTasks.has(item.task_id)"
                    >
                      <v-icon>mdi-restart</v-icon>
                    </v-btn>
                  </template>
                </v-tooltip>

                <v-tooltip text="Clear Task" location="top">
                  <template #activator="{ props }">
                    <v-btn
                      v-bind="props"
                      icon
                      size="x-small"
                      variant="text"
                      color="error"
                      @click="taskStore.removeTask(item.task_id)"
                    >
                      <v-icon>mdi-close</v-icon>
                    </v-btn>
                  </template>
                </v-tooltip>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Task Details Dialog -->
    <v-dialog v-model="detailsDialog" max-width="600">
      <v-card v-if="selectedTask">
        <v-card-title>
          <div class="d-flex align-center justify-space-between">
            <span>Task Details</span>
            <v-btn icon variant="text" @click="detailsDialog = false">
              <v-icon>mdi-close</v-icon>
            </v-btn>
          </div>
        </v-card-title>

        <v-divider />

        <v-card-text>
          <v-list dense>
            <v-list-item>
              <v-list-item-title class="font-weight-bold">Task ID</v-list-item-title>
              <v-list-item-subtitle>
                <code class="text-caption">{{ selectedTask.task_id }}</code>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="selectedTask.item_id">
              <v-list-item-title class="font-weight-bold">Item ID</v-list-item-title>
              <v-list-item-subtitle>
                <code class="text-caption">{{ selectedTask.item_id }}</code>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title class="font-weight-bold">Status</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  :color="getStatusColor(selectedTask.status)"
                  size="small"
                  class="mt-1"
                >
                  {{ selectedTask.status }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-title class="font-weight-bold">Started</v-list-item-title>
              <v-list-item-subtitle>
                {{ formatTimestamp(selectedTask.timestamp) }}
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="selectedTask.ready">
              <v-list-item-title class="font-weight-bold">Result</v-list-item-title>
              <v-list-item-subtitle>
                <div v-if="selectedTask.successful === true" class="text-success">
                  <v-icon color="success" size="small" class="mr-1">mdi-check-circle</v-icon>
                  Success
                  <span v-if="selectedTask.study_site_count !== undefined">
                    - {{ selectedTask.study_site_count }} study site(s) found
                  </span>
                </div>
                <div v-else class="text-error">
                  <v-icon color="error" size="small" class="mr-1">mdi-alert-circle</v-icon>
                  Failed
                  <div v-if="selectedTask.error" class="mt-2 pa-2 bg-error-lighten-5 rounded">
                    <code class="text-caption">{{ selectedTask.error }}</code>
                  </div>
                </div>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="selectedTask.extraction_status">
              <v-list-item-title class="font-weight-bold">Extraction Status</v-list-item-title>
              <v-list-item-subtitle>
                {{ selectedTask.extraction_status }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            v-if="selectedTask.item_id"
            color="primary"
            variant="text"
            :to="`/items/${selectedTask.item_id}`"
            @click="detailsDialog = false"
          >
            View Item
          </v-btn>
          <v-btn color="grey" variant="text" @click="detailsDialog = false">
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '@/stores/tasks'
import type { Task } from '@/stores/tasks'

const taskStore = useTaskStore()
const cancelling = ref(false)
const retryingAll = ref(false)
const retryingTasks = ref(new Set<string>())
const detailsDialog = ref(false)
const selectedTask = ref<Task | null>(null)

const headers = [
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Progress', key: 'progress', sortable: false },
  { title: 'Result', key: 'result', sortable: false },
  { title: 'Started', key: 'timestamp', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' },
]

const getStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    PENDING: 'grey',
    STARTED: 'info',
    SUCCESS: 'success',
    FAILURE: 'error',
    RETRY: 'warning',
  }
  return colorMap[status] || 'grey'
}

const getStatusIcon = (status: string): string => {
  const iconMap: Record<string, string> = {
    PENDING: 'mdi-clock-outline',
    STARTED: 'mdi-cog-sync-outline',
    SUCCESS: 'mdi-check-circle',
    FAILURE: 'mdi-alert-circle',
    RETRY: 'mdi-refresh',
  }
  return iconMap[status] || 'mdi-help-circle-outline'
}

const formatTimestamp = (timestamp: number): string => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} min ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`

  return date.toLocaleString()
}

const handleCancelPending = async () => {
  cancelling.value = true
  try {
    await taskStore.cancelPendingTasks()
  } finally {
    cancelling.value = false
  }
}

const handleClearAll = () => {
  if (confirm('Are you sure you want to clear all tasks?')) {
    taskStore.clearAllTasks()
  }
}

const handleClearFailed = () => {
  if (confirm('Are you sure you want to delete all failed tasks?')) {
    taskStore.clearFailedTasks()
  }
}

const handleRetryAllFailed = async () => {
  retryingAll.value = true
  try {
    await taskStore.retryAllFailed()
  } finally {
    retryingAll.value = false
  }
}

const handleRetryTask = async (taskId: string) => {
  retryingTasks.value.add(taskId)
  try {
    await taskStore.retryTask(taskId)
  } finally {
    retryingTasks.value.delete(taskId)
  }
}

const viewTaskDetails = async (task: Task) => {
  selectedTask.value = task
  detailsDialog.value = true

  // Fetch fresh details from API
  const details = await taskStore.getTaskDetails(task.task_id)
  if (details) {
    // Update with fresh data
    selectedTask.value = { ...task, ...details }
  }
}

// Ensure polling is active when page loads
onMounted(() => {
  if (taskStore.hasTasks && !taskStore.isPolling) {
    taskStore.startPolling()
  }
})

// Keep polling alive while on this page
onUnmounted(() => {
  // Don't stop polling - let App.vue handle it
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}

.gap-1 {
  gap: 4px;
}
</style>
