import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useNotificationStore } from './notification'

export interface StudySite {
  id: string
  item_id: string
  name: string | null
  latitude?: number
  longitude?: number
  location_id: string
  confidence_score: number
  validation_score: number
  context: string
  extraction_method: string
  source_type: string
  section: string
  is_manual: boolean
  created_at: string
  updated_at: string
}

export interface StudySiteCreate {
  name: string
  latitude: number
  longitude: number
  context?: string
  confidence_score?: number
  validation_score?: number
}

export interface StudySiteUpdate {
  name?: string
  latitude?: number
  longitude?: number
  context?: string
  confidence_score?: number
  validation_score?: number
}

export interface StudySiteWithItem extends StudySite {
  item_title?: string
  item?: any
}

export const useStudySitesStore = defineStore('studySites', () => {
  const studySites = ref<StudySiteWithItem[]>([])
  const currentStudySite = ref<StudySite | null>(null)
  const loading = ref(false)

  const notificationStore = useNotificationStore()

  // Get study sites grouped by is_manual flag
  const manualStudySites = computed(() =>
    studySites.value.filter(site => site.is_manual)
  )

  const automaticStudySites = computed(() =>
    studySites.value.filter(site => !site.is_manual)
  )

  /**
   * Fetch all study sites for a specific item
   */
  const fetchItemStudySites = async (itemId: string): Promise<StudySite[]> => {
    loading.value = true
    try {
      const response = await api.get(`/study-sites/items/${itemId}/study-sites`)
      return response.data.data || []
    } catch (error: any) {
      console.error('Error fetching item study sites:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch study sites',
        'error'
      )
      return []
    } finally {
      loading.value = false
    }
  }

  /**
   * Fetch all study sites across all items (for map display)
   */
  const fetchAllStudySites = async (): Promise<void> => {
    loading.value = true
    try {
      // Fetch items with their study sites
      const itemsResponse = await api.get('/items/', { params: { limit: 1000 } })
      const items = itemsResponse.data.data || []

      // Extract all study sites from items and enrich with item info
      const enrichedSites: StudySiteWithItem[] = []

      items.forEach((item: any) => {
        if (item.study_sites && Array.isArray(item.study_sites)) {
          item.study_sites.forEach((site: any) => {
            // Get coordinates from the item's study_site if available
            // The backend may return lat/lon in different structures
            const latitude = site.latitude
            const longitude = site.longitude

            enrichedSites.push({
              ...site,
              latitude,
              longitude,
              item_title: item.title || 'Unknown',
              item
            })
          })
        }
      })

      studySites.value = enrichedSites
    } catch (error: any) {
      console.error('Error fetching all study sites:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch study sites',
        'error'
      )
    } finally {
      loading.value = false
    }
  }

  /**
   * Get a single study site by ID
   */
  const fetchStudySite = async (studySiteId: string): Promise<StudySite | null> => {
    loading.value = true
    try {
      const response = await api.get(`/study-sites/study-sites/${studySiteId}`)
      currentStudySite.value = response.data
      return response.data
    } catch (error: any) {
      console.error('Error fetching study site:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch study site',
        'error'
      )
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Create a new manual study site
   */
  const createStudySite = async (
    itemId: string,
    data: StudySiteCreate
  ): Promise<StudySite | null> => {
    loading.value = true
    try {
      const response = await api.post(
        `/study-sites/items/${itemId}/study-sites`,
        data
      )

      const newSite = response.data

      // Fetch item info to enrich the new site
      const itemResponse = await api.get(`/items/${itemId}`)
      const enrichedSite = {
        ...newSite,
        item_title: itemResponse.data.title || 'Unknown',
        item: itemResponse.data
      }

      studySites.value.push(enrichedSite)

      notificationStore.showNotification(
        'Study site created successfully',
        'success'
      )
      return newSite
    } catch (error: any) {
      console.error('Error creating study site:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to create study site',
        'error'
      )
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Update an existing study site
   */
  const updateStudySite = async (
    studySiteId: string,
    data: StudySiteUpdate
  ): Promise<StudySite | null> => {
    loading.value = true
    try {
      const response = await api.put(
        `/study-sites/study-sites/${studySiteId}`,
        data
      )

      const updatedSite = response.data

      // Update in local state
      const index = studySites.value.findIndex(s => s.id === studySiteId)
      if (index !== -1) {
        studySites.value[index] = {
          ...studySites.value[index],
          ...updatedSite
        }
      }

      if (currentStudySite.value?.id === studySiteId) {
        currentStudySite.value = updatedSite
      }

      notificationStore.showNotification(
        'Study site updated successfully',
        'success'
      )
      return updatedSite
    } catch (error: any) {
      console.error('Error updating study site:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to update study site',
        'error'
      )
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete a study site
   */
  const deleteStudySite = async (studySiteId: string): Promise<boolean> => {
    loading.value = true
    try {
      await api.delete(`/study-sites/study-sites/${studySiteId}`)

      // Remove from local state
      studySites.value = studySites.value.filter(s => s.id !== studySiteId)

      if (currentStudySite.value?.id === studySiteId) {
        currentStudySite.value = null
      }

      notificationStore.showNotification(
        'Study site deleted successfully',
        'success'
      )
      return true
    } catch (error: any) {
      console.error('Error deleting study site:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to delete study site',
        'error'
      )
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * Get statistics for an item's study sites
   */
  const getItemStats = async (itemId: string): Promise<any> => {
    try {
      const response = await api.get(`/study-sites/items/${itemId}/study-sites/stats`)
      return response.data
    } catch (error: any) {
      console.error('Error fetching study site stats:', error)
      return null
    }
  }

  return {
    // State
    studySites,
    currentStudySite,
    loading,

    // Computed
    manualStudySites,
    automaticStudySites,

    // Actions
    fetchItemStudySites,
    fetchAllStudySites,
    fetchStudySite,
    createStudySite,
    updateStudySite,
    deleteStudySite,
    getItemStats
  }
})
