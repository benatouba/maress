import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'
import { useNotificationStore } from './notification'
import logger from '@/utils/logger'
import type { MapPoint } from './studySites'

export interface GISSelection {
  type: 'all' | 'ids' | 'bbox' | 'geometry'
  ids?: string[]
  bbox?: [number, number, number, number]
  geometry?: Record<string, any>
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
  type: 'count' | 'avg' | 'min' | 'max' | 'sum'
  field: string
  alias?: string
}

export interface GISSpatialFilter {
  layer_id: 'regions'
  selection: GISSelection
  predicate?: 'within' | 'intersects'
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

export interface GISAsyncTaskRef {
  task_id: string
  operation_id: string
  status: string
  message?: string | null
}

export interface GISAsyncTaskAccepted {
  data: GISAsyncTaskRef
}

export interface GISAsyncTaskStatus {
  task_id: string
  state: string
  status: string
  ready: boolean
  successful: boolean | null
  failed: boolean | null
  result?: Record<string, any>
  error?: Record<string, any>
  metadata?: Record<string, any>
}

export interface GISPreset {
  id: string
  owner_id: string
  name: string
  operation_id: string
  config: Record<string, any>
  created_at: string
  updated_at: string
}

export interface GISPresetsResponse {
  data: GISPreset[]
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
  const asyncTaskStatus = ref<GISAsyncTaskStatus | null>(null)
  const presets = ref<GISPreset[]>([])

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

  const applyOperationResult = (operationId: string, result: Record<string, any>) => {
    if (operationId === 'buffer') {
      bufferFeatures.value = result.features || []
      return
    }
    if (operationId === 'clip') {
      clippedStudySites.value = result.study_sites || []
      return
    }
    if (operationId === 'within-distance') {
      withinDistanceStudySites.value = result.study_sites || []
      withinDistanceRegions.value = result.regions || []
      return
    }
    if (operationId === 'summary-stats') {
      summaryStatsRows.value = result.rows || []
      summaryStatsCount.value = result.count || 0
    }
  }

  const runOperationAsync = async (
    operationId: 'buffer' | 'clip' | 'within-distance' | 'summary-stats',
    payload: Record<string, any>,
  ): Promise<Record<string, any> | null> => {
    runningOperation.value = true
    asyncTaskStatus.value = null
    try {
      const enqueueResponse = await api.post<GISAsyncTaskAccepted>('/gis/operations/async', {
        operation_id: operationId,
        payload,
      })

      const taskId = enqueueResponse.data.data.task_id
      const startedAt = Date.now()
      const timeoutMs = 120000

      while (Date.now() - startedAt < timeoutMs) {
        const statusResponse = await api.get<GISAsyncTaskStatus>(`/gis/tasks/${taskId}`)
        asyncTaskStatus.value = statusResponse.data

        if (statusResponse.data.ready) {
          if (statusResponse.data.successful && statusResponse.data.result) {
            const wrapped = statusResponse.data.result
            const operationResult = wrapped.result || wrapped
            applyOperationResult(operationId, operationResult)
            notificationStore.showNotification(`GIS task complete: ${operationId}`, 'success')
            return operationResult
          }

          notificationStore.showNotification(
            statusResponse.data.error?.message || `GIS task failed: ${operationId}`,
            'error',
          )
          return null
        }

        await new Promise((resolve) => setTimeout(resolve, 1500))
      }

      notificationStore.showNotification('GIS task timed out', 'error')
      return null
    } catch (error: any) {
      logger.error('Error running async GIS operation:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Async GIS operation failed',
        'error',
      )
      return null
    } finally {
      runningOperation.value = false
    }
  }

  const fetchPresets = async (): Promise<void> => {
    try {
      const response = await api.get<GISPresetsResponse>('/gis/presets')
      presets.value = response.data.data || []
    } catch (error: any) {
      logger.error('Error fetching GIS presets:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch GIS presets',
        'error',
      )
    }
  }

  const createPreset = async (
    name: string,
    operationId: string,
    config: Record<string, any>,
  ): Promise<GISPreset | null> => {
    try {
      const response = await api.post<GISPreset>('/gis/presets', {
        name,
        operation_id: operationId,
        config,
      })
      presets.value = [response.data, ...presets.value]
      notificationStore.showNotification('Preset saved', 'success')
      return response.data
    } catch (error: any) {
      logger.error('Error creating GIS preset:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to save preset',
        'error',
      )
      return null
    }
  }

  const deletePreset = async (presetId: string): Promise<boolean> => {
    try {
      await api.delete(`/gis/presets/${presetId}`)
      presets.value = presets.value.filter((preset) => preset.id !== presetId)
      notificationStore.showNotification('Preset deleted', 'success')
      return true
    } catch (error: any) {
      logger.error('Error deleting GIS preset:', error)
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to delete preset',
        'error',
      )
      return false
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
    asyncTaskStatus,
    presets,
    fetchCapabilities,
    runBuffer,
    runClip,
    runWithinDistance,
    runSummaryStats,
    runOperationAsync,
    fetchPresets,
    createPreset,
    deletePreset,
    clearResults,
  }
})
