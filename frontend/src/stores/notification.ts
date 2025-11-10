import { defineStore } from 'pinia'
import { ref, type Ref } from 'vue'

// Notification types
export type NotificationType = 'success' | 'error' | 'warning' | 'info'

export interface Notification {
  message: string
  type: NotificationType
}

// Define the store's return type for better intellisense
export interface NotificationStore {
  notification: Ref<Notification | null>
  showNotification: (message: string, type?: NotificationType, duration?: number) => void
  clearNotification: () => void
}

export const useNotificationStore = defineStore('notification', (): NotificationStore => {
  const notification = ref<Notification | null>(null)

  const showNotification = (message: string, type: NotificationType = 'info', duration: number = 5000): void => {
    notification.value = { message, type }

    // Auto-clear notification after duration
    setTimeout(() => {
      clearNotification()
    }, duration)
  }

  const clearNotification = (): void => {
    notification.value = null
  }

  return {
    notification,
    showNotification,
    clearNotification,
  }
})
