import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'
import { useNotificationStore } from './notification'
import logger from '@/utils/logger'
import type { MapPoint } from './studySites'

export interface GISSelection {
  type: 'all' | 'ids' | 'bbox'
  ids?: string[]
  bbox?: [number, number, number, number]
}

export interface GISFeatureSetRef {
  layer_id: 'study-sites' | 'regions'
  selection: GISSelection
}

export interface GISCapability {
  id: string
  label: string
  description: string
  permission: string
  execution: 'sync' | 'async'
  requires_authentication: boolean
  enabled: boolean
  geometry_inputs: string[]
  parameter_schema: Record<string, any>
}

export interface GISCapabilitiesResponse {
  version: string
  operations: GISCapability[]
  limits: Record<string, any>
}

export interface GISBufferedFeature {
  source_id: string | null
  geometry: Record<string, any>
}

export interface GISBufferResult {
  target_layer_id: string
  distance_meters: number
  dissolved: boolean
  count: number
  features: GISBufferedFeature[]
}

export interface GISClipResult {
  target_layer_id: string
  clip_layer_id: string
  count: number
  study_sites: MapPoint[] | null
}

export interface GISRegionFeature {
  id: string
  name: string
}

export interface GISWithinDistanceResult {
  source_layer_id: string
  against_layer_id: string
  return_layer_id: string
  distance_meters: number
  count: number
  study_sites: MapPoint[] | null
  regions: GISRegionFeature[] | null
}

export interface GISWithinDistanceParameters {
  distance: number
  unit: 'meter' | 'kilometer'
  return: 'source' | 'against'
}

export interface GISMetric {
  type: 'count' | 'avg'
  field: string
  alias?: string
}

export interface GISSpatialFilter {
  layer_id: 'regions'
  selection: GISSelection
  predicate?: 'within'
}

export interface GISSummaryStatsRequest {
  target: GISFeatureSetRef
  group_by: string[]
  metrics: GISMetric[]
  spatial_filter?: GISSpatialFilter
}

export interface GISSummaryStatsResult {
  rows: Record<string, any>[]
  count: number
}

export const useGisStore = defineStore('gis', () => {
  const capabilities = ref<GISCapability[]>([])
  const capabilitiesVersion = ref<string | null>(null)
  const limits = ref<Record<string, any>>({})

  const loadingCapabilities = ref(false)
  const runningOperation = ref(false)

  const bufferFeatures = ref<GISBufferedFeature[]>([])
  const clippedStudySites = ref<MapPoint[]>([])
  const withinDistanceStudySites = ref<MapPoint[]>([])
  const withinDistanceRegions = ref<GISRegionFeature[]>([])
  const summaryStatsRows = ref<Record<string, any>[]>([])
  const summaryStatsCount = ref(0)

  const notificationStore = useNotificationStore()

  const fetchCapabilities = async (): Promise<void> => {
    loadingCapabilities.value = true
    try {
      const response = await api.get<GISCapabilitiesResponse>('/gis/capabilities')
      capabilities.value = response.data.operations || []
      capabilitiesVersion.value = response.data.version || null
      limits.value = response.data.limits || {}
    } catch (error: any) {
      logger.error('Error fetching GIS capabilities:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch GIS capabilities',
        'error',
      )
    } finally {
      loadingCapabilities.value = false
    }
  }

  const runBuffer = async (
    target: GISFeatureSetRef,
    parameters: { distance: number; unit: 'meter' | 'kilometer'; dissolve: boolean },
  ): Promise<GISBufferResult | null> => {
    runningOperation.value = true
    try {
      const response = await api.post<GISBufferResult>('/gis/operations/buffer', {
        target,
        parameters,
      })
      bufferFeatures.value = response.data.features || []

      notificationStore.showNotification(
        `Buffer complete: ${response.data.count} feature(s) generated`,
        'success',
      )

      return response.data
    } catch (error: any) {
      logger.error('Error running buffer operation:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Buffer operation failed',
        'error',
      )
      return null
    } finally {
      runningOperation.value = false
    }
  }

  const runClip = async (
    target: GISFeatureSetRef,
    clipWith: GISFeatureSetRef,
  ): Promise<GISClipResult | null> => {
    runningOperation.value = true
    try {
      const response = await api.post<GISClipResult>('/gis/operations/clip', {
        target,
        clip_with: clipWith,
      })

      clippedStudySites.value = response.data.study_sites || []

      notificationStore.showNotification(
        `Clip complete: ${response.data.count} study site(s)`,
        'success',
      )

      return response.data
    } catch (error: any) {
      logger.error('Error running clip operation:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Clip operation failed',
        'error',
      )
      return null
    } finally {
      runningOperation.value = false
    }
  }

  const runWithinDistance = async (
    source: GISFeatureSetRef,
    against: GISFeatureSetRef,
    parameters: GISWithinDistanceParameters,
  ): Promise<GISWithinDistanceResult | null> => {
    runningOperation.value = true
    try {
      const response = await api.post<GISWithinDistanceResult>('/gis/operations/within-distance', {
        source,
        against,
        parameters,
      })

      withinDistanceStudySites.value = response.data.study_sites || []
      withinDistanceRegions.value = response.data.regions || []

      notificationStore.showNotification(
        `Within-distance complete: ${response.data.count} result(s)`,
        'success',
      )

      return response.data
    } catch (error: any) {
      logger.error('Error running within-distance operation:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Within-distance operation failed',
        'error',
      )
      return null
    } finally {
      runningOperation.value = false
    }
  }

  const runSummaryStats = async (
    payload: GISSummaryStatsRequest,
  ): Promise<GISSummaryStatsResult | null> => {
    runningOperation.value = true
    try {
      const response = await api.post<GISSummaryStatsResult>('/gis/operations/summary-stats', payload)

      summaryStatsRows.value = response.data.rows || []
      summaryStatsCount.value = response.data.count || 0

      notificationStore.showNotification(
        `Summary stats complete: ${summaryStatsCount.value} row(s)`,
        'success',
      )

      return response.data
    } catch (error: any) {
      logger.error('Error running summary-stats operation:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Summary-stats operation failed',
        'error',
      )
      return null
    } finally {
      runningOperation.value = false
    }
  }

  const clearResults = () => {
    bufferFeatures.value = []
    clippedStudySites.value = []
    withinDistanceStudySites.value = []
    withinDistanceRegions.value = []
    summaryStatsRows.value = []
    summaryStatsCount.value = 0
  }

  return {
    capabilities,
    capabilitiesVersion,
    limits,
    loadingCapabilities,
    runningOperation,
    bufferFeatures,
    clippedStudySites,
    withinDistanceStudySites,
    withinDistanceRegions,
    summaryStatsRows,
    summaryStatsCount,
    fetchCapabilities,
    runBuffer,
    runClip,
    runWithinDistance,
    runSummaryStats,
    clearResults,
  }
})
