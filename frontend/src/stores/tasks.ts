import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '@/services/api'
import { useNotificationStore } from './notification'

export interface Task {
  task_id: string
  item_id?: string
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY'
  ready: boolean
  successful?: boolean
  study_site_count?: number
  extraction_status?: string
  error?: string
  timestamp: number
}

export interface TaskSummary {
  total: number
  pending: number
  started: number
  success: number
  failure: number
  retry: number
  ready: number
  successful: number
  failed: number
}

export const useTaskStore = defineStore('tasks', () => {
  const activeTasks = ref<Map<string, Task>>(new Map())
  const pollingInterval = ref<number | null>(null)
  const pollingIntervalMs = 3000 // Poll every 3 seconds

  const notificationStore = useNotificationStore()

  // Computed
  const hasTasks = computed(() => activeTasks.value.size > 0)

  const taskCount = computed(() => activeTasks.value.size)

  const completedCount = computed(() => {
    return Array.from(activeTasks.value.values()).filter((t) => t.ready).length
  })

  const successCount = computed(() => {
    return Array.from(activeTasks.value.values()).filter((t) => t.successful === true).length
  })

  const failedCount = computed(() => {
    return Array.from(activeTasks.value.values()).filter((t) => t.ready && t.successful === false)
      .length
  })

  const pendingCount = computed(() => {
    return Array.from(activeTasks.value.values()).filter((t) => !t.ready).length
  })

  const summary = computed((): TaskSummary => {
    const tasks = Array.from(activeTasks.value.values())
    return {
      total: tasks.length,
      pending: tasks.filter((t) => t.status === 'PENDING').length,
      started: tasks.filter((t) => t.status === 'STARTED').length,
      success: tasks.filter((t) => t.status === 'SUCCESS').length,
      failure: tasks.filter((t) => t.status === 'FAILURE').length,
      retry: tasks.filter((t) => t.status === 'RETRY').length,
      ready: tasks.filter((t) => t.ready).length,
      successful: tasks.filter((t) => t.successful === true).length,
      failed: tasks.filter((t) => t.ready && t.successful === false).length,
    }
  })

  // Methods
  const addTask = (taskId: string, itemId?: string) => {
    activeTasks.value.set(taskId, {
      task_id: taskId,
      item_id: itemId,
      status: 'PENDING',
      ready: false,
      timestamp: Date.now(),
    })

    // Start polling if not already polling
    if (pollingInterval.value === null) {
      startPolling()
    }
  }

  const addTasks = (tasks: Array<{ task_id: string; item_id?: string }>) => {
    tasks.forEach((task) => {
      addTask(task.task_id, task.item_id)
    })
  }

  const updateTask = (taskId: string, taskData: Partial<Task>) => {
    const existingTask = activeTasks.value.get(taskId)
    if (existingTask) {
      activeTasks.value.set(taskId, { ...existingTask, ...taskData })
    }
  }

  const removeTask = (taskId: string) => {
    activeTasks.value.delete(taskId)

    // Stop polling if no more tasks
    if (activeTasks.value.size === 0) {
      stopPolling()
    }
  }

  const clearCompletedTasks = () => {
    const tasks = Array.from(activeTasks.value.entries())
    tasks.forEach(([taskId, task]) => {
      if (task.ready) {
        activeTasks.value.delete(taskId)
      }
    })

    // Stop polling if no more tasks
    if (activeTasks.value.size === 0) {
      stopPolling()
    }
  }

  const clearAllTasks = () => {
    activeTasks.value.clear()
    stopPolling()
  }

  const fetchTaskStatuses = async () => {
    if (activeTasks.value.size === 0) {
      return
    }

    const taskIds = Array.from(activeTasks.value.keys())

    try {
      // Only query 50 tasks per request to avoid URL length issues
      for (let i = 0; i < taskIds.length; i += 50) {
        const chunk = taskIds.slice(i, i + 50)
        const chunkString = chunk.join(',')

        const response = await axios.get('/items/tasks/batch/', {
          params: { task_ids: chunkString },
        })
        // the response contains tasks and summary
        // Collect and combine the results from each request
        const combinedData = {
            tasks: response.data.tasks,
            summary: response.data.batchSummary,
        }
        processTaskStatusResponse(combinedData.tasks, combinedData.summary)
      }
    } catch (error) {
      console.error('Error fetching task statuses:', error)
    }
  }

  const processTaskStatusResponse = (tasks, summary) => {

    // Update each task
    Object.entries(tasks).forEach(([taskId, taskInfo]: [string, any]) => {
      const existingTask = activeTasks.value.get(taskId)

      if (existingTask) {
        const wasReady = existingTask.ready
        const isNowReady = taskInfo.ready

        updateTask(taskId, {
          status: taskInfo.status,
          ready: taskInfo.ready,
          successful: taskInfo.successful,
          study_site_count: taskInfo.study_site_count,
          extraction_status: taskInfo.extraction_status,
          error: taskInfo.error,
        })

        // Show notification if task just completed
        if (!wasReady && isNowReady) {
          handleTaskCompletion(taskId, taskInfo)
        }
      }
    })

    // Auto-remove completed tasks after 5 seconds
    const completedTaskIds = Object.entries(tasks)
      .filter(([_, taskInfo]: [string, any]) => taskInfo.ready)
      .map(([taskId]) => taskId)

    completedTaskIds.forEach((taskId) => {
      setTimeout(() => {
        removeTask(taskId)
      }, 5000)
    })
  }

  const handleTaskCompletion = (taskId: string, taskInfo: any) => {
    const task = activeTasks.value.get(taskId)

    if (taskInfo.successful) {
      const count = taskInfo.study_site_count || 0
      const message =
        count > 0 ?
          `Extraction complete: ${count} study site(s) found`
        : 'Extraction complete: No study sites found'

      notificationStore.showNotification(message, 'success', 8000)
    } else {
      const errorMsg = taskInfo.error || 'Unknown error'
      notificationStore.showNotification(`Extraction failed: ${errorMsg}`, 'error', 10000)
    }
  }

  const startPolling = () => {
    if (pollingInterval.value !== null) {
      return // Already polling
    }

    // Fetch immediately
    fetchTaskStatuses()

    // Then poll every N seconds
    pollingInterval.value = window.setInterval(() => {
      fetchTaskStatuses()
    }, pollingIntervalMs)
  }

  const stopPolling = () => {
    if (pollingInterval.value !== null) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  const cancelTask = async (taskId: string) => {
    try {
      const response = await axios.delete(`/items/tasks/${taskId}`)

      // Remove from active tasks
      removeTask(taskId)

      notificationStore.showNotification('Task cancelled successfully', 'info', 3000)

      return response.data
    } catch (error) {
      console.error('Error cancelling task:', error)
      notificationStore.showNotification('Failed to cancel task', 'error', 5000)
      return null
    }
  }

  const cancelAllTasks = async () => {
    if (activeTasks.value.size === 0) {
      return
    }

    const taskIds = Array.from(activeTasks.value.keys())
    const taskIdsString = taskIds.join(',')

    try {
      const response = await axios.post('/items/tasks/batch/cancel', null, {
        params: { task_ids: taskIdsString },
      })

      const { cancelled_count, failed_count } = response.data

      // Clear all tasks from store
      clearAllTasks()

      notificationStore.showNotification(
        `Cancelled ${cancelled_count} task(s)` +
          (failed_count > 0 ? ` (${failed_count} failed to cancel)` : ''),
        failed_count > 0 ? 'warning' : 'success',
        5000,
      )

      return response.data
    } catch (error) {
      console.error('Error cancelling tasks:', error)
      notificationStore.showNotification('Failed to cancel tasks', 'error', 5000)
      return null
    }
  }

  const cancelPendingTasks = async () => {
    // Get only pending tasks (not completed/running)
    const pendingTasks = Array.from(activeTasks.value.entries())
      .filter(
        ([_, task]) => !task.ready && (task.status === 'PENDING' || task.status === 'STARTED'),
      )
      .map(([taskId]) => taskId)

    if (pendingTasks.length === 0) {
      notificationStore.showNotification('No pending tasks to cancel', 'info', 3000)
      return
    }

    const taskIdsString = pendingTasks.join(',')

    try {
      const response = await axios.post('/items/tasks/batch/cancel', null, {
        params: { task_ids: taskIdsString },
      })

      const { cancelled_count } = response.data

      // Remove cancelled tasks from store
      pendingTasks.forEach((taskId) => removeTask(taskId))

      notificationStore.showNotification(
        `Cancelled ${cancelled_count} pending task(s)`,
        'success',
        5000,
      )

      return response.data
    } catch (error) {
      console.error('Error cancelling pending tasks:', error)
      notificationStore.showNotification('Failed to cancel pending tasks', 'error', 5000)
      return null
    }
  }

  const isPolling = computed(() => pollingInterval.value !== null)

  const getTaskDetails = async (taskId: string) => {
    try {
      const response = await axios.get(`/items/tasks/${taskId}`)
      return response.data
    } catch (error) {
      console.error('Error fetching task details:', error)
      return null
    }
  }

  const getAllTasks = computed(() => {
    return Array.from(activeTasks.value.values()).sort((a, b) => b.timestamp - a.timestamp)
  })

  return {
    // State
    activeTasks,
    pollingInterval,

    // Computed
    hasTasks,
    taskCount,
    completedCount,
    successCount,
    failedCount,
    pendingCount,
    summary,
    isPolling,
    getAllTasks,

    // Methods
    addTask,
    addTasks,
    updateTask,
    removeTask,
    clearCompletedTasks,
    clearAllTasks,
    fetchTaskStatuses,
    getTaskDetails,
    startPolling,
    stopPolling,
    cancelTask,
    cancelAllTasks,
    cancelPendingTasks,
  }
})
