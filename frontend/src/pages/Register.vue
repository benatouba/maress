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
        lg="5">
        <v-card
          elevation="8"
          rounded="lg">
          <!-- Header -->
          <v-card-title class="text-h5 text-center pa-6 bg-primary">
            <span class="text-white">Create Your Account</span>
          </v-card-title>

          <v-card-subtitle class="text-center pa-4">
            Join us to start your research journey
          </v-card-subtitle>

          <v-divider />

          <!-- Form -->
          <v-card-text class="pa-6">
            <v-form
              ref="formRef"
              v-model="formValid"
              @submit.prevent="handleRegister">
              <!-- Full Name Field -->
              <v-text-field
                v-model="fullName"
                :rules="fullNameRules"
                label="Full Name"
                placeholder="Enter your full name"
                variant="outlined"
                prepend-inner-icon="mdi-account"
                density="comfortable"
                class="mb-3"
                :disabled="authStore.loading"
                autocomplete="name"
                required />

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
                :disabled="authStore.loading"
                autocomplete="email"
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
                autocomplete="new-password"
                required
                @update:model-value="validatePasswordStrength"
                @click:append-inner="showPassword = !showPassword" />

              <!-- Password Strength Indicator -->
              <div
                v-if="password"
                class="mb-3">
                <div class="text-caption mb-1">
                  Password Strength: {{ passwordStrength.text }}
                </div>
                <v-progress-linear
                  :model-value="passwordStrength.value"
                  :color="passwordStrength.color"
                  height="6"
                  rounded />
                <div class="text-caption mt-1 text-medium-emphasis">
                  <v-icon
                    size="x-small"
                    :color="hasMinLength ? 'success' : 'grey'">
                    {{ hasMinLength ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                  </v-icon>
                  At least 8 characters
                  <v-icon
                    size="x-small"
                    class="ml-2"
                    :color="hasUpperCase ? 'success' : 'grey'">
                    {{ hasUpperCase ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                  </v-icon>
                  One uppercase letter
                  <v-icon
                    size="x-small"
                    class="ml-2"
                    :color="hasNumber ? 'success' : 'grey'">
                    {{ hasNumber ? 'mdi-check-circle' : 'mdi-circle-outline' }}
                  </v-icon>
                  One number
                </div>
              </div>

              <!-- Confirm Password Field -->
              <v-text-field
                v-model="confirmPassword"
                :rules="confirmPasswordRules"
                :type="showConfirmPassword ? 'text' : 'password'"
                label="Confirm Password"
                placeholder="Re-enter your password"
                variant="outlined"
                prepend-inner-icon="mdi-lock-check"
                :append-inner-icon="showConfirmPassword ? 'mdi-eye-off' : 'mdi-eye'"
                density="comfortable"
                class="mb-4"
                :disabled="authStore.loading"
                required
                @click:append-inner="showConfirmPassword = !showConfirmPassword" />

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
                  mdi-account-plus
                </v-icon>
                Create Account
              </v-btn>
            </v-form>
          </v-card-text>

          <v-divider />

          <!-- Footer -->
          <v-card-actions class="pa-6 justify-center">
            <span class="text-body-2 text-medium-emphasis">
              Already have an account?
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
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

// Form refs and state
const formRef = ref()
const formValid = ref(false)
const fullName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)

// Password strength indicators
const hasMinLength = computed(() => password.value.length >= 8)
const hasUpperCase = computed(() => /[A-Z]/.test(password.value))
const hasNumber = computed(() => /[0-9]/.test(password.value))
const hasSpecialChar = computed(() => /[!@#$%^&*(),.?":{}|<>]/.test(password.value))

// Password strength calculation
const passwordStrength = computed(() => {
  if (!password.value) {
    return { value: 0, color: 'grey', text: 'None' }
  }

  let strength = 0
  if (hasMinLength.value) strength += 25
  if (hasUpperCase.value) strength += 25
  if (hasNumber.value) strength += 25
  if (hasSpecialChar.value) strength += 25

  if (strength <= 25) {
    return { value: strength, color: 'error', text: 'Weak' }
  } else if (strength <= 50) {
    return { value: strength, color: 'warning', text: 'Fair' }
  } else if (strength <= 75) {
    return { value: strength, color: 'info', text: 'Good' }
  } else {
    return { value: strength, color: 'success', text: 'Strong' }
  }
})

// Validation rules
const fullNameRules = [
  (v: string) => !!v || 'Full name is required',
  (v: string) => v.length >= 2 || 'Full name must be at least 2 characters',
]

const emailRules = [
  (v: string) => !!v || 'Email is required',
  (v: string) => /.+@.+\..+/.test(v) || 'Email must be valid',
]

const passwordRules = [
  (v: string) => !!v || 'Password is required',
  (v: string) => v.length >= 8 || 'Password must be at least 8 characters',
  (v: string) => /[A-Z]/.test(v) || 'Password must contain at least one uppercase letter',
  (v: string) => /[0-9]/.test(v) || 'Password must contain at least one number',
]

const confirmPasswordRules = [
  (v: string) => !!v || 'Please confirm your password',
  (v: string) => v === password.value || 'Passwords do not match',
]

// Validate password strength (for triggering re-validation)
const validatePasswordStrength = () => {
  // Force re-validation of confirm password when password changes
  if (confirmPassword.value) {
    formRef.value?.validate()
  }
}

// Handle registration
const handleRegister = async () => {
  // Validate form
  const { valid } = await formRef.value.validate()
  if (!valid) return

  const success = await authStore.register({
    email: email.value,
    full_name: fullName.value,
    password: password.value,
  })

  if (success) {
    router.push('/')
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
