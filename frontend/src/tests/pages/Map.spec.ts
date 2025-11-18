import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Map from '@/pages/Map.vue'
import { useStudySitesStore } from '@/stores/studySites'
import { useZoteroStore } from '@/stores/zotero'
import { setupTest, teardownTest } from '../utils/test-utils'

// Mock data
const mockLocation = {
  id: 'loc-1',
  latitude: 45.5,
  longitude: -122.3,
  cluster_label: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

const mockLocation2 = {
  id: 'loc-2',
  latitude: 40.7,
  longitude: -74.0,
  cluster_label: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

const mockStudySite = {
  id: 'site-1',
  item_id: 'paper-1',
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
  item_title: 'Test Paper 1',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

const mockStudySiteAuto = {
  id: 'site-2',
  item_id: 'paper-2',
  name: 'Auto Site',
  location: mockLocation2,
  location_id: 'loc-2',
  confidence_score: 0.72,
  validation_score: 0.8,
  context: 'Automatically extracted site',
  extraction_method: 'nlp',
  source_type: 'text',
  section: 'results',
  is_manual: false,
  item_title: 'Test Paper 2',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z'
}

const mockPaper1 = {
  id: 'paper-1',
  title: 'Test Paper 1',
  abstractNote: 'This is a test abstract',
  publicationTitle: 'Test Journal',
  date: '2024-01-15',
  itemType: 'journalArticle',
  study_sites: [mockStudySite]
}

const mockPaper2 = {
  id: 'paper-2',
  title: 'Test Paper 2',
  abstractNote: 'Another test abstract',
  publicationTitle: 'Science Journal',
  date: '2024-02-20',
  itemType: 'journalArticle',
  study_sites: [mockStudySiteAuto]
}

const mockPaperWithoutSites = {
  id: 'paper-3',
  title: 'Paper Without Sites',
  abstractNote: 'No study sites',
  publicationTitle: 'Empty Journal',
  date: '2024-03-10',
  itemType: 'journalArticle',
  study_sites: []
}

// Create mock router
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div>Home</div>' } },
    { path: '/map', component: { template: '<div>Map</div>' } }
  ]
})

describe('Map Page', () => {
  let wrapper: any
  let studySitesStore: any
  let zoteroStore: any

  const createWrapper = (routeQuery = {}) => {
    router.push({ path: '/map', query: routeQuery })

    return mount(Map, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          StudySiteMap: {
            template: '<div class="mock-map"></div>',
            methods: {
              panTo: vi.fn()
            }
          },
          VContainer: { template: '<div><slot /></div>' },
          VRow: { template: '<div><slot /></div>' },
          VCol: { template: '<div><slot /></div>' },
          VCard: { template: '<div><slot /></div>' },
          VCardText: { template: '<div><slot /></div>' },
          VCardTitle: { template: '<div><slot /></div>' },
          VCardActions: { template: '<div><slot /></div>' },
          VBtn: {
            template: '<button @click="$emit(\'click\')" :disabled="disabled"><slot /></button>',
            props: ['disabled', 'loading', 'icon', 'variant']
          },
          VTextField: {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue']
          },
          VSelect: {
            template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
            props: ['modelValue', 'items']
          },
          VDialog: {
            template: '<div v-if="modelValue"><slot /></div>',
            props: ['modelValue']
          },
          VList: { template: '<ul><slot /></ul>' },
          VListItem: {
            template: '<li @click="$emit(\'click\')"><slot /><slot name="prepend" /><slot name="append" /></li>',
            props: ['active']
          },
          VListItemTitle: { template: '<div><slot /></div>' },
          VListItemSubtitle: { template: '<div><slot /></div>' },
          VIcon: { template: '<i />' },
          VChip: {
            template: '<span @click="$emit(\'click\')"><slot /></span>',
            props: ['color', 'size', 'variant']
          },
          VAvatar: { template: '<div><slot /></div>', props: ['color', 'size'] },
          VEmptyState: { template: '<div><slot /></div>' },
          VDivider: { template: '<hr />' },
          VAlert: { template: '<div><slot /></div>' },
          VProgressLinear: { template: '<div />', props: ['modelValue', 'color'] },
          VTooltip: { template: '<div><slot /></div>' },
          VSpacer: { template: '<div />' }
        }
      }
    })
  }

  beforeEach(() => {
    setupTest()
    const pinia = createPinia()
    setActivePinia(pinia)

    // Mock Study Sites store
    studySitesStore = useStudySitesStore()
    studySitesStore.studySites = [mockStudySite, mockStudySiteAuto]
    studySitesStore.loading = false
    vi.spyOn(studySitesStore, 'fetchAllStudySites').mockImplementation(async () => {
      studySitesStore.studySites = [mockStudySite, mockStudySiteAuto]
    })

    // Mock Zotero store
    zoteroStore = useZoteroStore()
    zoteroStore.items = {
      data: [mockPaper1, mockPaper2, mockPaperWithoutSites],
      count: 3
    }
    zoteroStore.loading = false
    vi.spyOn(zoteroStore, 'fetchItems').mockImplementation(async () => {
      zoteroStore.items = {
        data: [mockPaper1, mockPaper2, mockPaperWithoutSites],
        count: 3
      }
    })
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    teardownTest()
  })

  describe('Rendering', () => {
    it('should render papers sidebar on the left', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('Papers')
    })

    it('should render study sites sidebar on the right', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('Study Sites')
    })

    it('should render map in the center', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const map = wrapper.find('.mock-map')
      expect(map.exists()).toBe(true)
    })

    it('should display papers count', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('3 papers')
    })

    it('should display study sites count', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('2 sites')
    })
  })

  describe('Data Loading', () => {
    it('should fetch study sites on mount', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(studySitesStore.fetchAllStudySites).toHaveBeenCalled()
    })

    it('should fetch papers on mount', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(zoteroStore.fetchItems).toHaveBeenCalled()
    })

    it('should load both papers and study sites in parallel', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(studySitesStore.fetchAllStudySites).toHaveBeenCalled()
      expect(zoteroStore.fetchItems).toHaveBeenCalled()
    })
  })

  describe('Papers List', () => {
    it('should display all papers', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('Test Paper 1')
      expect(wrapper.text()).toContain('Test Paper 2')
      expect(wrapper.text()).toContain('Paper Without Sites')
    })

    it('should show study sites count for each paper', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const papers = wrapper.vm.filteredPapers
      expect(papers[0].study_sites.length).toBe(1)
      expect(papers[1].study_sites.length).toBe(1)
      expect(papers[2].study_sites.length).toBe(0)
    })

    it('should display publication info as subtitle', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('Test Journal')
      expect(wrapper.text()).toContain('Science Journal')
    })
  })

  describe('Paper Filtering', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should filter papers by search query', async () => {
      wrapper.vm.paperSearchQuery = 'Paper Without'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredPapers).toHaveLength(1)
      expect(wrapper.vm.filteredPapers[0].title).toBe('Paper Without Sites')
    })

    it('should filter papers with study sites', async () => {
      wrapper.vm.paperFilterType = 'with_sites'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredPapers).toHaveLength(2)
      expect(wrapper.vm.filteredPapers.every((p: any) => p.study_sites.length > 0)).toBe(true)
    })

    it('should filter papers without study sites', async () => {
      wrapper.vm.paperFilterType = 'without_sites'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredPapers).toHaveLength(1)
      expect(wrapper.vm.filteredPapers[0].study_sites.length).toBe(0)
    })

    it('should search in title, abstract, and publication', async () => {
      wrapper.vm.paperSearchQuery = 'Science'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredPapers).toHaveLength(1)
      expect(wrapper.vm.filteredPapers[0].publicationTitle).toContain('Science')
    })
  })

  describe('Paper Selection', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should select paper on click', async () => {
      await wrapper.vm.handlePaperClick(mockPaper1)

      expect(wrapper.vm.selectedPaper).toEqual(mockPaper1)
    })

    it('should toggle paper selection on second click', async () => {
      await wrapper.vm.handlePaperClick(mockPaper1)
      expect(wrapper.vm.selectedPaper).toEqual(mockPaper1)

      await wrapper.vm.handlePaperClick(mockPaper1)
      expect(wrapper.vm.selectedPaper).toBeNull()
    })

    it('should clear paper selection', async () => {
      wrapper.vm.selectedPaper = mockPaper1
      await wrapper.vm.clearPaperSelection()

      expect(wrapper.vm.selectedPaper).toBeNull()
    })

    it('should filter study sites by selected paper', async () => {
      wrapper.vm.selectedPaper = mockPaper1
      await wrapper.vm.$nextTick()

      const filtered = wrapper.vm.filteredSites
      expect(filtered.every((s: any) => s.item_id === mockPaper1.id)).toBe(true)
    })
  })

  describe('Study Sites Dialog', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should open dialog when clicking study sites chip', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)

      expect(wrapper.vm.studySitesDialog).toBe(true)
      expect(wrapper.vm.dialogPaper).toEqual(mockPaper1)
    })

    it('should display study sites information in dialog', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Test Site 1')
      expect(wrapper.text()).toContain('Portland')
    })

    it('should show confidence score in dialog', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('85.0%')
    })

    it('should display location coordinates', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('45.5000')
      expect(wrapper.text()).toContain('-122.3000')
    })

    it('should display context text', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Study site in Portland')
    })

    it('should show extraction method', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Manual')
    })

    it('should close dialog', async () => {
      wrapper.vm.studySitesDialog = true
      wrapper.vm.studySitesDialog = false

      expect(wrapper.vm.studySitesDialog).toBe(false)
    })

    it('should filter by dialog paper when clicking "Show on Map"', async () => {
      await wrapper.vm.showPaperStudySites(mockPaper1)
      await wrapper.vm.filterByDialogPaper()

      expect(wrapper.vm.selectedPaper).toEqual(mockPaper1)
      expect(wrapper.vm.studySitesDialog).toBe(false)
    })
  })

  describe('Map Integration', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should pass filtered sites to map component', async () => {
      const mapComponent = wrapper.findComponent({ name: 'StudySiteMap' })
      expect(mapComponent.exists()).toBe(true)
      expect(mapComponent.props('sites')).toEqual(wrapper.vm.filteredSites)
    })

    it('should filter map markers when paper is selected', async () => {
      wrapper.vm.selectedPaper = mockPaper1
      await wrapper.vm.$nextTick()

      const mapComponent = wrapper.findComponent({ name: 'StudySiteMap' })
      const filteredSites = mapComponent.props('sites')

      expect(filteredSites.length).toBe(1)
      expect(filteredSites[0].item_id).toBe(mockPaper1.id)
    })

    it('should show all markers when no paper is selected', async () => {
      wrapper.vm.selectedPaper = null
      await wrapper.vm.$nextTick()

      const mapComponent = wrapper.findComponent({ name: 'StudySiteMap' })
      const sites = mapComponent.props('sites')

      expect(sites.length).toBe(2)
    })

    it('should pan to study site from dialog', async () => {
      const panToSpy = vi.fn()
      wrapper.vm.mapComponent = { panTo: panToSpy }

      await wrapper.vm.panToStudySite(mockStudySite)

      expect(panToSpy).toHaveBeenCalledWith(45.5, -122.3, 12, 1500)
      expect(wrapper.vm.selectedSite).toEqual(mockStudySite)
    })

    it('should close dialog when panning to site', async () => {
      wrapper.vm.studySitesDialog = true
      wrapper.vm.mapComponent = { panTo: vi.fn() }

      await wrapper.vm.panToStudySite(mockStudySite)

      expect(wrapper.vm.studySitesDialog).toBe(false)
    })

    it('should handle missing map component gracefully', async () => {
      wrapper.vm.mapComponent = null
      const consoleWarnSpy = vi.spyOn(console, 'warn')

      await wrapper.vm.panToStudySite(mockStudySite)

      expect(consoleWarnSpy).toHaveBeenCalledWith('Map component not initialized yet')
    })

    it('should handle invalid location data', async () => {
      wrapper.vm.mapComponent = { panTo: vi.fn() }
      const siteWithoutLocation = { ...mockStudySite, location: null }
      const consoleWarnSpy = vi.spyOn(console, 'warn')

      await wrapper.vm.panToStudySite(siteWithoutLocation)

      expect(consoleWarnSpy).toHaveBeenCalled()
    })

    it('should fit map to markers when paper selection changes', async () => {
      const fitToMarkersSpy = vi.fn()
      wrapper.vm.mapComponent = { fitToMarkers: fitToMarkersSpy }

      wrapper.vm.selectedPaper = mockPaper1
      await wrapper.vm.$nextTick()

      // Wait for the setTimeout in the watch
      await new Promise(resolve => setTimeout(resolve, 350))

      expect(fitToMarkersSpy).toHaveBeenCalled()
    })
  })

  describe('Refresh Functionality', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should refresh papers', async () => {
      await wrapper.vm.refreshPapers()

      expect(zoteroStore.fetchItems).toHaveBeenCalledTimes(2) // Once on mount, once on refresh
    })

    it('should refresh study sites', async () => {
      await wrapper.vm.refreshData()

      expect(studySitesStore.fetchAllStudySites).toHaveBeenCalledTimes(2)
    })
  })

  describe('Helper Functions', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should format paper subtitle correctly', () => {
      const subtitle = wrapper.vm.formatPaperSubtitle(mockPaper1)
      expect(subtitle).toContain('Test Journal')
      expect(subtitle).toContain('2024')
    })

    it('should handle missing publication info', () => {
      const paperWithoutInfo = { ...mockPaper1, publicationTitle: null, date: null }
      const subtitle = wrapper.vm.formatPaperSubtitle(paperWithoutInfo)
      expect(subtitle).toBe('No publication info')
    })

    it('should get correct study sites color for manual sites', () => {
      const color = wrapper.vm.getStudySitesColor([mockStudySite])
      expect(color).toBe('success')
    })

    it('should get correct study sites color for auto sites', () => {
      const color = wrapper.vm.getStudySitesColor([mockStudySiteAuto])
      expect(color).toBe('info')
    })

    it('should get default color for empty sites', () => {
      const color = wrapper.vm.getStudySitesColor([])
      expect(color).toBe('default')
    })

    it('should get confidence color based on score', () => {
      expect(wrapper.vm.getConfidenceColor(0.9)).toBe('success')
      expect(wrapper.vm.getConfidenceColor(0.6)).toBe('warning')
      expect(wrapper.vm.getConfidenceColor(0.3)).toBe('error')
    })

    it('should format extraction method', () => {
      expect(wrapper.vm.formatExtractionMethod('manual')).toBe('Manual')
      expect(wrapper.vm.formatExtractionMethod('nlp_extraction')).toBe('Nlp Extraction')
      expect(wrapper.vm.formatExtractionMethod('')).toBe('Unknown')
    })
  })

  describe('Query Parameters', () => {
    it('should load with itemTitle query param', async () => {
      wrapper = createWrapper({ itemTitle: 'Test Paper 1' })
      await flushPromises()

      expect(wrapper.vm.searchQuery).toBe('Test Paper 1')
    })

    it('should watch for itemTitle changes', async () => {
      wrapper = createWrapper()
      await flushPromises()

      await router.push({ path: '/map', query: { itemTitle: 'New Search' } })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.searchQuery).toBe('New Search')
    })
  })

  describe('Keyboard Navigation', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should clear selection on ESC key', async () => {
      wrapper.vm.selectedSite = mockStudySite
      wrapper.vm.selectedPaper = mockPaper1

      // Trigger ESC key event
      await wrapper.trigger('keydown.esc')
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.selectedSite).toBeNull()
      expect(wrapper.vm.selectedPaper).toBeNull()
    })
  })

  describe('Empty States', () => {
    it('should show empty state when no papers found', async () => {
      zoteroStore.items = { data: [], count: 0 }
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('No papers found')
    })

    it('should show empty state when no sites match filter', async () => {
      wrapper = createWrapper()
      await flushPromises()

      wrapper.vm.paperSearchQuery = 'Non-existent paper'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredPapers).toHaveLength(0)
    })

    it('should show message when paper has no study sites', async () => {
      wrapper = createWrapper()
      await flushPromises()

      await wrapper.vm.showPaperStudySites(mockPaperWithoutSites)
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('No study sites have been extracted')
    })
  })

  describe('Computed Properties', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should calculate total papers correctly', () => {
      expect(wrapper.vm.totalPapers).toBe(3)
    })

    it('should calculate total sites correctly', () => {
      expect(wrapper.vm.totalSites).toBe(2)
    })

    it('should extract papers from items data', () => {
      expect(wrapper.vm.papers).toEqual([mockPaper1, mockPaper2, mockPaperWithoutSites])
    })

    it('should handle missing items data', async () => {
      zoteroStore.items = {}
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.vm.papers).toEqual([])
    })
  })
})
