/// <reference types="vite/client" />
/// <reference types="unplugin-vue-router/client" />
/// <reference types="vite-plugin-vue-layouts-next/client" />

declare global {
  // User interface
  export interface User {
    id: string | number
    email: string
    full_name?: string
    is_active?: boolean
    is_superuser?: boolean
    created_at?: string
    updated_at?: string
  }

  // Authentication credentials interfaces
  export interface LoginCredentials {
    email: string
    password: string
  }

  export interface RegisterData {
    email: string
    password: string
    full_name?: string
  }

  export interface UpdateProfileData {
    email?: string
    full_name?: string
  }

  // API response interfaces
  export interface LoginResponse {
    access_token: string
    token_type: string
  }

  export interface RegisterResponse {
    access_token: string
    token_type: string
    user: User
  }

  // API error response interface
  export interface ApiErrorResponse {
    detail: string
  }

  // Define the notification type
  export interface Notification {
    message: string
    type: NotificationType
  }

  // Define allowed notification types
  export type NotificationType = 'info' | 'success' | 'warning' | 'error'

}

export {}
