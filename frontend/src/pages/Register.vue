<template>
  <div class="max-w-md mx-auto p-6">
    <h2 class="text-2xl font-semibold mb-4">Create a new account</h2>
    <form @submit.prevent="handleRegister" class="space-y-4">
      <div><label class="form-label">Username</label><input v-model="username" type="text" class="form-input" required /></div>
      <div><label class="form-label">Email</label><input v-model="email" type="email" class="form-input" required /></div>
      <div><label class="form-label">Password</label><input v-model="password" type="password" class="form-input" required /></div>
      <button type="submit" class="btn btn-primary w-full">Sign up</button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const username = ref('')
const email = ref('')
const password = ref('')

const handleRegister = async () => {
  const success = await authStore.register({ username: username.value, email: email.value, password: password.value })
  if (success) {
    router.push('/')
  }
}
</script>
