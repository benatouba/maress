import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useStudySitesStore } from '@/stores/studySites'
import StudySiteMap from '@/components/maps/StudySiteMap.vue'

let pinia: ReturnType<typeof createPinia>

const vectorSourceInstance = {
  clear: vi.fn(),
  addFeature: vi.fn(),
  getExtent: vi.fn(() => [0, 0, 10, 10]),
}

const clusterSourceInstance = {
  setSource: vi.fn(),
}

const mapViewInstance = {
  fit: vi.fn(),
  setCenter: vi.fn(),
  setZoom: vi.fn(),
  animate: vi.fn(),
}

const mapInstance = {
  on: vi.fn(),
  hasFeatureAtPixel: vi.fn(() => false),
  getTargetElement: vi.fn(() => ({ style: {} })),
  forEachFeatureAtPixel: vi.fn(() => undefined),
  getView: vi.fn(() => mapViewInstance),
  setTarget: vi.fn(),
}

vi.mock('ol', () => ({
  Map: vi.fn(() => mapInstance),
  View: vi.fn(() => mapViewInstance),
  Feature: vi.fn((data) => ({
    get: (key: string) => data[key],
    getGeometry: () => ({ getCoordinates: () => [0, 0] }),
  })),
}))

vi.mock('ol/layer', () => ({
  Tile: vi.fn(() => ({})),
  Vector: vi.fn(() => ({})),
}))

vi.mock('ol/source', () => ({
  OSM: vi.fn(() => ({})),
  Vector: vi.fn(() => vectorSourceInstance),
  Cluster: vi.fn(() => clusterSourceInstance),
}))

vi.mock('ol/geom', () => ({
  Point: vi.fn((coords) => ({ coords })),
}))

vi.mock('ol/proj', () => ({
  fromLonLat: vi.fn((coords) => coords),
  toLonLat: vi.fn((coords) => coords),
}))

vi.mock('ol/style', () => ({
  Style: vi.fn(() => ({})),
  Circle: vi.fn(() => ({})),
  Fill: vi.fn(() => ({})),
  Stroke: vi.fn(() => ({})),
  Text: vi.fn(() => ({})),
}))

vi.mock('ol/extent', () => ({
  boundingExtent: vi.fn(() => [0, 0, 10, 10]),
}))

describe('StudySiteMap', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  const mountComponent = (sites?: any[]) => {
    return mount(StudySiteMap, {
      props: sites ? { sites } : {},
      global: {
        plugins: [pinia],
        stubs: {
          StudySiteEditDialog: { template: '<div />' },
          StudySiteCreateDialog: { template: '<div />' },
          VOverlay: { template: '<div><slot /></div>' },
          VProgressCircular: { template: '<div />' },
          VCard: { template: '<div><slot /></div>' },
          VCardText: { template: '<div><slot /></div>' },
          VBtn: { template: '<button><slot /></button>' },
        },
      },
    })
  }

  it('adds one feature per valid map point from store', async () => {
    const studySitesStore = useStudySitesStore()
    studySitesStore.mapPoints = [
      {
        id: 'site-1',
        name: 'A',
        item_id: 'item-1',
        item_title: 'Paper A',
        latitude: 45.5,
        longitude: -122.3,
        is_manual: true,
        confidence_score: 0.9,
      },
      {
        id: 'site-2',
        name: 'B',
        item_id: 'item-2',
        item_title: 'Paper B',
        latitude: 40.7,
        longitude: -74,
        is_manual: false,
        confidence_score: 0.8,
      },
    ]

    mountComponent()
    await Promise.resolve()

    expect(vectorSourceInstance.clear).toHaveBeenCalled()
    expect(vectorSourceInstance.addFeature).toHaveBeenCalledTimes(2)
  })

  it('skips points with null coordinates', async () => {
    const studySitesStore = useStudySitesStore()
    studySitesStore.mapPoints = [
      {
        id: 'site-1',
        name: 'A',
        item_id: 'item-1',
        item_title: 'Paper A',
        latitude: null,
        longitude: -122.3,
        is_manual: true,
        confidence_score: 0.9,
      } as any,
      {
        id: 'site-2',
        name: 'B',
        item_id: 'item-2',
        item_title: 'Paper B',
        latitude: 40.7,
        longitude: null,
        is_manual: false,
        confidence_score: 0.8,
      } as any,
    ]

    mountComponent()
    await Promise.resolve()

    expect(vectorSourceInstance.addFeature).not.toHaveBeenCalled()
  })

  it('keeps valid zero coordinates (0, 0)', async () => {
    const studySitesStore = useStudySitesStore()
    studySitesStore.mapPoints = [
      {
        id: 'site-0',
        name: 'Null Island',
        item_id: 'item-0',
        item_title: 'Paper 0',
        latitude: 0,
        longitude: 0,
        is_manual: false,
        confidence_score: 0.5,
      },
    ]

    mountComponent()
    await Promise.resolve()

    expect(vectorSourceInstance.addFeature).toHaveBeenCalledTimes(1)
  })

  it('uses props.sites instead of store mapPoints when provided', async () => {
    const studySitesStore = useStudySitesStore()
    studySitesStore.mapPoints = []

    mountComponent([
      {
        id: 'site-prop',
        name: 'From props',
        item_id: 'item-prop',
        item_title: 'Paper prop',
        latitude: 10,
        longitude: 20,
        is_manual: true,
        confidence_score: 1,
      },
    ])
    await Promise.resolve()

    expect(vectorSourceInstance.addFeature).toHaveBeenCalledTimes(1)
  })
})
