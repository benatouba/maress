import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStudySitesStore } from '@/stores/studySites'
import { useNotificationStore } from '@/stores/notification'
import api from '@/services/api'
import { setupTest, teardownTest, flushPromises } from '../utils/test-utils'
import {
  mockStudySite,
  mockStudySiteAuto,
  mockItem,
  mockItemsResponse
} from '../mocks/api-mocks'

// Mock API
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

describe('Study Sites CRUD Integration Tests', () => {
  let studySitesStore: ReturnType<typeof useStudySitesStore>
  let notificationStore: ReturnType<typeof useNotificationStore>

  beforeEach(() => {
    setupTest()
    setActivePinia(createPinia())
    studySitesStore = useStudySitesStore()
    notificationStore = useNotificationStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    teardownTest()
  })

  describe('Complete CRUD Flow', () => {
    it('should perform full CRUD lifecycle', async () => {
      const mockGet = vi.mocked(api.get)
      const mockPost = vi.mocked(api.post)
      const mockPut = vi.mocked(api.put)
      const mockDelete = vi.mocked(api.delete)

      // 1. READ - Fetch all study sites
      mockGet.mockResolvedValueOnce({
        data: {
          data: [{
            ...mockItem,
            study_sites: [mockStudySite]
          }],
          count: 1
        }
      })

      await studySitesStore.fetchAllStudySites()

      expect(studySitesStore.studySites).toHaveLength(1)
      expect(studySitesStore.studySites[0].id).toBe(mockStudySite.id)

      // 2. CREATE - Add new study site
      const newSiteData = {
        name: 'New Site',
        latitude: 40.0,
        longitude: -120.0,
        context: 'Test context'
      }

      const createdSite = {
        ...mockStudySite,
        ...newSiteData,
        id: 'new-site-id'
      }

      mockPost.mockResolvedValueOnce({ data: createdSite })
      mockGet.mockResolvedValueOnce({ data: mockItem })

      const result = await studySitesStore.createStudySite('item-1', newSiteData)

      expect(result).toBeTruthy()
      expect(studySitesStore.studySites).toHaveLength(2)
      expect(studySitesStore.studySites[1].name).toBe(newSiteData.name)

      // 3. UPDATE - Modify the new study site
      const updateData = {
        name: 'Updated Site Name',
        latitude: 41.0
      }

      const updatedSite = {
        ...createdSite,
        ...updateData
      }

      mockPut.mockResolvedValueOnce({ data: updatedSite })

      const updateResult = await studySitesStore.updateStudySite('new-site-id', updateData)

      expect(updateResult).toBeTruthy()
      const updatedInStore = studySitesStore.studySites.find(s => s.id === 'new-site-id')
      expect(updatedInStore?.name).toBe(updateData.name)
      expect(updatedInStore?.latitude).toBe(updateData.latitude)

      // 4. DELETE - Remove the study site
      mockDelete.mockResolvedValueOnce({ data: { message: 'Deleted' } })

      const deleteResult = await studySitesStore.deleteStudySite('new-site-id')

      expect(deleteResult).toBe(true)
      expect(studySitesStore.studySites).toHaveLength(1)
      expect(studySitesStore.studySites.find(s => s.id === 'new-site-id')).toBeUndefined()
    })
  })

  describe('Error Handling in CRUD Operations', () => {
    it('should handle CREATE error gracefully', async () => {
      const mockPost = vi.mocked(api.post)
      mockPost.mockRejectedValueOnce(new Error('Network error'))

      vi.spyOn(notificationStore, 'showNotification')

      const result = await studySitesStore.createStudySite('item-1', {
        name: 'Test',
        latitude: 45.0,
        longitude: -122.0
      })

      expect(result).toBeNull()
      expect(studySitesStore.studySites).toHaveLength(0)
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        'error'
      )
    })

    it('should handle UPDATE error gracefully', async () => {
      // Setup initial data
      studySitesStore.studySites = [mockStudySite]

      const mockPut = vi.mocked(api.put)
      mockPut.mockRejectedValueOnce(new Error('Update failed'))

      vi.spyOn(notificationStore, 'showNotification')

      const result = await studySitesStore.updateStudySite('site-1', {
        name: 'New Name'
      })

      expect(result).toBeNull()
      // Original data should be unchanged
      expect(studySitesStore.studySites[0].name).toBe(mockStudySite.name)
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        'error'
      )
    })

    it('should handle DELETE error gracefully', async () => {
      // Setup initial data
      studySitesStore.studySites = [mockStudySite, mockStudySiteAuto]

      const mockDelete = vi.mocked(api.delete)
      mockDelete.mockRejectedValueOnce(new Error('Delete failed'))

      vi.spyOn(notificationStore, 'showNotification')

      const result = await studySitesStore.deleteStudySite('site-1')

      expect(result).toBe(false)
      // Original data should be unchanged
      expect(studySitesStore.studySites).toHaveLength(2)
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        'error'
      )
    })
  })

  describe('Concurrent Operations', () => {
    it('should handle multiple CREATE operations', async () => {
      const mockPost = vi.mocked(api.post)
      const mockGet = vi.mocked(api.get)

      mockPost.mockResolvedValue({ data: mockStudySite })
      mockGet.mockResolvedValue({ data: mockItem })

      // Create multiple sites concurrently
      const promises = [
        studySitesStore.createStudySite('item-1', {
          name: 'Site 1',
          latitude: 40.0,
          longitude: -120.0
        }),
        studySitesStore.createStudySite('item-1', {
          name: 'Site 2',
          latitude: 41.0,
          longitude: -121.0
        }),
        studySitesStore.createStudySite('item-1', {
          name: 'Site 3',
          latitude: 42.0,
          longitude: -122.0
        })
      ]

      await Promise.all(promises)

      expect(studySitesStore.studySites).toHaveLength(3)
    })

    it('should handle mixed CRUD operations', async () => {
      const mockGet = vi.mocked(api.get)
      const mockPost = vi.mocked(api.post)
      const mockPut = vi.mocked(api.put)
      const mockDelete = vi.mocked(api.delete)

      // Setup initial data
      studySitesStore.studySites = [mockStudySite]

      mockPost.mockResolvedValue({ data: { ...mockStudySite, id: 'new-id' } })
      mockGet.mockResolvedValue({ data: mockItem })
      mockPut.mockResolvedValue({ data: { ...mockStudySite, name: 'Updated' } })
      mockDelete.mockResolvedValue({ data: {} })

      // Execute mixed operations
      await Promise.all([
        studySitesStore.createStudySite('item-1', {
          name: 'New Site',
          latitude: 40.0,
          longitude: -120.0
        }),
        studySitesStore.updateStudySite(mockStudySite.id, { name: 'Updated' }),
        studySitesStore.fetchItemStudySites('item-1')
      ])

      // All operations should complete without errors
      expect(mockPost).toHaveBeenCalled()
      expect(mockPut).toHaveBeenCalled()
      expect(mockGet).toHaveBeenCalled()
    })
  })

  describe('Data Consistency', () => {
    it('should maintain consistent state after failed CREATE', async () => {
      const initialLength = studySitesStore.studySites.length

      const mockPost = vi.mocked(api.post)
      mockPost.mockRejectedValueOnce(new Error('Create failed'))

      await studySitesStore.createStudySite('item-1', {
        name: 'Test',
        latitude: 40.0,
        longitude: -120.0
      })

      expect(studySitesStore.studySites).toHaveLength(initialLength)
    })

    it('should maintain consistent state after failed UPDATE', async () => {
      studySitesStore.studySites = [mockStudySite]
      const originalName = mockStudySite.name

      const mockPut = vi.mocked(api.put)
      mockPut.mockRejectedValueOnce(new Error('Update failed'))

      await studySitesStore.updateStudySite(mockStudySite.id, {
        name: 'Should Not Update'
      })

      expect(studySitesStore.studySites[0].name).toBe(originalName)
    })

    it('should maintain consistent state after failed DELETE', async () => {
      studySitesStore.studySites = [mockStudySite, mockStudySiteAuto]

      const mockDelete = vi.mocked(api.delete)
      mockDelete.mockRejectedValueOnce(new Error('Delete failed'))

      await studySitesStore.deleteStudySite(mockStudySite.id)

      expect(studySitesStore.studySites).toHaveLength(2)
      expect(studySitesStore.studySites.find(s => s.id === mockStudySite.id)).toBeTruthy()
    })
  })

  describe('Loading States', () => {
    it('should set loading state during CREATE', async () => {
      const mockPost = vi.mocked(api.post)
      const mockGet = vi.mocked(api.get)

      let loadingDuringOperation = false

      mockPost.mockImplementation(async () => {
        loadingDuringOperation = studySitesStore.loading
        return { data: mockStudySite }
      })
      mockGet.mockResolvedValue({ data: mockItem })

      await studySitesStore.createStudySite('item-1', {
        name: 'Test',
        latitude: 40.0,
        longitude: -120.0
      })

      expect(loadingDuringOperation).toBe(true)
      expect(studySitesStore.loading).toBe(false)
    })

    it('should set loading state during UPDATE', async () => {
      studySitesStore.studySites = [mockStudySite]

      const mockPut = vi.mocked(api.put)

      let loadingDuringOperation = false

      mockPut.mockImplementation(async () => {
        loadingDuringOperation = studySitesStore.loading
        return { data: mockStudySite }
      })

      await studySitesStore.updateStudySite(mockStudySite.id, { name: 'Test' })

      expect(loadingDuringOperation).toBe(true)
      expect(studySitesStore.loading).toBe(false)
    })

    it('should reset loading state after error', async () => {
      const mockPost = vi.mocked(api.post)
      mockPost.mockRejectedValueOnce(new Error('Error'))

      await studySitesStore.createStudySite('item-1', {
        name: 'Test',
        latitude: 40.0,
        longitude: -120.0
      })

      expect(studySitesStore.loading).toBe(false)
    })
  })

  describe('Notifications', () => {
    beforeEach(() => {
      vi.spyOn(notificationStore, 'showNotification')
    })

    it('should show success notification on CREATE', async () => {
      const mockPost = vi.mocked(api.post)
      const mockGet = vi.mocked(api.get)

      mockPost.mockResolvedValueOnce({ data: mockStudySite })
      mockGet.mockResolvedValueOnce({ data: mockItem })

      await studySitesStore.createStudySite('item-1', {
        name: 'Test',
        latitude: 40.0,
        longitude: -120.0
      })

      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site created successfully',
        'success'
      )
    })

    it('should show success notification on UPDATE', async () => {
      studySitesStore.studySites = [mockStudySite]

      const mockPut = vi.mocked(api.put)
      mockPut.mockResolvedValueOnce({ data: mockStudySite })

      await studySitesStore.updateStudySite(mockStudySite.id, { name: 'Updated' })

      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site updated successfully',
        'success'
      )
    })

    it('should show success notification on DELETE', async () => {
      studySitesStore.studySites = [mockStudySite]

      const mockDelete = vi.mocked(api.delete)
      mockDelete.mockResolvedValueOnce({ data: {} })

      await studySitesStore.deleteStudySite(mockStudySite.id)

      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site deleted successfully',
        'success'
      )
    })

    it('should show error notification on failed operations', async () => {
      const mockPost = vi.mocked(api.post)
      mockPost.mockRejectedValueOnce(new Error('Failed'))

      await studySitesStore.createStudySite('item-1', {
        name: 'Test',
        latitude: 40.0,
        longitude: -120.0
      })

      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        'error'
      )
    })
  })
})
