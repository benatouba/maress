import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_V1_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor to attach auth token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => {
  return Promise.reject(error)
})

// Response interceptor to handle errors globally
api.interceptors.response.use(
  response => response,
  error => {
    // Handle authentication errors
    if (error.response?.status === 401 || error.response?.status === 403) {
      // Check if it's an authentication error (not a permission error)
      const detail = error.response?.data?.detail || ''
      if (
        detail.includes('credentials') ||
        detail.includes('token') ||
        detail.includes('authenticate')
      ) {
        // Token is invalid/expired - clear auth and notify app
        const hadToken = !!localStorage.getItem('token')
        localStorage.removeItem('token')

        // Do not force navigation for public/anonymous views.
        // Show notification only if there was an authenticated session.
        if (hadToken) {
          const event = new CustomEvent('auth:expired', {
            detail: { message: 'Your session has expired. Please log in again.' }
          })
          window.dispatchEvent(event)
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api
