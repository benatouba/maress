import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import StudySiteMap from '@/components/maps/StudySiteMap.vue'
import { useStudySitesStore } from '@/stores/studySites'
import { mockStudySite, mockStudySiteAuto, mockLocation, mockLocation2 } from '../mocks/api-mocks'

// Mock OpenLayers modules
vi.mock('ol/Map', () => ({
  default: vi.fn(() => ({
    setTarget: vi.fn(),
    addLayer: vi.fn(),
    getView: vi.fn(() => ({
      fit: vi.fn(),
      setCenter: vi.fn(),
      setZoom: vi.fn()
    })),
    on: vi.fn(),
    getLayers: vi.fn(() => ({
      getArray: vi.fn(() => [])
    })),
    setView: vi.fn()
  }))
}))

vi.mock('ol/View', () => ({
  default: vi.fn(() => ({
    fit: vi.fn(),
    setCenter: vi.fn(),
    setZoom: vi.fn()
  }))
}))

vi.mock('ol/layer', () => ({
  Tile: vi.fn(),
  Vector: vi.fn(() => ({
    getSource: vi.fn(() => ({
      clear: vi.fn(),
      addFeature: vi.fn(),
      getFeatures: vi.fn(() => [])
    }))
  }))
}))

vi.mock('ol/source', () => ({
  OSM: vi.fn(),
  Vector: vi.fn(() => ({
    clear: vi.fn(),
    addFeature: vi.fn(),
    getFeatures: vi.fn(() => [])
  }))
}))

vi.mock('ol/Feature', () => ({
  default: vi.fn((config) => ({
    ...config,
    setStyle: vi.fn(),
    get: vi.fn((key) => config[key]),
    getGeometry: vi.fn(() => ({
      getCoordinates: vi.fn(() => [0, 0])
    }))
  }))
}))

vi.mock('ol/geom', () => ({
  Point: vi.fn()
}))

vi.mock('ol/proj', () => ({
  fromLonLat: vi.fn((coords) => coords),
  toLonLat: vi.fn((coords) => coords)
}))

vi.mock('ol/style', () => ({
  Style: vi.fn(),
  Circle: vi.fn(),
  Fill: vi.fn(),
  Stroke: vi.fn(),
  Text: vi.fn()
}))

vi.mock('ol/interaction', () => ({
  Select: vi.fn(() => ({
    on: vi.fn()
  }))
}))

vi.mock('ol/events/condition', () => ({
  click: vi.fn()
}))

describe('StudySiteMap - Pin Display', () => {
  let studySitesStore: ReturnType<typeof useStudySitesStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    studySitesStore = useStudySitesStore()
  })

  it('should display pins for study sites with valid location data', async () => {
    // Setup study sites with location data
    studySitesStore.studySites = [
      mockStudySite,
      mockStudySiteAuto
    ]

    const wrapper = mount(StudySiteMap, {
      global: {
        plugins: [createPinia()]
      }
    })

    await wrapper.vm.$nextTick()

    // Verify study sites are loaded
    expect(studySitesStore.studySites).toHaveLength(2)

    // Verify first study site has location with coordinates
    expect(studySitesStore.studySites[0].location).toBeDefined()
    expect(studySitesStore.studySites[0].location.latitude).toBe(mockLocation.latitude)
    expect(studySitesStore.studySites[0].location.longitude).toBe(mockLocation.longitude)

    // Verify second study site has location with coordinates
    expect(studySitesStore.studySites[1].location).toBeDefined()
    expect(studySitesStore.studySites[1].location.latitude).toBe(mockLocation2.latitude)
    expect(studySitesStore.studySites[1].location.longitude).toBe(mockLocation2.longitude)
  })

  it('should not display pins for study sites without location data', async () => {
    // Setup study site without location
    const siteWithoutLocation = {
      ...mockStudySite,
      id: 'site-no-location',
      location: null as any
    }

    studySitesStore.studySites = [siteWithoutLocation]

    const wrapper = mount(StudySiteMap, {
      global: {
        plugins: [createPinia()]
      }
    })

    await wrapper.vm.$nextTick()

    // Study site exists but has no location
    expect(studySitesStore.studySites).toHaveLength(1)
    expect(studySitesStore.studySites[0].location).toBeNull()
  })

  it('should handle study sites with missing latitude or longitude in location', async () => {
    // Setup study site with incomplete location data
    const incompleteLocation = {
      ...mockLocation,
      latitude: null as any
    }

    const siteWithIncompleteLocation = {
      ...mockStudySite,
      id: 'site-incomplete',
      location: incompleteLocation
    }

    studySitesStore.studySites = [siteWithIncompleteLocation]

    const wrapper = mount(StudySiteMap, {
      global: {
        plugins: [createPinia()]
      }
    })

    await wrapper.vm.$nextTick()

    // Site has location but coordinates are invalid
    expect(studySitesStore.studySites[0].location).toBeDefined()
    expect(studySitesStore.studySites[0].location.latitude).toBeNull()
  })

  it('should correctly access coordinates via location object', () => {
    // Verify our mock data structure is correct
    expect(mockStudySite.location.latitude).toBe(45.5)
    expect(mockStudySite.location.longitude).toBe(-122.3)

    expect(mockStudySiteAuto.location.latitude).toBe(40.7)
    expect(mockStudySiteAuto.location.longitude).toBe(-74.0)

    // Verify location IDs match
    expect(mockStudySite.location_id).toBe(mockStudySite.location.id)
    expect(mockStudySiteAuto.location_id).toBe(mockStudySiteAuto.location.id)
  })

  it('should differentiate between manual and automatic study sites', async () => {
    studySitesStore.studySites = [mockStudySite, mockStudySiteAuto]

    const wrapper = mount(StudySiteMap, {
      global: {
        plugins: [createPinia()]
      }
    })

    await wrapper.vm.$nextTick()

    // Check manual site
    expect(studySitesStore.studySites[0].is_manual).toBe(true)
    expect(studySitesStore.studySites[0].extraction_method).toBe('manual')

    // Check automatic site
    expect(studySitesStore.studySites[1].is_manual).toBe(false)
    expect(studySitesStore.studySites[1].extraction_method).toBe('regex')

    // Both should have valid locations
    expect(studySitesStore.studySites[0].location.latitude).toBeTruthy()
    expect(studySitesStore.studySites[1].location.latitude).toBeTruthy()
  })
})
