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
  fetchCollections: () => Promise<void>
  fetchZoteroCollections: (libraryType?: 'user' | 'group') => Promise<void>
  fetchItems: (limit?: number) => Promise<void>
  syncLibrary: (reload?: boolean, collectionId?: string | null) => Promise<boolean>
  downloadAttachments: () => Promise<any | null>
  importItem: (itemId: string) => Promise<any | null>
  updateStudySite: (studySiteId: string, updateData: object) => Promise<any>
  importFileFromZotero: (itemId: string) => Promise<any | null>
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

  // Fetch collections (legacy - database collections)
  const fetchCollections = async () => {
    loading.value = true
    try {
      const response = await axios.get('/zotero')
      collections.value = response.data.collections
    } catch (error) {
      console.error('Error fetching collections:', error)
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
      console.log('Fetched Zotero collections:', zoteroCollections.value)
    } catch (error) {
      console.error('Error fetching Zotero collections:', error)
      const notificationStore = useNotificationStore()
      notificationStore.showNotification(
        'Failed to fetch Zotero collections',
        'error'
      )
    } finally {
      loading.value = false
    }
  }

  // Fetch items
  const fetchItems = async (limit = 500) => {
    loading.value = true
    try {
      const params = { limit }

      const response = await axios.get('/items', { params })
      console.log('Fetched items:', response.data)
      items.value = response.data
      itemsCount.value = response.data.length
      console.log('Updated items:', items.value)
      return items.value
    } catch (error) {
      console.error('Error fetching items:', error)
    } finally {
      loading.value = false
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

    try {
      const response = await axios.get('/items/import_file_zotero/')
      notificationStore.showNotification('Attachment download started!', 'info')
      return response.data
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to download attachments',
        'error',
      )
      return null
    } finally {
      downloading.value = false
    }
  }

  const getLocations = async () => {
    try {
      const response = await axios.post('/items/study_sites/')
      return response.data
    } catch (error) {
      console.error('Error fetching locations:', error)
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
      console.error('Error updating study site:', error)
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

  // Extract study sites for items
  // oxlint-disable-next-line no-explicit-any
  const extractStudySites = async (itemIds: string | string[] | null = null, force: boolean = false): Promise<{ count: number; tasks: any[] } | null> => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      // Build request body
      const requestBody: { item_ids?: string[]; force: boolean } = { force }

      if (itemIds) {
        // Ensure itemIds is always an array
        requestBody.item_ids = Array.isArray(itemIds) ? itemIds : [itemIds]
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
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to start extraction',
        'error',
      )
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
    fetchCollections,
    fetchZoteroCollections,
    fetchItems,
    downloadAttachments,
    getLocations,
    syncLibrary,
    importItem,
    updateStudySite,
    importFileFromZotero,
    extractStudySites,
  }
})
