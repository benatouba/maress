import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/services/api'
import { useNotificationStore } from './notification'
import type { Ref } from 'vue'

// Zotero collection interface
export interface ZoteroCollection {
  key: string
  name: string
  version?: number
  data?: any
}

// Auth store interface for better intellisense
export interface ZoteroStore {
  collections: Ref<any[]>
  zoteroCollections: Ref<ZoteroCollection[]>
  selectedCollectionId: Ref<string | null>
  items: Ref<any[]>
  itemsCount: Ref<number>
  loading: Ref<boolean>
  syncing: Ref<boolean>
  downloading: Ref<boolean>
  downloadProgress: Ref<{ current: number; total: number; downloaded: number; skipped: number; failed: number } | null>
  fetchCollections: () => Promise<void>
  fetchZoteroCollections: (libraryType?: 'user' | 'group') => Promise<void>
  fetchItems: (limit?: number, silent?: boolean) => Promise<void>
  syncLibrary: (reload?: boolean, collectionId?: string | null) => Promise<boolean>
  downloadAttachments: () => Promise<any | null>
  importItem: (itemId: string) => Promise<any | null>
  updateStudySite: (studySiteId: string, updateData: object) => Promise<any>
  importFileFromZotero: (itemId: string) => Promise<any | null>
  getExtractionResults: (itemId: string) => Promise<any | null>
  extractStudySites: (itemId?: string | null, force?: boolean) => Promise<any | null>
}
export const useZoteroStore = defineStore('zotero', (): ZoteroStore => {
  const collections = ref([])
  const zoteroCollections = ref<ZoteroCollection[]>([])
  const selectedCollectionId = ref<string | null>(null)
  const items = ref([])
  const itemsCount = ref(0)
  const loading = ref(false)
  const syncing = ref(false)
  const downloading = ref(false)
  const downloadProgress = ref<{ current: number; total: number; downloaded: number; skipped: number; failed: number } | null>(null)

  // Add polling interval reference
  let pollingInterval: ReturnType<typeof setInterval> | null = null

  // Fetch collections (legacy - database collections)
  const fetchCollections = async () => {
    loading.value = true
    try {
      const response = await axios.get('/zotero')
      collections.value = response.data.collections
    } catch (error) {
      const notificationStore = useNotificationStore()
      notificationStore.showNotification(
        'Failed to fetch collections, with error:' + (error.response?.data?.detail || error.message),
        'error'
      )
    } finally {
      loading.value = false
    }
  }

  // Fetch Zotero collections from API
  const fetchZoteroCollections = async (libraryType: 'user' | 'group' = 'group') => {
    loading.value = true
    try {
      const response = await axios.get(`/items/zotero_collections/${libraryType}`)
      // Transform response to array of collections
      const collectionsData = Array.isArray(response.data) ? response.data : []
      zoteroCollections.value = collectionsData.map((col: any) => ({
        key: col.key || col.data?.key,
        name: col.data?.name || col.name || 'Unnamed Collection',
        version: col.version,
        data: col.data
      }))
    } catch (error) {
      const notificationStore = useNotificationStore()
      notificationStore.showNotification(
        'Failed to fetch Zotero collections, with error:' + (error.response?.data?.detail || error.message),
        'error'
      )
    } finally {
      loading.value = false
    }
  }

  // Fetch items
  const fetchItems = async (limit = 500, silent = false) => {
    // Don't set loading if it's a silent refresh (polling during download)
    if (!silent && !downloading.value) {
      loading.value = true
    }
    try {
      const params = { limit }

      const response = await axios.get('/items/', { params })
      items.value = response.data
      itemsCount.value = response.data.length
      return items.value
    } catch (error) {
      const notificationStore = useNotificationStore()
      notificationStore.showNotification(
        'Failed to fetch items, with error:' + (error.response?.data?.detail || error.message),
        'error'
      )
    } finally {
      if (!silent && !downloading.value) {
        loading.value = false
      }
    }
  }

  // Sync library or collection
  const syncLibrary = async (reload = false, collectionId: string | null = null) => {
    const notificationStore = useNotificationStore()
    syncing.value = true

    try {
      const params: any = { reload }
      if (collectionId) {
        params.collection_id = collectionId
        params.library_type = 'group'
      }

      await axios.get('/items/import_from_zotero/', { params })

      const message = collectionId
        ? `Zotero collection sync started${reload ? ' (force reload)' : ''}`
        : `Zotero library sync started${reload ? ' (force reload)' : ''}`

      notificationStore.showNotification(message, 'info')
      return true
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to start sync',
        'error',
      )
      return false
    } finally {
      syncing.value = false
    }
  }
  const downloadAttachments = async () => {
    const notificationStore = useNotificationStore()
    downloading.value = true
    loading.value = true
    downloadProgress.value = null // Reset progress

    // Start polling to refresh items every 2 seconds during download
    pollingInterval = setInterval(async () => {
      try {
        await fetchItems(500, true) // silent = true to avoid interfering with loading state
      } catch (error) {
        const notificationStore = useNotificationStore()
        notificationStore.showNotification(
          'Error refreshing items during download: ' + (error.response?.data?.detail || error.message),
          'error'
        )
      }
    }, 2000)

    try {
      notificationStore.showNotification('Starting background download...', 'info')

      // Start background task - POST now returns task IDs
      const response = await axios.post('/items/import_file_zotero/', null, {
        params: { skip: 0, limit: 10000 }
      })

      // Get task ID from response
      const tasks = response.data.data
      if (!tasks || tasks.length === 0) {
        throw new Error('No task ID returned from server')
      }

      const taskId = tasks[0].task_id
      notificationStore.showNotification('Download running in background...', 'info')

      // Poll task status
      const taskResult = await pollTaskStatus(taskId)

      // Stop polling items
      if (pollingInterval) {
        clearInterval(pollingInterval)
        pollingInterval = null
      }

      // Final refresh to ensure we have the latest data
      await fetchItems()

      // Show completion message with statistics
      if (taskResult && taskResult.downloaded !== undefined) {
        const msg = `Downloaded: ${taskResult.downloaded}, Skipped: ${taskResult.skipped}, Failed: ${taskResult.failed}`
        notificationStore.showNotification(msg, 'success')
      } else {
        notificationStore.showNotification('Attachments downloaded successfully!', 'success')
      }

      return taskResult
    } catch (error) {
      // Stop polling on error
      if (pollingInterval) {
        clearInterval(pollingInterval)
        pollingInterval = null
      }

      notificationStore.showNotification(
        error.response?.data?.detail || error.message || 'Failed to download attachments',
        'error',
      )
      return null
    } finally {
      downloading.value = false
      loading.value = false
    }
  }

  // Poll task status until completion
  const pollTaskStatus = async (taskId: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const taskPollingInterval = setInterval(async () => {
        try {
          const response = await axios.get(`/items/tasks/${taskId}`)
          const taskData = response.data

          // Check task state
          if (taskData.state === 'SUCCESS') {
            clearInterval(taskPollingInterval)
            downloadProgress.value = null // Clear progress on completion
            resolve(taskData.result)
          } else if (taskData.state === 'FAILURE') {
            clearInterval(taskPollingInterval)
            downloadProgress.value = null // Clear progress on failure
            reject(new Error(taskData.result || 'Task failed'))
          } else if (taskData.state === 'PROGRESS') {
            // Update progress information
            const meta = taskData.result
            downloadProgress.value = {
              current: meta?.current || 0,
              total: meta?.total || 0,
              downloaded: meta?.downloaded || 0,
              skipped: meta?.skipped || 0,
              failed: meta?.failed || 0,
            }
            console.log(`Download progress: ${meta?.current || 0}/${meta?.total || 0}`)
          }
          // PENDING state - keep polling
        } catch (error) {
          clearInterval(taskPollingInterval)
          downloadProgress.value = null // Clear progress on error
          reject(error)
        }
      }, 10 * 1000) // Poll every 10 seconds

      // Add timeout after 24 hours
      setTimeout(() => {
        clearInterval(taskPollingInterval)
        downloadProgress.value = null // Clear progress on timeout
        reject(new Error('Task polling timeout'))
      }, 24 * 60 * 60 * 1000) // 24 hours
    })
  }

  const getLocations = async () => {
    try {
      const response = await axios.post('/items/study_sites/')
      return response.data
    } catch (error) {
      const notificationStore = useNotificationStore()
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to extract study sites',
        'error',
      )
      return []
    }
  }

  // Import single item
  const importItem = async (itemId) => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.post(`/zotero/import/${itemId}`)
      notificationStore.showNotification('Item imported successfully!', 'success')
      return response.data
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to import item',
        'error',
      )
      return null
    } finally {
      loading.value = false
    }
  }

  // Add this method to your Zotero store
  const updateStudySite = async (studySiteId, updateData) => {
    const notificationStore = useNotificationStore()
    try {
      const response = await axios.patch(`/study_sites/${studySiteId}`, updateData)
      return response.data
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to update study site',
        'error',
      )
      throw error
    }
  }

  // Import file from Zotero for a single item
  const importFileFromZotero = async (itemId) => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.get(`/items/import_file_zotero/${itemId}`)
      notificationStore.showNotification('File imported successfully', 'success')
      return response.data
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to import file',
        'error',
      )
      return null
    } finally {
      loading.value = false
    }
  }

  // Get extraction results (all candidates) for an item
  const getExtractionResults = async (itemId: string) => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.get(`/items/${itemId}/extraction-results`)
      return response.data
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to fetch extraction results',
        'error',
      )
      return null
    } finally {
      loading.value = false
    }
  }

  // Extract study sites for items
  // oxlint-disable-next-line no-explicit-any
  const extractStudySites = async (itemIds: string | string[] | null = null, force: boolean = false): Promise<{ count: number; tasks: any[] } | null> => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      // Build request body
      const requestBody: { item_ids?: string[] | null; force: boolean } = { force }

      if (itemIds) {
        // Ensure itemIds is always an array
        requestBody.item_ids = Array.isArray(itemIds) ? itemIds : [itemIds]
      } else {
        // Explicitly set to null when no items are specified
        requestBody.item_ids = null
      }

      const response = await axios.post('/items/study_sites/', requestBody)
      const count = response.data.count || 0
      const taskData = response.data.data || []

      const message = itemIds
        ? `Study site extraction queued for ${Array.isArray(itemIds) ? itemIds.length : 1} item(s)`
        : `Study site extraction queued for ${count} item(s)`

      notificationStore.showNotification(message, 'info')

      // Return both count and task data
      return {
        count,
        tasks: taskData
      }
    } catch (error) {
      const errorDetail = error.response?.data?.detail

      // Format validation errors if present
      let errorMessage = 'Failed to start extraction'
      if (Array.isArray(errorDetail)) {
        errorMessage = errorDetail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ')
      } else if (typeof errorDetail === 'string') {
        errorMessage = errorDetail
      }

      notificationStore.showNotification(errorMessage, 'error')
      return null
    } finally {
      loading.value = false
    }
  }

  // Add it to the return statement
  return {
    collections,
    zoteroCollections,
    selectedCollectionId,
    items,
    itemsCount,
    loading,
    syncing,
    downloading,
    downloadProgress,
    fetchCollections,
    fetchZoteroCollections,
    fetchItems,
    downloadAttachments,
    getLocations,
    syncLibrary,
    importItem,
    updateStudySite,
    importFileFromZotero,
    getExtractionResults,
    extractStudySites,
  }
})
