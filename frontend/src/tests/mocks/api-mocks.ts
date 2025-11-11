import { vi } from 'vitest'

/**
 * Mock location data
 */
export const mockLocation = {
  id: 'loc-1',
  latitude: 45.5,
  longitude: -122.3,
  cluster_label: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

export const mockLocation2 = {
  id: 'loc-2',
  latitude: 40.7,
  longitude: -74.0,
  cluster_label: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

/**
 * Mock study site data
 */
export const mockStudySite = {
  id: 'site-1',
  item_id: 'item-1',
  name: 'Test Site 1',
  location: mockLocation,
  location_id: 'loc-1',
  confidence_score: 0.85,
  validation_score: 0.9,
  context: 'Study site in Portland',
  extraction_method: 'manual',
  source_type: 'text',
  section: 'methods',
  is_manual: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

export const mockStudySiteAuto = {
  ...mockStudySite,
  id: 'site-2',
  name: 'Auto Site',
  location: mockLocation2,
  location_id: 'loc-2',
  is_manual: false,
  extraction_method: 'regex',
  confidence_score: 0.75
}

/**
 * Mock item data
 */
export const mockItem = {
  id: 'item-1',
  title: 'Test Paper 1',
  abstractNote: 'This is a test abstract about climate research in Portland.',
  publicationTitle: 'Journal of Test Studies',
  date: '2024-01-15',
  doi: '10.1234/test.2024',
  url: 'https://example.com/paper1',
  itemType: 'journalArticle',
  owner_id: 'user-1',
  attachment: 'files/test.pdf',
  study_sites: [mockStudySite],
  dateAdded: '2024-01-01T00:00:00Z',
  dateModified: '2024-01-01T00:00:00Z',
  version: 1,
  key: 'ABC12345'
}

export const mockItemWithoutSites = {
  ...mockItem,
  id: 'item-2',
  title: 'Test Paper 2',
  study_sites: []
}

/**
 * Mock items response
 */
export const mockItemsResponse = {
  data: [mockItem, mockItemWithoutSites],
  count: 2
}

/**
 * Mock study sites response
 */
export const mockStudySitesResponse = {
  data: [mockStudySite, mockStudySiteAuto],
  count: 2
}

/**
 * Create mock axios instance
 */
export function createMockApi() {
  return {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn(), eject: vi.fn() },
      response: { use: vi.fn(), eject: vi.fn() }
    }
  }
}

/**
 * Mock successful API responses
 */
export function mockApiSuccess(mockApi: any) {
  mockApi.get.mockImplementation((url: string) => {
    if (url.includes('/items/')) {
      return Promise.resolve({ data: mockItemsResponse })
    }
    if (url.includes('/study-sites/items/')) {
      return Promise.resolve({ data: mockStudySitesResponse })
    }
    if (url.match(/\/study-sites\/study-sites\/[\w-]+$/)) {
      return Promise.resolve({ data: mockStudySite })
    }
    return Promise.resolve({ data: {} })
  })

  mockApi.post.mockImplementation((url: string, data: any) => {
    if (url.includes('/study-sites/items/')) {
      return Promise.resolve({
        data: {
          ...mockStudySite,
          ...data,
          id: 'new-site-id'
        }
      })
    }
    return Promise.resolve({ data: {} })
  })

  mockApi.put.mockImplementation((url: string, data: any) => {
    return Promise.resolve({
      data: {
        ...mockStudySite,
        ...data
      }
    })
  })

  mockApi.delete.mockResolvedValue({ data: { message: 'Deleted' } })
}

/**
 * Mock API errors
 */
export function mockApiError(mockApi: any, errorMessage = 'API Error') {
  const error: any = new Error(errorMessage)
  error.response = {
    data: { detail: errorMessage },
    status: 400,
    statusText: 'Bad Request'
  }

  mockApi.get.mockRejectedValue(error)
  mockApi.post.mockRejectedValue(error)
  mockApi.put.mockRejectedValue(error)
  mockApi.delete.mockRejectedValue(error)
}
