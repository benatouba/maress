<template>
  <v-card class="mx-auto my-12">
    <v-card-title>Create a new account</v-card-title>
    <v-card-text>
      <v-form
        @submit.prevent="handleRegister"
        @keyup.enter="handleRegister">
        <v-text-field
          v-model="email"
          label="Email"
          class="form-input"
          required />
        <v-text-field
          v-model="full_name"
          label="Full Name"
          class="form-input"
          required="required" />
        <v-text-field
          v-model="password"
          label="Password"
          type="password"
          class="form-input"
          required />
        <v-row>
          <v-col cols="12">
            <v-btn
              block
              color="primary"
              type="submit"
              :loading="authStore.loading">
              Create Account
            </v-btn>
          </v-col>
        </v-row>
        <v-row>
          <v-col
            cols="8"
            align-self="center">
            <span>Already have an account?</span>
          </v-col>
          <v-col cols="4">
            <v-btn
              text
              to="/login">
              Log in
            </v-btn>
          </v-col>
        </v-row>
      </v-form>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const full_name = ref('')
const email = ref('')
const password = ref('')

const handleRegister = async () => {
  const success = await authStore.register({
    email: email.value,
    full_name: full_name.value,
    password: password.value,
  })
  if (success) {
    router.push('/')
  }
}
</script>
