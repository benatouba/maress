import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useNotificationStore } from './notification'
import type { MapPoint } from './studySites'

export interface GeoJSONGeometry {
  type: string
  coordinates: any
}

export interface Region {
  id: string
  name: string
  description: string
  source_filename: string | null
  properties_json: string | null
  owner_id: string
  created_at: string
  updated_at: string
  geojson: GeoJSONGeometry | null
}

export interface RegionStats {
  region_id: string
  region_name: string
  study_site_count: number
  paper_count: number
  manual_count: number
  automatic_count: number
  extraction_methods: Record<string, number>
  papers: Array<{ id: string; title: string | null }>
}

export const useRegionsStore = defineStore('regions', () => {
  const regions = ref<Region[]>([])
  const selectedRegion = ref<Region | null>(null)
  const regionStats = ref<RegionStats | null>(null)
  const regionStudySites = ref<MapPoint[]>([])
  const loading = ref(false)
  const uploading = ref(false)

  const notificationStore = useNotificationStore()

  const regionCount = computed(() => regions.value.length)

  /**
   * Upload a shapefile (.zip) and create regions
   */
  const uploadShapefile = async (file: File): Promise<Region[]> => {
    uploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await api.post('/regions/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      const created: Region[] = response.data.data || []
      regions.value.push(...created)

      notificationStore.showNotification(
        `Uploaded ${created.length} region(s) from ${file.name}`,
        'success',
      )
      return created
    } catch (error: any) {
      console.error('Error uploading shapefile:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to upload shapefile',
        'error',
      )
      return []
    } finally {
      uploading.value = false
    }
  }

  /**
   * Fetch all regions for the current user
   */
  const fetchRegions = async (): Promise<void> => {
    loading.value = true
    try {
      const response = await api.get('/regions/')
      regions.value = response.data.data || []
    } catch (error: any) {
      console.error('Error fetching regions:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch regions',
        'error',
      )
    } finally {
      loading.value = false
    }
  }

  /**
   * Fetch spatial statistics for a region
   */
  const fetchRegionStats = async (regionId: string): Promise<RegionStats | null> => {
    try {
      const response = await api.get(`/regions/${regionId}/stats`)
      regionStats.value = response.data
      return response.data
    } catch (error: any) {
      console.error('Error fetching region stats:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch region statistics',
        'error',
      )
      return null
    }
  }

  /**
   * Fetch study sites within a region
   */
  const fetchRegionStudySites = async (regionId: string): Promise<MapPoint[]> => {
    try {
      const response = await api.get(`/regions/${regionId}/study-sites`)
      const points: MapPoint[] = response.data.data || []
      regionStudySites.value = points
      return points
    } catch (error: any) {
      console.error('Error fetching region study sites:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch study sites for region',
        'error',
      )
      return []
    }
  }

  /**
   * Delete a region
   */
  const deleteRegion = async (regionId: string): Promise<boolean> => {
    try {
      await api.delete(`/regions/${regionId}`)
      regions.value = regions.value.filter((r) => r.id !== regionId)

      if (selectedRegion.value?.id === regionId) {
        selectedRegion.value = null
        regionStats.value = null
        regionStudySites.value = []
      }

      notificationStore.showNotification('Region deleted', 'success')
      return true
    } catch (error: any) {
      console.error('Error deleting region:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to delete region',
        'error',
      )
      return false
    }
  }

  /**
   * Select a region and fetch its stats
   */
  const selectRegion = async (region: Region | null) => {
    selectedRegion.value = region
    if (region) {
      await Promise.all([
        fetchRegionStats(region.id),
        fetchRegionStudySites(region.id),
      ])
    } else {
      regionStats.value = null
      regionStudySites.value = []
    }
  }

  return {
    regions,
    selectedRegion,
    regionStats,
    regionStudySites,
    loading,
    uploading,
    regionCount,
    uploadShapefile,
    fetchRegions,
    fetchRegionStats,
    fetchRegionStudySites,
    deleteRegion,
    selectRegion,
  }
})
