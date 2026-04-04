import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useGisStore } from '@/stores/gis'
import api from '@/services/api'
import { setupTest, teardownTest } from '../utils/test-utils'

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('GIS Store', () => {
  let store: ReturnType<typeof useGisStore>

  beforeEach(() => {
    setupTest()
    setActivePinia(createPinia())
    store = useGisStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    teardownTest()
  })

  it('fetches capabilities', async () => {
    const mockGet = vi.mocked(api.get)
    mockGet.mockResolvedValueOnce({
      data: {
        version: 'draft-v1',
        operations: [{ id: 'buffer', enabled: true }],
        limits: { max_features_sync: 25000 },
      },
    })

    await store.fetchCapabilities()

    expect(mockGet).toHaveBeenCalledWith('/gis/capabilities')
    expect(store.capabilitiesVersion).toBe('draft-v1')
    expect(store.capabilities).toHaveLength(1)
  })

  it('runs buffer and stores features', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValueOnce({
      data: {
        target_layer_id: 'study-sites',
        distance_meters: 1000,
        dissolved: false,
        count: 1,
        features: [{ source_id: 'site-1', geometry: { type: 'Polygon', coordinates: [] } }],
      },
    })

    const result = await store.runBuffer(
      { layer_id: 'study-sites', selection: { type: 'all' } },
      { distance: 1000, unit: 'meter', dissolve: false },
    )

    expect(mockPost).toHaveBeenCalledWith('/gis/operations/buffer', expect.any(Object))
    expect(result?.count).toBe(1)
    expect(store.bufferFeatures).toHaveLength(1)
  })

  it('runs clip and stores clipped study sites', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValueOnce({
      data: {
        target_layer_id: 'study-sites',
        clip_layer_id: 'regions',
        count: 1,
        study_sites: [
          {
            id: 'site-1',
            name: 'A',
            item_id: 'item-1',
            item_title: 'Paper',
            latitude: 1,
            longitude: 2,
            is_manual: true,
            confidence_score: 1,
          },
        ],
      },
    })

    const result = await store.runClip(
      { layer_id: 'study-sites', selection: { type: 'all' } },
      { layer_id: 'regions', selection: { type: 'ids', ids: ['region-1'] } },
    )

    expect(result?.count).toBe(1)
    expect(store.clippedStudySites).toHaveLength(1)
  })

  it('runs within-distance and stores returned features', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValueOnce({
      data: {
        source_layer_id: 'study-sites',
        against_layer_id: 'regions',
        return_layer_id: 'study-sites',
        distance_meters: 1000,
        count: 1,
        study_sites: [
          {
            id: 'site-1',
            name: 'A',
            item_id: 'item-1',
            item_title: 'Paper',
            latitude: 1,
            longitude: 2,
            is_manual: true,
            confidence_score: 1,
          },
        ],
        regions: null,
      },
    })

    const result = await store.runWithinDistance(
      { layer_id: 'study-sites', selection: { type: 'all' } },
      { layer_id: 'regions', selection: { type: 'all' } },
      { distance: 1000, unit: 'meter', return: 'source' },
    )

    expect(mockPost).toHaveBeenCalledWith('/gis/operations/within-distance', expect.any(Object))
    expect(result?.count).toBe(1)
    expect(store.withinDistanceStudySites).toHaveLength(1)
    expect(store.withinDistanceRegions).toHaveLength(0)
  })

  it('runs summary-stats and stores rows', async () => {
    const mockPost = vi.mocked(api.post)
    mockPost.mockResolvedValueOnce({
      data: {
        rows: [
          { is_manual: true, site_count: 3, avg_confidence: 0.8 },
        ],
        count: 1,
      },
    })

    const result = await store.runSummaryStats({
      target: { layer_id: 'study-sites', selection: { type: 'all' } },
      group_by: ['is_manual'],
      metrics: [
        { type: 'count', field: 'id', alias: 'site_count' },
      ],
    })

    expect(mockPost).toHaveBeenCalledWith('/gis/operations/summary-stats', expect.any(Object))
    expect(result?.count).toBe(1)
    expect(store.summaryStatsRows).toHaveLength(1)
    expect(store.summaryStatsCount).toBe(1)
  })
})
