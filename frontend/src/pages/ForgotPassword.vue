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
            <span class="text-white">Reset Password</span>
          </v-card-title>

          <v-card-subtitle class="text-center pa-4">
            Enter your email to receive password reset instructions
          </v-card-subtitle>

          <v-divider />

          <!-- Form -->
          <v-card-text class="pa-6">
            <v-form
              ref="formRef"
              v-model="formValid"
              @submit.prevent="handleResetRequest">
              <!-- Email Field -->
              <v-text-field
                v-model="email"
                :rules="emailRules"
                label="Email Address"
                placeholder="Enter your email"
                type="email"
                variant="outlined"
                prepend-inner-icon="mdi-email"
                density="comfortable"
                class="mb-3"
                :disabled="loading"
                autocomplete="email"
                required />

              <!-- Success Message -->
              <v-alert
                v-if="showSuccess"
                type="success"
                variant="tonal"
                class="mb-4"
                closable
                @click:close="showSuccess = false">
                If an account with that email exists, you will receive password reset instructions shortly.
              </v-alert>

              <!-- Submit Button -->
              <v-btn
                block
                color="primary"
                size="large"
                type="submit"
                :loading="loading"
                :disabled="!formValid || loading">
                <v-icon
                  left
                  class="mr-2">
                  mdi-email-send
                </v-icon>
                Send Reset Link
              </v-btn>
            </v-form>
          </v-card-text>

          <v-divider />

          <!-- Footer -->
          <v-card-actions class="pa-6 justify-center">
            <span class="text-body-2 text-medium-emphasis">
              Remember your password?
            </span>
            <v-btn
              variant="text"
              color="primary"
              to="/login">
              Sign In
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useNotificationStore } from '@/stores/notification'

const notificationStore = useNotificationStore()

// Form refs and state
const formRef = ref()
const formValid = ref(false)
const email = ref('')
const loading = ref(false)
const showSuccess = ref(false)

// Validation rules
const emailRules = [
  (v: string) => !!v || 'Email is required',
  (v: string) => /.+@.+\..+/.test(v) || 'Email must be valid',
]

// Handle password reset request
const handleResetRequest = async () => {
  // Validate form
  const { valid } = await formRef.value.validate()
  if (!valid) return

  loading.value = true

  try {
    // TODO: Implement password reset API call
    // await authStore.requestPasswordReset(email.value)

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1500))

    showSuccess.value = true
    email.value = ''
    formRef.value.reset()

    notificationStore.showNotification(
      'Password reset instructions sent',
      'success',
      5000
    )
  } catch (error) {
    notificationStore.showNotification(
      'Failed to send reset instructions. Please try again.',
      'error',
      5000
    )
  } finally {
    loading.value = false
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
