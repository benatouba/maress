<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <!-- Navigation -->
    <nav class="bg-white shadow-sm">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center space-x-4">
            <!-- User menu -->
            <div class="relative" v-if="authStore.isAuthenticated">
              <button
                @click="showUserMenu = !showUserMenu"
                class="flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <span class="sr-only">Open user menu</span>
                <div class="h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center">
                  <span class="text-white font-medium">
                    {{ authStore.user?.username?.charAt(0).toUpperCase() }}
                  </span>
                </div>
              </button>

              <!-- User dropdown -->
              <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50">
                <router-link to="/profile" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">
                  Profile
                </router-link>
                <button
                  @click="handleLogout"
                  class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                >
                  Sign out
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main content -->
    <main class="flex-1">
      <router-view />
    </main>

    <!-- Loading overlay -->
    <div v-if="isLoading" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white p-6 rounded-lg shadow-lg">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p class="mt-4 text-gray-600">Loading...</p>
      </div>
    </div>

    <!-- Notification -->
    <div
      v-if="notification"
      class="fixed top-4 right-4 max-w-sm bg-white rounded-lg shadow-lg p-4 z-50"
      :class="notificationClass"
    >
      <div class="flex items-center">
        <div class="flex-shrink-0">
          <svg
            v-if="notification.type === 'success'"
            class="h-5 w-5 text-green-400"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clip-rule="evenodd"
            />
          </svg>
          <svg
            v-else-if="notification.type === 'error'"
            class="h-5 w-5 text-red-400"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clip-rule="evenodd"
            />
          </svg>
        </div>
        <div class="ml-3">
          <p class="text-sm font-medium text-gray-900">
            {{ notification.message }}
          </p>
        </div>
        <div class="ml-auto pl-3">
          <button @click="clearNotification" class="inline-flex text-gray-400 hover:text-gray-500">
            <span class="sr-only">Close</span>
            <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'

export default {
  name: 'HomeView',
  setup() {
    const authStore = useAuthStore()
    const notificationStore = useNotificationStore()

    const showUserMenu = ref(false)
    const isLoading = ref(false)

    const notification = computed(() => notificationStore.notification)
    const notificationClass = computed(() => ({
      'border-l-4 border-green-400': notification.value?.type === 'success',
      'border-l-4 border-red-400': notification.value?.type === 'error',
      'border-l-4 border-yellow-400': notification.value?.type === 'warning',
      'border-l-4 border-blue-400': notification.value?.type === 'info',
    }))

    const handleLogout = async () => {
      try {
        await authStore.logout()
        showUserMenu.value = false
      } catch (error) {
        console.error('Logout error:', error)
      }
    }

    const clearNotification = () => {
      notificationStore.clearNotification()
    }

    onMounted(() => {
      // Initialize authentication state
      authStore.initializeAuth()
    })

    return {
      authStore,
      showUserMenu,
      isLoading,
      notification,
      notificationClass,
      handleLogout,
      clearNotification,
    }
  },
}
</script>
