import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/services/api'
import { useNotificationStore } from './notification'
import type { Ref } from 'vue'

// Tag interfaces for better intellisense
export interface Tag {
  id: number
  name: string
  description?: string
  owner_id: string
  created_at: string
  updated_at: string
  items?: TagItem[]
}

export interface TagCreate {
  name: string
  description?: string
}

export interface TagsPublic {
  data: Tag[]
  count: number
}

export interface TagItem {
  id: string
  title: string
  abstractNote?: string
  publicationTitle?: string
  date?: string
}

// Tag store interface for better intellisense
export interface TagStore {
  tags: Ref<Tag[]>
  currentTag: Ref<Tag | null>
  totalCount: Ref<number>
  loading: Ref<boolean>
  fetchTags: (skip?: number, limit?: number) => Promise<void>
  fetchTag: (tagId: number) => Promise<Tag | null>
  createTag: (tagData: TagCreate) => Promise<Tag | null>
  updateTag: (tagId: number, tagData: TagCreate) => Promise<Tag | null>
  deleteTag: (tagId: number) => Promise<boolean>
  removeTag: (tagId: number) => void
  addItemToTag: (tagId: number, itemId: string) => Promise<boolean>
  removeItemFromTag: (tagId: number, itemId: string) => Promise<boolean>
  getTagsForItem: (itemId: string) => Tag[]
  searchTags: (query: string) => Tag[]
}

export const useTagStore = defineStore('tags', (): TagStore => {
  const tags = ref<Tag[]>([])
  const currentTag = ref<Tag | null>(null)
  const totalCount = ref(0)
  const loading = ref(false)

  // Fetch all tags
  const fetchTags = async (skip = 0, limit = 100) => {
    loading.value = true
    try {
      const params = { skip, limit }
      const response = await axios.get('/tags/', { params })
      tags.value = response.data.data
      totalCount.value = response.data.count
      console.log('Fetched tags:', response.data)
    } catch (error) {
      console.error('Error fetching tags:', error)
    } finally {
      loading.value = false
    }
  }

  // Fetch single tag
  const fetchTag = async (tagId: number) => {
    loading.value = true
    try {
      const response = await axios.get(`/tags/${tagId}`)
      currentTag.value = response.data
      return response.data
    } catch (error) {
      console.error('Error fetching tag:', error)
      return null
    } finally {
      loading.value = false
    }
  }

  // Create new tag
  const createTag = async (tagData: TagCreate) => {
    const notificationStore = useNotificationStore()
    loading.value = true
    try {
      const response = await axios.post('/tags/', tagData)
      const newTag = response.data
      tags.value.push(newTag)
      totalCount.value += 1
      notificationStore.showNotification('Tag created successfully!', 'success')
      return newTag
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to create tag',
        'error',
      )
      return null
    } finally {
      loading.value = false
    }
  }

  // Update existing tag
  const updateTag = async (tagId: number, tagData: TagCreate) => {
    const notificationStore = useNotificationStore()
    loading.value = true
    try {
      const response = await axios.put(`/tags/${tagId}`, tagData)
      const updatedTag = response.data

      // Update the tag in the local array
      const index = tags.value.findIndex((tag) => tag.id === tagId)
      if (index !== -1) {
        tags.value[index] = updatedTag
      }

      // Update current tag if it matches
      if (currentTag.value?.id === tagId) {
        currentTag.value = updatedTag
      }

      notificationStore.showNotification('Tag updated successfully!', 'success')
      return updatedTag
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to update tag',
        'error',
      )
      return null
    } finally {
      loading.value = false
    }
  }

  //remove Tag from local array
  const removeTag = (tagId: number) => {
    tags.value = tags.value.filter((tag) => tag.id !== tagId)
    totalCount.value -= 1
    if (currentTag.value?.id === tagId) {
      currentTag.value = null
    }
  }

  // Delete tag
  const deleteTag = async (tagId: number) => {
    const notificationStore = useNotificationStore()
    loading.value = true
    try {
      await axios.delete(`/tags/${tagId}`)

      // Remove from local array
      tags.value = tags.value.filter((tag) => tag.id !== tagId)
      totalCount.value -= 1

      // Clear current tag if it matches
      if (currentTag.value?.id === tagId) {
        currentTag.value = null
      }

      notificationStore.showNotification('Tag deleted successfully!', 'success')
      return true
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to delete tag',
        'error',
      )
      return false
    } finally {
      loading.value = false
    }
  }

  // Add an item to a tag
  const addItemToTag = async (tagId: number, itemId: string) => {
    const notificationStore = useNotificationStore()
    loading.value = true
    try {
      const response = await axios.post(`/tags/${tagId}/items/${itemId}`)
      const updatedTag = response.data

      // Update in tags array
      const index = tags.value.findIndex((t) => t.id === tagId)
      if (index !== -1) {
        tags.value[index] = updatedTag
      }

      // Update currentTag if it matches
      if (currentTag.value?.id === tagId) {
        currentTag.value = updatedTag
      }

      notificationStore.showNotification('Item added to tag successfully!', 'success')
      return true
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to add item to tag',
        'error',
      )
      return false
    } finally {
      loading.value = false
    }
  }

  // Remove an item from a tag
  const removeItemFromTag = async (tagId: number, itemId: string) => {
    const notificationStore = useNotificationStore()
    loading.value = true
    try {
      await axios.delete(`/tags/${tagId}/items/${itemId}`)

      // Update tag in array by removing the item
      const tagIndex = tags.value.findIndex((t) => t.id === tagId)
      if (tagIndex !== -1 && tags.value[tagIndex].items) {
        tags.value[tagIndex].items = tags.value[tagIndex].items!.filter(
          (item) => item.id !== itemId,
        )
      }

      // Update currentTag if it matches
      if (currentTag.value?.id === tagId && currentTag.value.items) {
        currentTag.value.items = currentTag.value.items.filter((item) => item.id !== itemId)
      }

      notificationStore.showNotification('Item removed from tag successfully!', 'success')
      return true
    } catch (error) {
      notificationStore.showNotification(
        error.response?.data?.detail || 'Failed to remove item from tag',
        'error',
      )
      return false
    } finally {
      loading.value = false
    }
  }

  // Get tags for a specific item
  const getTagsForItem = (itemId: string): Tag[] => {
    return tags.value.filter((tag) => tag.items?.some((item) => item.id === itemId))
  }

  // Search tags by name
  const searchTags = (query: string): Tag[] => {
    const lowerQuery = query.toLowerCase()
    return tags.value.filter((tag) => tag.name.toLowerCase().includes(lowerQuery))
  }

  return {
    tags,
    currentTag,
    totalCount,
    loading,
    fetchTags,
    fetchTag,
    createTag,
    updateTag,
    deleteTag,
    removeTag,
    addItemToTag,
    removeItemFromTag,
    getTagsForItem,
    searchTags,
  }
})
