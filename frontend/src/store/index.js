import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

export const useAppStore = defineStore('app', () => {
  // State
  const isLoading = ref(false)
  const error = ref(null)
  const papers = ref([])
  const selectedPaper = ref(null)
  const mapCenter = ref([51.505, -0.09]) // Default to London
  const mapZoom = ref(2)

  // Getters
  const processedPapers = computed(() => 
    papers.value.filter(paper => paper.processed)
  )
  
  const unprocessedPapers = computed(() => 
    papers.value.filter(paper => !paper.processed)
  )

  const papersWithLocations = computed(() => 
    papers.value.filter(paper => paper.locations && paper.locations.length > 0)
  )

  // Actions
  async function fetchPapers() {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await api.get('/papers/')
      papers.value = response.data
    } catch (err) {
      error.value = err.message
      console.error('Error fetching papers:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchPaper(id) {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await api.get(`/papers/${id}`)
      selectedPaper.value = response.data
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('Error fetching paper:', err)
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function importFromZotero(collectionKey = null, limit = 50) {
    isLoading.value = true
    error.value = null
    
    try {
      const params = { limit }
      if (collectionKey) {
        params.collection_key = collectionKey
      }
      
      const response = await api.post('/papers/import-from-zotero', null, { params })
      await fetchPapers() // Refresh papers list
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('Error importing from Zotero:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function processPaper(paperId) {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await api.post(`/papers/${paperId}/process`)
      return response.data
    } catch (err) {
      error.value = err.message
      console.error('Error processing paper:', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function setMapView(center, zoom) {
    mapCenter.value = center
    mapZoom.value = zoom
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    isLoading,
    error,
    papers,
    selectedPaper,
    mapCenter,
    mapZoom,
    
    // Getters
    processedPapers,
    unprocessedPapers,
    papersWithLocations,
    
    // Actions
    fetchPapers,
    fetchPaper,
    importFromZotero,
    processPaper,
    setMapView,
    clearError
  }
})