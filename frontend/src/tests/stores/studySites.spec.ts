import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStudySitesStore } from '@/stores/studySites'
import { useNotificationStore } from '@/stores/notification'
import api from '@/services/api'
import {
  mockStudySite,
  mockStudySiteAuto,
  mockItem,
  mockItemsResponse,
  mockStudySitesResponse,
  mockApiSuccess,
  mockApiError
} from '../mocks/api-mocks'
import { setupTest, teardownTest, flushPromises } from '../utils/test-utils'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

describe('StudySites Store', () => {
  let store: ReturnType<typeof useStudySitesStore>
  let notificationStore: ReturnType<typeof useNotificationStore>

  beforeEach(() => {
    setupTest()
    setActivePinia(createPinia())
    store = useStudySitesStore()
    notificationStore = useNotificationStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    teardownTest()
  })

  describe('Initial State', () => {
    it('should have empty studySites array', () => {
      expect(store.studySites).toEqual([])
    })

    it('should have null currentStudySite', () => {
      expect(store.currentStudySite).toBeNull()
    })

    it('should have loading as false', () => {
      expect(store.loading).toBe(false)
    })
  })

  describe('Computed Properties', () => {
    beforeEach(() => {
      store.studySites = [mockStudySite, mockStudySiteAuto]
    })

    it('should filter manual study sites', () => {
      expect(store.manualStudySites).toHaveLength(1)
      expect(store.manualStudySites[0].is_manual).toBe(true)
    })

    it('should filter automatic study sites', () => {
      expect(store.automaticStudySites).toHaveLength(1)
      expect(store.automaticStudySites[0].is_manual).toBe(false)
    })
  })

  describe('fetchItemStudySites', () => {
    it('should fetch study sites for a specific item', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockResolvedValueOnce({ data: mockStudySitesResponse })

      const result = await store.fetchItemStudySites('item-1')

      expect(mockGet).toHaveBeenCalledWith('/study-sites/items/item-1/study-sites')
      expect(result).toEqual(mockStudySitesResponse.data)
    })

    it('should handle errors when fetching item study sites', async () => {
      const mockGet = vi.mocked(api.get)
      const error = new Error('Network error')
      mockGet.mockRejectedValueOnce(error)

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.fetchItemStudySites('item-1')

      expect(result).toEqual([])
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Failed to fetch study sites',
        'error'
      )
    })

    it('should set loading state correctly', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockImplementation(
        () => new Promise((resolve) => {
          expect(store.loading).toBe(true)
          resolve({ data: mockStudySitesResponse })
        })
      )

      await store.fetchItemStudySites('item-1')
      expect(store.loading).toBe(false)
    })
  })

  describe('fetchAllStudySites', () => {
    it('should fetch all study sites with enriched item info', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockResolvedValueOnce({ data: mockItemsResponse })

      await store.fetchAllStudySites()

      expect(mockGet).toHaveBeenCalledWith('/items/', { params: { limit: 1000 } })
      expect(store.studySites).toHaveLength(1) // Only items with study_sites
      expect(store.studySites[0].item_title).toBe(mockItem.title)
    })

    it('should handle items with multiple study sites', async () => {
      const mockGet = vi.mocked(api.get)
      const itemWithMultipleSites = {
        ...mockItem,
        study_sites: [mockStudySite, mockStudySiteAuto]
      }
      mockGet.mockResolvedValueOnce({
        data: { data: [itemWithMultipleSites], count: 1 }
      })

      await store.fetchAllStudySites()

      expect(store.studySites).toHaveLength(2)
      expect(store.studySites[0].item_title).toBe(mockItem.title)
      expect(store.studySites[1].item_title).toBe(mockItem.title)
    })

    it('should handle errors when fetching all study sites', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockRejectedValueOnce(new Error('API Error'))

      vi.spyOn(notificationStore, 'showNotification')

      await store.fetchAllStudySites()

      expect(store.studySites).toEqual([])
      expect(notificationStore.showNotification).toHaveBeenCalled()
    })
  })

  describe('fetchStudySite', () => {
    it('should fetch a single study site by ID', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockResolvedValueOnce({ data: mockStudySite })

      const result = await store.fetchStudySite('site-1')

      expect(mockGet).toHaveBeenCalledWith('/study-sites/study-sites/site-1')
      expect(result).toEqual(mockStudySite)
      expect(store.currentStudySite).toEqual(mockStudySite)
    })

    it('should return null on error', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockRejectedValueOnce(new Error('Not found'))

      const result = await store.fetchStudySite('site-1')

      expect(result).toBeNull()
      expect(store.currentStudySite).toBeNull()
    })
  })

  describe('createStudySite', () => {
    const newSiteData = {
      name: 'New Site',
      latitude: 40.0,
      longitude: -120.0,
      context: 'Test context'
    }

    it('should create a new study site', async () => {
      const mockPost = vi.mocked(api.post)
      const mockGet = vi.mocked(api.get)

      const createdSite = { ...mockStudySite, ...newSiteData, id: 'new-site' }
      mockPost.mockResolvedValueOnce({ data: createdSite })
      mockGet.mockResolvedValueOnce({ data: mockItem })

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.createStudySite('item-1', newSiteData)

      expect(mockPost).toHaveBeenCalledWith(
        '/study-sites/items/item-1/study-sites',
        newSiteData
      )
      expect(result).toEqual(createdSite)
      expect(store.studySites).toHaveLength(1)
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site created successfully',
        'success'
      )
    })

    it('should enrich created site with item info', async () => {
      const mockPost = vi.mocked(api.post)
      const mockGet = vi.mocked(api.get)

      mockPost.mockResolvedValueOnce({ data: mockStudySite })
      mockGet.mockResolvedValueOnce({ data: mockItem })

      await store.createStudySite('item-1', newSiteData)

      expect(store.studySites[0].item_title).toBe(mockItem.title)
      expect(store.studySites[0].item).toEqual(mockItem)
    })

    it('should handle creation errors', async () => {
      const mockPost = vi.mocked(api.post)
      mockPost.mockRejectedValueOnce(new Error('Creation failed'))

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.createStudySite('item-1', newSiteData)

      expect(result).toBeNull()
      expect(store.studySites).toHaveLength(0)
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Failed to create study site',
        'error'
      )
    })
  })

  describe('updateStudySite', () => {
    const updateData = {
      name: 'Updated Site',
      latitude: 41.0
    }

    beforeEach(() => {
      store.studySites = [mockStudySite]
      store.currentStudySite = mockStudySite
    })

    it('should update an existing study site', async () => {
      const mockPut = vi.mocked(api.put)
      const updatedSite = { ...mockStudySite, ...updateData }
      mockPut.mockResolvedValueOnce({ data: updatedSite })

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.updateStudySite('site-1', updateData)

      expect(mockPut).toHaveBeenCalledWith(
        '/study-sites/study-sites/site-1',
        updateData
      )
      expect(result).toEqual(updatedSite)
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site updated successfully',
        'success'
      )
    })

    it('should update the site in local state', async () => {
      const mockPut = vi.mocked(api.put)
      const updatedSite = { ...mockStudySite, ...updateData }
      mockPut.mockResolvedValueOnce({ data: updatedSite })

      await store.updateStudySite('site-1', updateData)

      expect(store.studySites[0].name).toBe(updateData.name)
      expect(store.studySites[0].latitude).toBe(updateData.latitude)
    })

    it('should update currentStudySite if it matches', async () => {
      const mockPut = vi.mocked(api.put)
      const updatedSite = { ...mockStudySite, ...updateData }
      mockPut.mockResolvedValueOnce({ data: updatedSite })

      await store.updateStudySite('site-1', updateData)

      expect(store.currentStudySite?.name).toBe(updateData.name)
    })

    it('should handle update errors', async () => {
      const mockPut = vi.mocked(api.put)
      mockPut.mockRejectedValueOnce(new Error('Update failed'))

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.updateStudySite('site-1', updateData)

      expect(result).toBeNull()
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Failed to update study site',
        'error'
      )
    })
  })

  describe('deleteStudySite', () => {
    beforeEach(() => {
      store.studySites = [mockStudySite, mockStudySiteAuto]
      store.currentStudySite = mockStudySite
    })

    it('should delete a study site', async () => {
      const mockDelete = vi.mocked(api.delete)
      mockDelete.mockResolvedValueOnce({ data: { message: 'Deleted' } })

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.deleteStudySite('site-1')

      expect(mockDelete).toHaveBeenCalledWith('/study-sites/study-sites/site-1')
      expect(result).toBe(true)
      expect(store.studySites).toHaveLength(1)
      expect(store.studySites[0].id).toBe('site-2')
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site deleted successfully',
        'success'
      )
    })

    it('should clear currentStudySite if it matches deleted site', async () => {
      const mockDelete = vi.mocked(api.delete)
      mockDelete.mockResolvedValueOnce({ data: {} })

      await store.deleteStudySite('site-1')

      expect(store.currentStudySite).toBeNull()
    })

    it('should handle deletion errors', async () => {
      const mockDelete = vi.mocked(api.delete)
      mockDelete.mockRejectedValueOnce(new Error('Delete failed'))

      vi.spyOn(notificationStore, 'showNotification')

      const result = await store.deleteStudySite('site-1')

      expect(result).toBe(false)
      expect(store.studySites).toHaveLength(2) // Unchanged
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Failed to delete study site',
        'error'
      )
    })
  })

  describe('getItemStats', () => {
    it('should fetch statistics for an item', async () => {
      const mockGet = vi.mocked(api.get)
      const mockStats = {
        total: 10,
        manual: 3,
        automatic: 7
      }
      mockGet.mockResolvedValueOnce({ data: mockStats })

      const result = await store.getItemStats('item-1')

      expect(mockGet).toHaveBeenCalledWith('/study-sites/items/item-1/study-sites/stats')
      expect(result).toEqual(mockStats)
    })

    it('should return null on error', async () => {
      const mockGet = vi.mocked(api.get)
      mockGet.mockRejectedValueOnce(new Error('Stats failed'))

      const result = await store.getItemStats('item-1')

      expect(result).toBeNull()
    })
  })
})
