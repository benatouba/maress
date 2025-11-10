import { defineStore } from 'pinia'
import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { type AxiosError } from 'axios'
import axios from '@/services/api'

import { useNotificationStore } from './notification'

// User interface
export interface User {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
}

// Login credentials
export interface LoginCredentials {
  email: string
  password: string
}

// Register data
export interface RegisterData {
  email: string
  full_name: string
  password: string
}

// Update profile data
export interface UpdateProfileData {
  full_name?: string
  email?: string
}

// API response types
export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface RegisterResponse {
  user: User
}

export interface ApiErrorResponse {
  detail: string
}

// Auth store interface for better intellisense
export interface AuthStore {
  user: Ref<User | null>
  token: Ref<string | null>
  loading: Ref<boolean>
  isAuthenticated: ComputedRef<boolean>
  login: (credentials: LoginCredentials) => Promise<boolean>
  register: (userData: RegisterData) => Promise<boolean>
  logout: () => void
  fetchUser: () => Promise<void>
  updateProfile: (userData: UpdateProfileData) => Promise<boolean>
  initializeAuth: () => Promise<void>
}

export const useAuthStore = defineStore('auth', (): AuthStore => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))
  const loading = ref<boolean>(false)

  const isAuthenticated = computed<boolean>(() => !!token.value)

  // Set auth header for axios
  const setAuthHeader = (authToken: string | null): void => {
    if (authToken) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`
    } else {
      delete axios.defaults.headers.common['Authorization']
    }
  }

  // Initialize authentication
  const initializeAuth = async (): Promise<void> => {
    if (token.value) {
      setAuthHeader(token.value)
      try {
        await fetchUser()
      } catch (error: unknown) {
        // Token is invalid, clear it
        logout()
        throw error
      }
    }
  }

  // Login
  const login = async (credentials: LoginCredentials): Promise<boolean> => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const params = new URLSearchParams()
      params.append('grant_type', 'password')
      params.append('username', credentials.email)
      params.append('password', credentials.password)
      params.append('scope', '')

      const response = await axios.post<LoginResponse>('/login/access-token', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })

      const { access_token } = response.data
      token.value = access_token
      localStorage.setItem('token', access_token)
      setAuthHeader(access_token)

      await fetchUser()
      notificationStore.showNotification('Successfully logged in!', 'success')
      return true
    } catch (error) {
      const axiosError = error as AxiosError<ApiErrorResponse>
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Login failed',
        'error',
      )
      return false
    } finally {
      loading.value = false
    }
  }

  // Register
  const register = async (userData: RegisterData): Promise<boolean> => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.post<RegisterResponse>('/users/signup', userData)
      const { user } = response.data

      notificationStore.showNotification(
        `Registration successful! Welcome ${user.full_name}!`,
        'success',
      )

      // Auto-login after successful registration
      loading.value = false // Reset loading before login
      const loginSuccess = await login({
        email: userData.email,
        password: userData.password,
      })

      return loginSuccess
    } catch (error) {
      const axiosError = error as AxiosError<ApiErrorResponse>
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Registration failed',
        'error',
      )
      return false
    } finally {
      loading.value = false
    }
  }

  // Logout
  const logout = (): void => {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
    setAuthHeader(null)
  }

  // Fetch current user
  const fetchUser = async (): Promise<void> => {
    const response = await axios.get<User>('/users/me')
    user.value = response.data
  }

  // Update user profile
  const updateProfile = async (userData: UpdateProfileData): Promise<boolean> => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.patch<User>('/users/me', userData)
      user.value = response.data
      notificationStore.showNotification('Profile updated successfully!', 'success')
      return true
    } catch (error) {
      const axiosError = error as AxiosError<ApiErrorResponse>
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Profile update failed',
        'error',
      )
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    user,
    token,
    loading,
    isAuthenticated,
    login,
    register,
    logout,
    fetchUser,
    updateProfile,
    initializeAuth,
  }
})
