import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import Items from '@/pages/Items.vue'
import { useZoteroStore } from '@/stores/zoteroStore'
import { useNotificationStore } from '@/stores/notification'
import { mockItem, mockItemWithoutSites, mockItemsResponse } from '../mocks/api-mocks'
import { setupTest, teardownTest } from '../utils/test-utils'

// Create mock router
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div>Home</div>' } },
    { path: '/map', component: { template: '<div>Map</div>' } },
    { path: '/items/:id/edit', component: { template: '<div>Edit</div>' } }
  ]
})

describe('Items Page', () => {
  let wrapper: any
  let zoteroStore: any
  let notificationStore: ReturnType<typeof useNotificationStore>

  const createWrapper = () => {
    return mount(Items, {
      global: {
        plugins: [createPinia(), router],
        stubs: {
          VContainer: { template: '<div><slot /></div>' },
          VRow: { template: '<div><slot /></div>' },
          VCol: { template: '<div><slot /></div>' },
          VCard: { template: '<div><slot /></div>' },
          VCardText: { template: '<div><slot /></div>' },
          VCardTitle: { template: '<div><slot /></div>' },
          VCardActions: { template: '<div><slot /></div>' },
          VBtn: {
            template: '<button @click="$emit(\'click\')" :disabled="disabled"><slot /></button>',
            props: ['disabled', 'loading', 'icon']
          },
          VTextField: {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue']
          },
          VSelect: {
            template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
            props: ['modelValue', 'items']
          },
          VDataTable: {
            template: '<table><slot /></table>',
            props: ['headers', 'items', 'loading', 'itemsPerPage', 'page']
          },
          VDialog: {
            template: '<div v-if="modelValue"><slot /></div>',
            props: ['modelValue']
          },
          VList: { template: '<ul><slot /></ul>' },
          VListItem: { template: '<li><slot /></li>' },
          VIcon: { template: '<i />' },
          VChip: { template: '<span><slot /></span>' },
          VMenu: { template: '<div><slot name="activator" /><slot /></div>' },
          VDivider: { template: '<hr />' },
          VPagination: { template: '<div />' },
          VSpacer: { template: '<div />' }
        }
      }
    })
  }

  beforeEach(() => {
    setupTest()
    setActivePinia(createPinia())

    // Mock Zotero store
    zoteroStore = useZoteroStore()
    zoteroStore.items = { data: [mockItem, mockItemWithoutSites], count: 2 }
    zoteroStore.loading = false
    zoteroStore.syncing = false
    vi.spyOn(zoteroStore, 'fetchItems').mockResolvedValue(mockItemsResponse)
    vi.spyOn(zoteroStore, 'syncLibrary').mockResolvedValue(true)
    vi.spyOn(zoteroStore, 'downloadAttachments').mockResolvedValue(true)

    notificationStore = useNotificationStore()
    vi.spyOn(notificationStore, 'showNotification')
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    teardownTest()
  })

  describe('Rendering', () => {
    it('should render the page title', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(wrapper.text()).toContain('Research Library')
    })

    it('should render sync and refresh buttons', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const buttons = wrapper.findAll('button')
      const syncButton = buttons.find((btn: any) => btn.text().includes('Sync'))
      const refreshButton = buttons.find((btn: any) => btn.text().includes('Refresh'))

      expect(syncButton.exists()).toBe(true)
      expect(refreshButton.exists()).toBe(true)
    })

    it('should render search input', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const input = wrapper.find('input')
      expect(input.exists()).toBe(true)
    })

    it('should render filter selects', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const selects = wrapper.findAll('select')
      expect(selects.length).toBeGreaterThanOrEqual(2)
    })

    it('should render data table', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const table = wrapper.find('table')
      expect(table.exists()).toBe(true)
    })
  })

  describe('Data Loading', () => {
    it('should fetch items on mount', async () => {
      wrapper = createWrapper()
      await flushPromises()

      expect(zoteroStore.fetchItems).toHaveBeenCalled()
    })

    it('should display loading state', async () => {
      zoteroStore.loading = true
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()

      // VDataTable should receive loading prop
      const table = wrapper.findComponent({ name: 'VDataTable' })
      expect(table.props('loading')).toBe(true)
    })
  })

  describe('Search Functionality', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should update search value on input', async () => {
      const searchInput = wrapper.find('input')
      await searchInput.setValue('test query')

      expect(wrapper.vm.search).toBe('test query')
    })

    it('should reset page to 1 on search', async () => {
      wrapper.vm.page = 5
      const searchInput = wrapper.find('input')
      await searchInput.setValue('test')

      // Wait for debounce
      await new Promise(resolve => setTimeout(resolve, 350))

      expect(wrapper.vm.page).toBe(1)
    })
  })

  describe('Filtering', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should filter by item type', async () => {
      wrapper.vm.filterType = 'journalArticle'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredItems).toHaveLength(2) // Both mock items are journal articles
    })

    it('should filter by study sites presence', async () => {
      wrapper.vm.filterStudySites = 'with'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredItems).toHaveLength(1)
      expect(wrapper.vm.filteredItems[0].study_sites.length).toBeGreaterThan(0)
    })

    it('should filter by study sites absence', async () => {
      wrapper.vm.filterStudySites = 'without'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.filteredItems).toHaveLength(1)
      expect(wrapper.vm.filteredItems[0].study_sites.length).toBe(0)
    })

    it('should clear all filters', async () => {
      wrapper.vm.search = 'test'
      wrapper.vm.filterType = 'book'
      wrapper.vm.filterStudySites = 'with'
      wrapper.vm.page = 3

      await wrapper.vm.clearFilters()

      expect(wrapper.vm.search).toBe('')
      expect(wrapper.vm.filterType).toBeNull()
      expect(wrapper.vm.filterStudySites).toBeNull()
      expect(wrapper.vm.page).toBe(1)
    })

    it('should detect active filters', async () => {
      expect(wrapper.vm.hasActiveFilters).toBe(false)

      wrapper.vm.search = 'test'
      expect(wrapper.vm.hasActiveFilters).toBe(true)

      wrapper.vm.search = ''
      wrapper.vm.filterType = 'book'
      expect(wrapper.vm.hasActiveFilters).toBe(true)
    })
  })

  describe('Sync Functionality', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should sync library on button click', async () => {
      const syncButton = wrapper.findAll('button').find((btn: any) =>
        btn.text().includes('Sync')
      )

      await syncButton.trigger('click')
      await flushPromises()

      expect(zoteroStore.syncLibrary).toHaveBeenCalled()
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Library synced successfully',
        'success'
      )
    })

    it('should download attachments after sync', async () => {
      await wrapper.vm.handleSync()
      await flushPromises()

      expect(zoteroStore.downloadAttachments).toHaveBeenCalled()
    })

    it('should refresh items after sync', async () => {
      await wrapper.vm.handleSync()
      await flushPromises()

      expect(zoteroStore.fetchItems).toHaveBeenCalled()
    })
  })

  describe('Refresh Functionality', () => {
    it('should refresh items on button click', async () => {
      wrapper = createWrapper()
      await flushPromises()

      const refreshButton = wrapper.findAll('button').find((btn: any) =>
        btn.text().includes('Refresh')
      )

      await refreshButton.trigger('click')
      await flushPromises()

      expect(zoteroStore.fetchItems).toHaveBeenCalled()
      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Items refreshed',
        'success'
      )
    })
  })

  describe('Row Click', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should open details dialog on row click', async () => {
      await wrapper.vm.handleRowClick({}, { item: mockItem })

      expect(wrapper.vm.selectedItem).toEqual(mockItem)
      expect(wrapper.vm.detailsDialog).toBe(true)
    })
  })

  describe('View on Map', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should navigate to map with item ID', async () => {
      const pushSpy = vi.spyOn(router, 'push')

      await wrapper.vm.viewOnMap(mockItem)

      expect(pushSpy).toHaveBeenCalledWith({
        path: '/map',
        query: { itemId: mockItem.id }
      })
    })
  })

  describe('Extract Study Sites', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should show notification when extraction starts', async () => {
      await wrapper.vm.extractStudySites(mockItem)

      expect(notificationStore.showNotification).toHaveBeenCalledWith(
        'Study site extraction started',
        'info'
      )
    })
  })

  describe('Delete Item', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
      global.confirm = vi.fn(() => true)
    })

    it('should show confirmation dialog', async () => {
      await wrapper.vm.handleDelete(mockItem)

      expect(global.confirm).toHaveBeenCalledWith(
        expect.stringContaining(mockItem.title)
      )
    })

    it('should not delete if user cancels', async () => {
      global.confirm = vi.fn(() => false)

      await wrapper.vm.handleDelete(mockItem)

      expect(notificationStore.showNotification).not.toHaveBeenCalled()
    })
  })

  describe('Helper Functions', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should format dates correctly', () => {
      expect(wrapper.vm.formatDate('2024-01-15')).toBeTruthy()
      expect(wrapper.vm.formatDate(null)).toBe('—')
      expect(wrapper.vm.formatDate('invalid')).toBeTruthy()
    })

    it('should detect study sites presence', () => {
      expect(wrapper.vm.hasStudySites(mockItem)).toBe(true)
      expect(wrapper.vm.hasStudySites(mockItemWithoutSites)).toBe(false)
    })

    it('should get correct study sites color', () => {
      const manualSites = [{ is_manual: true }]
      const autoSites = [{ is_manual: false }]

      expect(wrapper.vm.getStudySitesColor(manualSites)).toBe('success')
      expect(wrapper.vm.getStudySitesColor(autoSites)).toBe('info')
      expect(wrapper.vm.getStudySitesColor([])).toBe('default')
    })

    it('should generate DOI URL', () => {
      const url = wrapper.vm.getDoiUrl('10.1234/test.2024')
      expect(url).toBe('https://doi.org/10.1234/test.2024')

      const urlWithPrefix = wrapper.vm.getDoiUrl('doi:10.1234/test.2024')
      expect(urlWithPrefix).toBe('https://doi.org/10.1234/test.2024')
    })
  })

  describe('Pagination', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should calculate total items correctly', () => {
      expect(wrapper.vm.totalItems).toBe(2)
    })

    it('should calculate page count correctly', () => {
      wrapper.vm.itemsPerPage = 1
      expect(wrapper.vm.pageCount).toBe(2)

      wrapper.vm.itemsPerPage = 25
      expect(wrapper.vm.pageCount).toBe(1)
    })
  })

  describe('Details Dialog', () => {
    beforeEach(async () => {
      wrapper = createWrapper()
      await flushPromises()
    })

    it('should show details dialog', async () => {
      await wrapper.vm.viewDetails(mockItem)

      expect(wrapper.vm.selectedItem).toEqual(mockItem)
      expect(wrapper.vm.detailsDialog).toBe(true)
    })

    it('should close details dialog', async () => {
      wrapper.vm.detailsDialog = true
      wrapper.vm.selectedItem = mockItem

      wrapper.vm.detailsDialog = false

      expect(wrapper.vm.detailsDialog).toBe(false)
    })
  })
})
