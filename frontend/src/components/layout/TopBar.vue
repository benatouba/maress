<template>
  <v-app-bar color="primary" theme="dark">
    <template #prepend>
      <router-link to="/" aria-label="Home">
        <v-img width="100" cover src="/logo.png" alt="NFDI4Earth Logo" />
      </router-link>
    </template>
    <v-toolbar-title>MaRESS</v-toolbar-title>
    <v-btn variant="text" to="/items">Papers</v-btn>
    <v-btn variant="text" to="/map">Map</v-btn>
    <v-btn variant="text" to="/graph">Graph</v-btn>
    <v-btn v-if="authStore.isAuthenticated" variant="text" to="/tasks">
      Tasks
      <v-badge
        v-if="taskStore.hasTasks"
        :content="taskStore.taskCount"
        color="error"
        inline
        class="ml-1"
      />
    </v-btn>
    <v-spacer></v-spacer>
    <!-- Theme Toggle -->
    <v-btn icon @click="toggleTheme">
      <v-icon>{{ isDark ? 'mdi-weather-sunny' : 'mdi-weather-night' }}</v-icon>
    </v-btn>
    <div v-if="authStore.isAuthenticated">
      <!-- User Menu -->
      <v-menu offset-y>
        <template #activator="{ props }">
          <v-btn icon v-bind="props">
            <v-avatar color="secondary" size="40">
              <span class="text-h6">
                {{ userInitial }}
              </span>
            </v-avatar>
          </v-btn>
        </template>
        <v-list>
          <v-list-item>
            <v-list-item-title class="font-weight-bold">
              {{ authStore.user?.full_name || 'User' }}
            </v-list-item-title>
            <v-list-item-subtitle>
              {{ authStore.user?.email }}
            </v-list-item-subtitle>
          </v-list-item>
          <v-divider />
          <v-list-item to="/account" prepend-icon="mdi-account-cog">
            <v-list-item-title>Account Settings</v-list-item-title>
          </v-list-item>
          <v-divider />
          <v-list-item @click="handleLogout" prepend-icon="mdi-logout">
            <v-list-item-title>Logout</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </div>
    <div v-else>
      <v-btn variant="text" to="/login">Login</v-btn>
      <v-btn variant="text" to="/register">Sign Up</v-btn>
    </div>
  </v-app-bar>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from 'vuetify'
import { useAuthStore } from '@/stores/auth'
import { useTaskStore } from '@/stores/tasks'

const router = useRouter()
const theme = useTheme()
const authStore = useAuthStore()
const taskStore = useTaskStore()

const isDark = computed(() => theme.global.name.value === 'dark')

const toggleTheme = () => {
  theme.global.name.value = isDark.value ? 'light' : 'dark'
}

// Get user initial for avatar
const userInitial = computed(() => {
  const fullName = authStore.user?.full_name
  if (fullName) {
    return fullName.charAt(0).toUpperCase()
  }
  const email = authStore.user?.email
  if (email) {
    return email.charAt(0).toUpperCase()
  }
  return 'U'
})

// Handle logout
const handleLogout = () => {
  authStore.logout()
  router.push('/')
}
</script>

<style scoped></style>
