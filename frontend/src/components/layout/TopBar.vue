<template>
  <v-app-bar app color="primary" dark>
    <template #prepend>
      <router-link to="/" aria-label="Home">
        <v-img width="100" cover src="@/assets/logo.svg" format="png" alt="UCO Logo" />
      </router-link>
    </template>
    <v-toolbar-title>MaRESS</v-toolbar-title>
    <v-btn text to="/items">Zotero</v-btn>
    <v-btn text to="/map">Map</v-btn>
    <v-spacer></v-spacer>
    <div v-if="authStore.isAuthenticated">
      <v-btn icon to="/profile">
        {{ authStore.user?.username?.charAt(0).toUpperCase() }}
      </v-btn>
      <v-btn text :active="authStore.loading" @click="handleLogout">Logout</v-btn>
    </div>
    <div v-else>
      <v-btn text to="/login">Login</v-btn>
      <v-btn text to="/signup">Sign Up</v-btn>
    </div>
    <v-spacer></v-spacer>
  </v-app-bar>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'

const showUserMenu = ref(false)
const authStore = useAuthStore()
const handleLogout = async () => {
  try {
    authStore.logout()
    showUserMenu.value = false
  } catch (error) {
    console.error('Logout error:', error)
  }
}
</script>

<style scoped></style>
