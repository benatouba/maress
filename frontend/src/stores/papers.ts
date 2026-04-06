import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '@/services/api'
import { useNotificationStore } from './notification'
import logger from '@/utils/logger'

interface Paper {
  id: string
  title: string
  abstract?: string
  authors?: string[]
  journal?: string
  [key: string]: unknown
}

interface PaperFilters {
  search: string
  author: string
  journal: string
  country: string
  dateFrom: string | null
  dateTo: string | null
}

export const usePapersStore = defineStore('papers', () => {
  const papers = ref<Paper[]>([])
  const currentPaper = ref<Paper | null>(null)
  const loading = ref(false)
  const filters = ref<PaperFilters>({
    search: '',
    author: '',
    journal: '',
    country: '',
    dateFrom: null,
    dateTo: null
  })

  const filteredPapers = computed(() => {
    let filtered = papers.value

    if (filters.value.search) {
      const search = filters.value.search.toLowerCase()
      filtered = filtered.filter(paper =>
        paper.title.toLowerCase().includes(search) ||
        paper.abstract?.toLowerCase().includes(search) ||
        paper.authors?.some(author => author.toLowerCase().includes(search))
      )
    }

    if (filters.value.author) {
      const author = filters.value.author.toLowerCase()
      filtered = filtered.filter(paper =>
        paper.authors?.some(a => a.toLowerCase().includes(author))
      )
    }

    if (filters.value.journal) {
      const journal = filters.value.journal.toLowerCase()
      filtered = filtered.filter(paper =>
        paper.journal?.toLowerCase().includes(journal)
      )
    }

    return filtered
  })

  const fetchPapers = async (params = {}) => {
    loading.value = true
    try {
      const response = await axios.get('/papers', { params })
      papers.value = response.data
    } catch (error) {
      logger.error('Error fetching papers:', error)
    } finally {
      loading.value = false
    }
  }

  const fetchPaper = async (id: string) => {
    loading.value = true
    try {
      const response = await axios.get(`/papers/${id}`)
      currentPaper.value = response.data
      return response.data
    } catch (error) {
      logger.error('Error fetching paper:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  const createPaper = async (paperData: Partial<Paper>) => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.post('/papers', paperData)
      papers.value.push(response.data)
      notificationStore.showNotification('Paper created successfully!', 'success')
      return response.data
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Failed to create paper',
        'error'
      )
      return null
    } finally {
      loading.value = false
    }
  }

  const updatePaper = async (id: string, paperData: Partial<Paper>) => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.put(`/papers/${id}`, paperData)
      const index = papers.value.findIndex(p => p.id === id)
      if (index !== -1) {
        papers.value[index] = response.data
      }
      if (currentPaper.value?.id === id) {
        currentPaper.value = response.data
      }
      notificationStore.showNotification('Paper updated successfully!', 'success')
      return response.data
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Failed to update paper',
        'error'
      )
      return null
    } finally {
      loading.value = false
    }
  }

  const deletePaper = async (id: string) => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      await axios.delete(`/papers/${id}`)
      papers.value = papers.value.filter(p => p.id !== id)
      if (currentPaper.value?.id === id) {
        currentPaper.value = null
      }
      notificationStore.showNotification('Paper deleted successfully!', 'success')
      return true
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Failed to delete paper',
        'error'
      )
      return false
    } finally {
      loading.value = false
    }
  }

  const processLocations = async (id: string) => {
    const notificationStore = useNotificationStore()

    try {
      await axios.post(`/papers/${id}/process-locations`)
      notificationStore.showNotification('Location processing started!', 'info')
      return true
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } }
      notificationStore.showNotification(
        axiosError.response?.data?.detail || 'Failed to start location processing',
        'error'
      )
      return false
    }
  }

  const getPaperLocations = async (id: string) => {
    try {
      const response = await axios.get(`/papers/${id}/locations`)
      return response.data
    } catch (error) {
      logger.error('Error fetching paper locations:', error)
      return []
    }
  }

  const updateFilters = (newFilters: Partial<PaperFilters>) => {
    filters.value = { ...filters.value, ...newFilters }
  }

  const clearFilters = () => {
    filters.value = {
      search: '',
      author: '',
      journal: '',
      country: '',
      dateFrom: null,
      dateTo: null
    }
  }

  return {
    papers,
    currentPaper,
    loading,
    filters,
    filteredPapers,
    fetchPapers,
    fetchPaper,
    createPaper,
    updatePaper,
    deletePaper,
    processLocations,
    getPaperLocations,
    updateFilters,
    clearFilters
  }
})
