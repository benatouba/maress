import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/services/api'
import { useNotificationStore } from './notification'
import type { Ref } from 'vue'

// Auth store interface for better intellisense
export interface ZoteroStore {
  collections: Ref<any[]>
  items: Ref<any[]>
  loading: Ref<boolean>
  syncing: Ref<boolean>
  fetchCollections: () => Promise<void>
  fetchItems: (collectionId?: string | null, limit?: number) => Promise<void>
  syncLibrary: () => Promise<boolean>
  downloadAttachments: () => Promise<any | null>
  importItem: (itemId: string) => Promise<any | null>
}
export const useZoteroStore = defineStore('zotero', (): ZoteroStore => {
  const collections = ref([])
  const items = ref([])
  const loading = ref(false)
  const syncing = ref(false)
  const downloading = ref(false)

  // Fetch collections
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

  // Fetch items
  const fetchItems = async (collectionId = null, limit = 500) => {
    loading.value = true
    try {
      const params = { limit }
      if (collectionId) {
        params.collection_id = collectionId
      }

      const response = await axios.get('/items', { params })
      console.log('Fetched items:', response.data)
      items.value = response.data
      console.log('Updated items:', items.value)
      return items.value
    } catch (error) {
      console.error('Error fetching items:', error)
    } finally {
      loading.value = false
    }
  }

  // Sync library
  const syncLibrary = async () => {
    const notificationStore = useNotificationStore()
    syncing.value = true

    try {
      await axios.get('/items/import_from_zotero/')
      notificationStore.showNotification('Zotero sync started!', 'info')
      return true
    } catch (error) {
      notificationStore.showNotification(error.response?.data?.detail || 'Failed to start sync', 'error')
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
      notificationStore.showNotification(error.response?.data?.detail || 'Failed to download attachments', 'error')
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
  const importItem = async itemId => {
    const notificationStore = useNotificationStore()
    loading.value = true

    try {
      const response = await axios.post(`/zotero/import/${itemId}`)
      notificationStore.showNotification('Item imported successfully!', 'success')
      return response.data
    } catch (error) {
      notificationStore.showNotification(error.response?.data?.detail || 'Failed to import item', 'error')
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    collections,
    items,
    loading,
    syncing,
    fetchCollections,
    fetchItems,
    downloadAttachments,
    getLocations,
    syncLibrary,
    importItem,
  }
})
