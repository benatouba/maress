<template>
  <v-card
    class="mx-auto my-12"
    max-width="400"
    elevation="3">
    <v-card-title>Sign in to your account</v-card-title>
    <v-card-text>
      <v-form
        @submit.prevent="handleLogin"
        @keyup.enter="handleLogin">
        <v-text-field
          v-model="email"
          class="form-input"
          label="Email"
          placeholder="Enter your email"
          type="email"
          required></v-text-field>
        <v-text-field
          v-model="password"
          class="form-input"
          label="Password"
          placeholder="Enter your password"
          type="password"
          required></v-text-field>
        <v-row>
          <v-col
            cols="12"
            justify-center>
            <v-btn
              block
              color="primary"
              type="submit"
              :loading="authStore.loading">
              Sign in
            </v-btn>
          </v-col>
        </v-row>
        <v-row>
          <v-col
            cols="8"
            align-self="center">
            <span>Don't have an account yet?</span>
          </v-col>
          <v-col cols="4">
            <v-btn
              text
              to="/register">
              Sign up
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
import { useRouter, useRoute } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')

const handleLogin = async () => {
  const success = await authStore.login({ email: email.value, password: password.value })
  if (success) {
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  }
}
</script>
