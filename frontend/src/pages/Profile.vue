<template>
  <v-row justify="center">
    <v-col cols="12" md="8" lg="6">
      <!-- Profile Header Card -->
      <v-card class="profile-card" elevation="4">
        <!-- Cover Image -->
        <v-img height="200" :src="coverImage" gradient="to bottom, rgba(0,0,0,.1), rgba(0,0,0,.5)">
          <div class="d-flex justify-end pa-4">
            <v-btn icon size="small" color="white" @click="editMode = !editMode">
              <v-icon>mdi-pencil</v-icon>
            </v-btn>
          </div>
        </v-img>

        <!-- Profile Avatar and Basic Info -->
        <div class="profile-avatar-section">
          <v-avatar size="120" class="profile-avatar" :color="user?.full_name ? 'primary' : 'grey-lighten-1'">
            <v-img v-if="user?.avatar" :src="user.avatar" :alt="user.full_name || 'User Avatar'" />
            <span v-else class="text-h4 font-weight-light">
              {{ getInitials(user?.full_name || user?.email) }}
            </span>
          </v-avatar>

          <div class="profile-header-content">
            <v-card-title class="text-h4 font-weight-bold pa-0 mb-1">
              {{ user?.full_name || 'Anonymous User' }}
            </v-card-title>

            <v-card-subtitle class="pa-0 mb-2">
              <v-icon size="small" class="me-1">mdi-email</v-icon>
              {{ user?.email }}
            </v-card-subtitle>

            <div class="d-flex align-center gap-2 mb-3">
              <v-chip v-if="user?.is_superuser" size="small" color="warning" variant="flat">
                <v-icon start size="small">mdi-shield-crown</v-icon>
                Admin
              </v-chip>
            </div>
          </div>
        </div>

        <v-divider />

        <!-- Profile Details -->
        <v-card-text class="pt-6">
          <!-- Edit Form -->
          <v-form v-if="editMode" @submit.prevent="handleUpdate" ref="profileForm">
            <v-row>
              <v-col cols="12">
                <v-text-field
                  v-model="formData.full_name"
                  label="Full Name"
                  prepend-inner-icon="mdi-account"
                  variant="outlined"
                  :rules="[rules.maxLength(255)]"
                  counter="255"
                />
              </v-col>

              <v-col cols="12">
                <v-text-field
                  v-model="formData.email"
                  label="Email Address"
                  prepend-inner-icon="mdi-email"
                  variant="outlined"
                  type="email"
                  :rules="[rules.required, rules.email, rules.maxLength(255)]"
                  counter="255"
                />
              </v-col>
            </v-row>

            <div class="d-flex gap-3 mt-4">
              <v-btn type="submit" color="primary" :loading="loading" prepend-icon="mdi-check"> Save Changes </v-btn>
              <v-btn color="secondary" variant="outlined" @click="cancelEdit" prepend-icon="mdi-close"> Cancel </v-btn>
            </div>
          </v-form>

          <!-- View Mode -->
          <div v-else>
            <v-row>
              <v-col cols="12" sm="6">
                <div class="profile-field">
                  <v-icon class="field-icon" color="primary">mdi-account</v-icon>
                  <div>
                    <div class="field-label">Full Name</div>
                    <div class="field-value">
                      {{ user?.full_name || 'Not provided' }}
                    </div>
                  </div>
                </div>
              </v-col>

              <v-col cols="12" sm="6">
                <div class="profile-field">
                  <v-icon class="field-icon" color="primary">mdi-email</v-icon>
                  <div>
                    <div class="field-label">Email Address</div>
                    <div class="field-value">{{ user?.email }}</div>
                  </div>
                </div>
              </v-col>
            </v-row>

            <!-- Change Password Section -->
            <v-divider class="my-6" />

            <h3 class="text-h6 mb-4">Security</h3>
            <v-btn color="secondary" variant="outlined" prepend-icon="mdi-lock" @click="showPasswordDialog = true">
              Change Password
            </v-btn>
          </div>
        </v-card-text>
      </v-card>

      <!-- Password Change Dialog -->
      <v-dialog v-model="showPasswordDialog" max-width="500">
        <v-card>
          <v-card-title>Change Password</v-card-title>
          <v-form @submit.prevent="handlePasswordUpdate" ref="passwordForm">
            <v-card-text>
              <v-text-field
                v-model="passwordData.current_password"
                label="Current Password"
                type="password"
                variant="outlined"
                :rules="[rules.required, rules.minLength(8)]"
                class="mb-4"
              />
              <v-text-field
                v-model="passwordData.new_password"
                label="New Password"
                type="password"
                variant="outlined"
                :rules="[rules.required, rules.minLength(8), rules.maxLength(40)]"
              />
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn color="secondary" variant="text" @click="showPasswordDialog = false"> Cancel </v-btn>
              <v-btn color="primary" type="submit" :loading="passwordLoading"> Update Password </v-btn>
            </v-card-actions>
          </v-form>
        </v-card>
      </v-dialog>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const fullName = ref('')
const institution = ref('')
const researchInterests = ref('')

const coverImage = computed(() => {
  return 'https://images.unsplash.com/photo-1557804506-669a67965ba0?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80'
})
const user = computed(() => authStore.user)
const editMode = ref(false)
const loading = ref(false)
const passwordLoading = ref(false)
const showPasswordDialog = ref(false)

const formData = reactive({
  full_name: '',
  email: '',
})

const rules = {
  required: (value: string) => !!value || 'This field is required',
  email: (value: string) => {
    const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return pattern.test(value) || 'Please enter a valid email address'
  },
  minLength: (min: number) => (value: string) => value.length >= min || `Minimum ${min} characters required`,
  maxLength: (max: number) => (value: string) => value.length <= max || `Maximum ${max} characters allowed`,
}

const getInitials = (name: string): string => {
  if (!name) return '?'
  return name
    .split(' ')
    .map(word => word.charAt(0).toUpperCase())
    .slice(0, 2)
    .join('')
}

onMounted(() => {
  if (authStore.user) {
    fullName.value = authStore.user.full_name || ''
  }
})

const handleUpdate = async () => {
  const updated = await authStore.updateProfile({
    full_name: formData.full_name,
    email: formData.email,
  })
  if (updated) {
    editMode.value = false
  }
}
</script>
