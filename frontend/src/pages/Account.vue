<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <!-- Header -->
        <div class="mb-6">
          <h2 class="text-h4 font-weight-bold">Account Settings</h2>
          <p class="text-subtitle-1 text-medium-emphasis">
            Manage your profile information and settings
          </p>
        </div>

        <!-- Profile Information Card -->
        <v-card class="mb-6" elevation="2">
          <v-card-title class="bg-primary">
            <v-icon class="mr-2">mdi-account</v-icon>
            Profile Information
          </v-card-title>
          <v-card-text class="pt-6">
            <v-form ref="profileForm" @submit.prevent="handleProfileUpdate">
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="profileData.full_name"
                    label="Full Name"
                    prepend-inner-icon="mdi-account"
                    variant="outlined"
                    :rules="[rules.required]"
                    :disabled="authStore.loading"
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="profileData.email"
                    label="Email"
                    prepend-inner-icon="mdi-email"
                    variant="outlined"
                    type="email"
                    :rules="[rules.required, rules.email]"
                    :disabled="authStore.loading"
                  />
                </v-col>
              </v-row>

              <!-- Zotero Settings -->
              <v-divider class="my-4" />
              <div class="text-h6 mb-4">
                <v-icon class="mr-2">mdi-bookshelf</v-icon>
                Zotero Integration
              </div>

              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="profileData.zotero_id"
                    label="Zotero User ID"
                    prepend-inner-icon="mdi-identifier"
                    variant="outlined"
                    hint="Your Zotero user or group ID"
                    persistent-hint
                    :disabled="authStore.loading"
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="profileData.zotero_api_key"
                    label="Zotero API Key"
                    prepend-inner-icon="mdi-key"
                    variant="outlined"
                    :type="showApiKey ? 'text' : 'password'"
                    :append-inner-icon="showApiKey ? 'mdi-eye-off' : 'mdi-eye'"
                    @click:append-inner="showApiKey = !showApiKey"
                    hint="Your Zotero API key (will be encrypted)"
                    persistent-hint
                    :disabled="authStore.loading"
                    :placeholder="isApiKeySet ? '****' : 'Enter API key'"
                  />
                </v-col>
              </v-row>

              <v-alert
                v-if="isApiKeySet"
                type="info"
                variant="tonal"
                class="mt-4"
                density="compact"
              >
                <v-icon class="mr-2">mdi-information</v-icon>
                Your API key is securely stored. Leave empty to keep current key, or enter a new one to update.
              </v-alert>

              <v-card-actions class="px-0 pt-6">
                <v-spacer />
                <v-btn
                  color="primary"
                  type="submit"
                  :loading="authStore.loading"
                  prepend-icon="mdi-content-save"
                >
                  Save Changes
                </v-btn>
              </v-card-actions>
            </v-form>
          </v-card-text>
        </v-card>

        <!-- Password Change Card -->
        <v-card elevation="2">
          <v-card-title class="bg-secondary">
            <v-icon class="mr-2">mdi-lock</v-icon>
            Change Password
          </v-card-title>
          <v-card-text class="pt-6">
            <v-form ref="passwordForm" @submit.prevent="handlePasswordUpdate">
              <v-row>
                <v-col cols="12">
                  <v-text-field
                    v-model="passwordData.current_password"
                    label="Current Password"
                    prepend-inner-icon="mdi-lock"
                    variant="outlined"
                    :type="showCurrentPassword ? 'text' : 'password'"
                    :append-inner-icon="showCurrentPassword ? 'mdi-eye-off' : 'mdi-eye'"
                    @click:append-inner="showCurrentPassword = !showCurrentPassword"
                    :rules="[rules.required, rules.minLength]"
                    :disabled="authStore.loading"
                    autocomplete="current-password"
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="passwordData.new_password"
                    label="New Password"
                    prepend-inner-icon="mdi-lock-plus"
                    variant="outlined"
                    :type="showNewPassword ? 'text' : 'password'"
                    :append-inner-icon="showNewPassword ? 'mdi-eye-off' : 'mdi-eye'"
                    @click:append-inner="showNewPassword = !showNewPassword"
                    :rules="[rules.required, rules.minLength]"
                    :disabled="authStore.loading"
                    autocomplete="new-password"
                    hint="At least 8 characters"
                    persistent-hint
                  />
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="confirmPassword"
                    label="Confirm New Password"
                    prepend-inner-icon="mdi-lock-check"
                    variant="outlined"
                    :type="showConfirmPassword ? 'text' : 'password'"
                    :append-inner-icon="showConfirmPassword ? 'mdi-eye-off' : 'mdi-eye'"
                    @click:append-inner="showConfirmPassword = !showConfirmPassword"
                    :rules="[rules.required, rules.passwordMatch]"
                    :disabled="authStore.loading"
                    autocomplete="new-password"
                  />
                </v-col>
              </v-row>

              <v-card-actions class="px-0 pt-6">
                <v-spacer />
                <v-btn
                  variant="outlined"
                  @click="resetPasswordForm"
                  :disabled="authStore.loading"
                >
                  Cancel
                </v-btn>
                <v-btn
                  color="secondary"
                  type="submit"
                  :loading="authStore.loading"
                  prepend-icon="mdi-lock-reset"
                >
                  Update Password
                </v-btn>
              </v-card-actions>
            </v-form>
          </v-card-text>
        </v-card>

        <!-- Account Status Card -->
        <v-card class="mt-6" elevation="2">
          <v-card-title>
            <v-icon class="mr-2">mdi-information</v-icon>
            Account Status
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <template #prepend>
                  <v-icon :color="user?.is_active ? 'success' : 'error'">
                    {{ user?.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
                  </v-icon>
                </template>
                <v-list-item-title>Account Status</v-list-item-title>
                <v-list-item-subtitle>
                  {{ user?.is_active ? 'Active' : 'Inactive' }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon :color="user?.is_superuser ? 'warning' : 'info'">
                    {{ user?.is_superuser ? 'mdi-shield-crown' : 'mdi-account' }}
                  </v-icon>
                </template>
                <v-list-item-title>User Role</v-list-item-title>
                <v-list-item-subtitle>
                  {{ user?.is_superuser ? 'Administrator' : 'Standard User' }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon>mdi-identifier</v-icon>
                </template>
                <v-list-item-title>Account ID</v-list-item-title>
                <v-list-item-subtitle>{{ user?.id }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const { user } = storeToRefs(authStore)

// Form refs
const profileForm = ref(null)
const passwordForm = ref(null)

// Profile data
const profileData = ref({
  full_name: '',
  email: '',
  zotero_id: '',
  zotero_api_key: ''
})

// Password data
const passwordData = ref({
  current_password: '',
  new_password: ''
})

const confirmPassword = ref('')

// Show/hide password fields
const showApiKey = ref(false)
const showCurrentPassword = ref(false)
const showNewPassword = ref(false)
const showConfirmPassword = ref(false)

// Check if API key is set
const isApiKeySet = computed(() => {
  return user.value?.zotero_api_key === '****'
})

// Validation rules
const rules = {
  required: value => !!value || 'This field is required',
  email: value => {
    const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return pattern.test(value) || 'Invalid email address'
  },
  minLength: value => {
    return value.length >= 8 || 'Must be at least 8 characters'
  },
  passwordMatch: value => {
    return value === passwordData.value.new_password || 'Passwords do not match'
  }
}

// Initialize form data from user
const initializeProfileData = () => {
  if (user.value) {
    profileData.value = {
      full_name: user.value.full_name || '',
      email: user.value.email || '',
      zotero_id: user.value.zotero_id || '',
      zotero_api_key: '' // Don't pre-fill API key
    }
  }
}

// Handle profile update
const handleProfileUpdate = async () => {
  const { valid } = await profileForm.value.validate()
  if (!valid) return

  // Prepare update data (exclude empty zotero_api_key if not changed)
  const updateData = {
    full_name: profileData.value.full_name,
    email: profileData.value.email,
    zotero_id: profileData.value.zotero_id || null
  }

  // Only include API key if user entered something
  if (profileData.value.zotero_api_key) {
    updateData.zotero_api_key = profileData.value.zotero_api_key
  }

  const success = await authStore.updateProfile(updateData)
  if (success) {
    // Clear API key field after successful update
    profileData.value.zotero_api_key = ''
  }
}

// Handle password update
const handlePasswordUpdate = async () => {
  const { valid } = await passwordForm.value.validate()
  if (!valid) return

  const success = await authStore.updatePassword({
    current_password: passwordData.value.current_password,
    new_password: passwordData.value.new_password
  })

  if (success) {
    resetPasswordForm()
  }
}

// Reset password form
const resetPasswordForm = () => {
  passwordData.value = {
    current_password: '',
    new_password: ''
  }
  confirmPassword.value = ''
  if (passwordForm.value) {
    passwordForm.value.reset()
  }
}

onMounted(() => {
  initializeProfileData()
})
</script>

<style scoped>
.v-card-title {
  font-weight: 600;
}
</style>
