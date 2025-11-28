<template>
  <v-container
    class="fill-height"
    fluid>
    <v-row
      align="center"
      justify="center">
      <v-col
        cols="12"
        sm="8"
        md="6"
        lg="4">
        <v-card
          elevation="8"
          rounded="lg">
          <!-- Header -->
          <v-card-title class="text-h5 text-center pa-6 bg-primary">
            <span class="text-white">Welcome Back</span>
          </v-card-title>

          <v-card-subtitle class="text-center pa-4">
            Sign in to your account to continue
          </v-card-subtitle>

          <v-divider />

          <!-- Form -->
          <v-card-text class="pa-6">
            <v-form
              ref="formRef"
              v-model="formValid"
              @submit.prevent="handleLogin">
              <v-text-field
                v-model="email"
                :rules="emailRules"
                label="Email Address"
                placeholder="Enter your email"
                type="text"
                variant="outlined"
                prepend-inner-icon="mdi-email"
                density="comfortable"
                class="mb-3"
                :disabled="authStore.loading"
                autocomplete="username"
                required />

              <!-- Password Field -->
              <v-text-field
                v-model="password"
                :rules="passwordRules"
                :type="showPassword ? 'text' : 'password'"
                label="Password"
                placeholder="Enter your password"
                variant="outlined"
                prepend-inner-icon="mdi-lock"
                :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                density="comfortable"
                class="mb-2"
                :disabled="authStore.loading"
                name="password"
                autocomplete="current-password"
                required
                @click:append-inner="showPassword = !showPassword" />

              <!-- Submit Button -->
              <v-btn
                block
                color="primary"
                size="large"
                type="submit"
                :loading="authStore.loading"
                :disabled="!formValid || authStore.loading">
                <v-icon
                  left
                  class="mr-2">
                  mdi-login
                </v-icon>
                Sign In
              </v-btn>
            </v-form>
          </v-card-text>

          <v-divider />

          <!-- Footer -->
          <v-card-actions class="pa-6 justify-center">
            <span class="text-body-2 text-medium-emphasis">
              Don't have an account?
            </span>
            <v-btn
              variant="text"
              color="primary"
              to="/register">
              Sign Up
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter, useRoute } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

// Form refs and state
const formRef = ref()
const formValid = ref(false)
const email = ref('')
const password = ref('')
const showPassword = ref(false)

// Validation rules
const emailRules = [
  (v: string) => !!v || 'Email is required',
  (v: string) => /.+@.+\..+/.test(v) || 'Email must be valid',
]

const passwordRules = [
  (v: string) => !!v || 'Password is required',
  (v: string) => v.length >= 6 || 'Password must be at least 6 characters',
]

// Handle login
const handleLogin = async () => {
  // Validate form
  const { valid } = await formRef.value.validate()
  if (!valid) return

  const success = await authStore.login({
    email: email.value,
    password: password.value,
  })

  if (success) {
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  }
}
</script>

<style scoped>
.fill-height {
  min-height: 100vh;
}

.bg-primary {
  background-color: rgb(var(--v-theme-primary)) !important;
}

.text-white {
  color: white !important;
}
</style>
