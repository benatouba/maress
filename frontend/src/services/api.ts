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
api.interceptors.response.use(response => response, error => {
  // You can add global error handling here
  return Promise.reject(error)
})

export default api
