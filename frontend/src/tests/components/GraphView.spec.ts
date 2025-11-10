import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import GraphView from '@/components/GraphView.vue'
import { setupTest, teardownTest, flushPromises } from '../utils/test-utils'

// Mock cytoscape
const mockCyInstance = {
  nodes: vi.fn().mockReturnValue({
    length: 5,
    forEach: vi.fn(),
    filter: vi.fn().mockReturnThis(),
    addClass: vi.fn().mockReturnThis(),
    removeClass: vi.fn().mockReturnThis()
  }),
  edges: vi.fn().mockReturnValue({
    length: 4,
    forEach: vi.fn()
  }),
  elements: vi.fn().mockReturnValue({
    components: vi.fn().mockReturnValue({ length: 1 })
  }),
  layout: vi.fn().mockReturnValue({
    run: vi.fn(),
    stop: vi.fn()
  }),
  fit: vi.fn(),
  center: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  png: vi.fn().mockReturnValue('data:image/png;base64,...'),
  destroy: vi.fn(),
  zoom: vi.fn().mockReturnValue(1),
  pan: vi.fn().mockReturnValue({ x: 0, y: 0 }),
  style: vi.fn().mockReturnThis(),
  add: vi.fn(),
  remove: vi.fn()
}

vi.mock('cytoscape', () => ({
  default: vi.fn(() => mockCyInstance)
}))

vi.mock('cytoscape-fcose', () => ({
  default: vi.fn()
}))

vi.mock('cytoscape-dagre', () => ({
  default: vi.fn()
}))

// Mock composable
vi.mock('@/composables/useGraphComposable', () => ({
  useGraphComposable: () => ({
    getNodeColor: vi.fn((type) => type === 'item' ? '#2196F3' : '#4CAF50'),
    getNodeSize: vi.fn(() => 30),
    exportToImage: vi.fn(() => 'data:image/png;base64,...'),
    calculateNodeImportance: vi.fn(() => ({
      items: { item1: 1, item2: 0.5 },
      tags: { tag1: 1, tag2: 0.3 }
    })),
    clusterNodes: vi.fn(() => [
      { clusterId: 0, nodeIds: ['item-item1', 'tag-tag1'] },
      { clusterId: 1, nodeIds: ['item-item2', 'tag-tag2'] }
    ])
  })
}))

describe('GraphView.vue', () => {
  let wrapper: any

  const mockItems = [
    {
      id: 'item1',
      title: 'Test Paper 1',
      authors: 'John Doe',
      tags: ['tag1', 'tag2'],
      study_sites: [],
      creators: []
    },
    {
      id: 'item2',
      title: 'Test Paper 2',
      authors: 'Jane Smith',
      tags: ['tag1'],
      study_sites: [],
      creators: []
    }
  ]

  const mockTags = [
    { id: 'tag1', name: 'Machine Learning' },
    { id: 'tag2', name: 'Deep Learning' }
  ]

  beforeEach(() => {
    setupTest()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    teardownTest()
  })

  describe('Rendering', () => {
    it('should render graph container', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      expect(wrapper.find('.graph-container').exists()).toBe(true)
      expect(wrapper.find('.cytoscape-graph').exists()).toBe(true)
    })

    it('should render controls when showControls is true', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true
        }
      })

      expect(wrapper.find('.graph-controls').exists()).toBe(true)
      expect(wrapper.find('.search-input').exists()).toBe(true)
      expect(wrapper.find('.layout-select').exists()).toBe(true)
    })

    it('should not render controls when showControls is false', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: false
        }
      })

      expect(wrapper.find('.graph-controls').exists()).toBe(false)
    })

    it('should render minimap when showMinimap is true', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showMinimap: true
        }
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      // Minimap should be rendered after cy is initialized
      expect(wrapper.vm.cy).toBeTruthy()
    })

    it('should not render minimap when showMinimap is false', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showMinimap: false
        }
      })

      expect(wrapper.find('.minimap-container').exists()).toBe(false)
    })
  })

  describe('Graph Data Building', () => {
    it('should build graph data from items and tags', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData

      expect(graphData).toHaveProperty('nodes')
      expect(graphData).toHaveProperty('edges')
      expect(Array.isArray(graphData.nodes)).toBe(true)
      expect(Array.isArray(graphData.edges)).toBe(true)
    })

    it('should create tag nodes', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData
      const tagNodes = graphData.nodes.filter((n: any) => n.data.type === 'tag')

      expect(tagNodes.length).toBe(2)
      expect(tagNodes[0].data.label).toBe('Machine Learning')
      expect(tagNodes[1].data.label).toBe('Deep Learning')
    })

    it('should create item nodes', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData
      const itemNodes = graphData.nodes.filter((n: any) => n.data.type === 'item')

      expect(itemNodes.length).toBe(2)
      expect(itemNodes[0].data.id).toBe('item_item1')
      expect(itemNodes[1].data.id).toBe('item_item2')
    })

    it('should create edges between items and tags', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData

      expect(graphData.edges.length).toBeGreaterThan(0)
      expect(graphData.edges[0]).toHaveProperty('data')
      expect(graphData.edges[0].data).toHaveProperty('source')
      expect(graphData.edges[0].data).toHaveProperty('target')
    })

    it('should filter nodes by search query', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      wrapper.vm.searchQuery = 'Machine'
      await wrapper.vm.$nextTick()

      const graphData = wrapper.vm.buildGraphData
      const tagNodes = graphData.nodes.filter((n: any) => n.data.type === 'tag')

      expect(tagNodes.length).toBe(1)
      expect(tagNodes[0].data.label).toBe('Machine Learning')
    })

    it('should warn when dataset is too large', () => {
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const largeItems = Array.from({ length: 1100 }, (_, i) => ({
        id: `item${i}`,
        title: `Paper ${i}`,
        authors: `Author ${i}`,
        tags: []
      }))

      wrapper = mount(GraphView, {
        props: {
          items: largeItems,
          tags: [],
          maxNodes: 1000
        }
      })

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Dataset too large')
      )

      consoleSpy.mockRestore()
    })
  })

  describe('Search Functionality', () => {
    it('should update searchQuery on input', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true
        }
      })

      const searchInput = wrapper.find('.search-input')
      await searchInput.setValue('Machine')

      expect(wrapper.vm.searchQuery).toBe('Machine')
    })

    it('should clear search on clear button click', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true
        }
      })

      wrapper.vm.searchQuery = 'Machine'
      await wrapper.vm.$nextTick()

      const clearBtn = wrapper.find('.clear-btn')
      await clearBtn.trigger('click')

      expect(wrapper.vm.searchQuery).toBe('')
    })

    it('should filter graph data based on search query', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      wrapper.vm.searchQuery = 'Test Paper 1'
      await wrapper.vm.$nextTick()

      const graphData = wrapper.vm.buildGraphData
      const itemNodes = graphData.nodes.filter((n: any) => n.data.type === 'item')

      expect(itemNodes.length).toBe(1)
      expect(itemNodes[0].data.originalData.title).toBe('Test Paper 1')
    })
  })

  describe('Layout Selection', () => {
    it('should change layout on select change', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true
        }
      })

      const layoutSelect = wrapper.find('.layout-select')
      await layoutSelect.setValue('fcose')

      expect(wrapper.vm.selectedLayout).toBe('fcose')
    })

    it('should apply layout when changed', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true,
          layoutType: 'random'
        }
      })

      await flushPromises()

      wrapper.vm.selectedLayout = 'dagre'
      await wrapper.vm.$nextTick()

      // Layout should be applied (checked via mock calls)
      expect(mockCyInstance.layout).toHaveBeenCalled()
    })
  })

  describe('Graph Controls', () => {
    it('should fit graph on fit button click', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true
        }
      })

      await flushPromises()

      const fitBtn = wrapper.findAll('.control-btn').find(btn =>
        btn.text().includes('Fit')
      )
      await fitBtn!.trigger('click')

      expect(mockCyInstance.fit).toHaveBeenCalled()
    })

    it('should center graph on center button click', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true
        }
      })

      await flushPromises()

      const centerBtn = wrapper.findAll('.control-btn').find(btn =>
        btn.text().includes('Center')
      )
      await centerBtn!.trigger('click')

      expect(mockCyInstance.center).toHaveBeenCalled()
    })

    it('should export graph on export button click', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          showControls: true,
          enableExport: true
        }
      })

      await flushPromises()

      const exportBtn = wrapper.findAll('.control-btn').find(btn =>
        btn.text().includes('Export')
      )
      await exportBtn!.trigger('click')

      expect(mockCyInstance.png).toHaveBeenCalled()
    })
  })

  describe('Node Selection', () => {
    it('should show node info panel when node is selected', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      wrapper.vm.selectedNode = {
        originalData: {
          title: 'Test Paper 1',
          authors: 'John Doe'
        }
      }
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.node-info-panel').exists()).toBe(true)
      expect(wrapper.find('.node-info-panel').text()).toContain('Test Paper 1')
    })

    it('should close node info panel on close button click', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        },
        global: {
          stubs: {
            VBtn: {
              template: '<button @click="$emit(\'click\')"><slot /></button>',
              props: ['icon']
            }
          }
        }
      })

      wrapper.vm.selectedNode = {
        originalData: {
          title: 'Test Paper 1'
        }
      }
      await wrapper.vm.$nextTick()

      const closeBtn = wrapper.find('.close-panel')
      await closeBtn.trigger('click')

      expect(wrapper.vm.selectedNode).toBeNull()
    })

    it('should not show node info panel when no node is selected', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      expect(wrapper.find('.node-info-panel').exists()).toBe(false)
    })
  })

  describe('Helper Functions', () => {
    it('should generate initials from title', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const initials = wrapper.vm.getInitials('John Doe Smith')
      expect(initials).toBe('JDS')
    })

    it('should handle empty title', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const initials = wrapper.vm.getInitials('')
      expect(initials).toBe('?')
    })

    it('should handle null title', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const initials = wrapper.vm.getInitials(null)
      expect(initials).toBe('?')
    })

    it('should limit initials to 3 characters', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      const initials = wrapper.vm.getInitials('One Two Three Four Five')
      expect(initials.length).toBeLessThanOrEqual(3)
    })
  })

  describe('Props', () => {
    it('should accept items prop', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: []
        }
      })

      expect(wrapper.props('items')).toEqual(mockItems)
    })

    it('should accept tags prop', () => {
      wrapper = mount(GraphView, {
        props: {
          items: [],
          tags: mockTags
        }
      })

      expect(wrapper.props('tags')).toEqual(mockTags)
    })

    it('should use default layout type', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      expect(wrapper.props('layoutType')).toBe('random')
    })

    it('should accept custom layout type', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          layoutType: 'fcose'
        }
      })

      expect(wrapper.props('layoutType')).toBe('fcose')
    })

    it('should accept colorScheme prop', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          colorScheme: 'category'
        }
      })

      expect(wrapper.props('colorScheme')).toBe('category')
    })

    it('should accept nodeSize prop', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          nodeSize: 'importance'
        }
      })

      expect(wrapper.props('nodeSize')).toBe('importance')
    })

    it('should accept maxNodes prop', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags,
          maxNodes: 500
        }
      })

      expect(wrapper.props('maxNodes')).toBe(500)
    })
  })

  describe('Lifecycle', () => {
    it('should initialize cytoscape on mount', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.cy).toBeTruthy()
    })

    it('should destroy cytoscape on unmount', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      await flushPromises()

      wrapper.unmount()

      expect(mockCyInstance.destroy).toHaveBeenCalled()
    })

    it('should update graph when items change', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      await flushPromises()

      const newItems = [
        ...mockItems,
        {
          id: 'item3',
          title: 'Test Paper 3',
          authors: 'Bob Johnson',
          tags: ['tag1']
        }
      ]

      await wrapper.setProps({ items: newItems })
      await wrapper.vm.$nextTick()

      const graphData = wrapper.vm.buildGraphData
      const itemNodes = graphData.nodes.filter((n: any) => n.data.type === 'item')

      expect(itemNodes.length).toBe(3)
    })

    it('should update graph when tags change', async () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: mockTags
        }
      })

      await flushPromises()

      const newTags = [
        ...mockTags,
        { id: 'tag3', name: 'Neural Networks' }
      ]

      await wrapper.setProps({ tags: newTags })
      await wrapper.vm.$nextTick()

      const graphData = wrapper.vm.buildGraphData
      const tagNodes = graphData.nodes.filter((n: any) => n.data.type === 'tag')

      expect(tagNodes.length).toBe(3)
    })
  })

  describe('Edge Cases', () => {
    it('should handle empty items array', () => {
      wrapper = mount(GraphView, {
        props: {
          items: [],
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData
      const itemNodes = graphData.nodes.filter((n: any) => n.data.type === 'item')

      expect(itemNodes.length).toBe(0)
    })

    it('should handle empty tags array', () => {
      wrapper = mount(GraphView, {
        props: {
          items: mockItems,
          tags: []
        }
      })

      const graphData = wrapper.vm.buildGraphData
      const tagNodes = graphData.nodes.filter((n: any) => n.data.type === 'tag')

      expect(tagNodes.length).toBe(0)
    })

    it('should handle items without tags', () => {
      const itemsWithoutTags = [
        {
          id: 'item1',
          title: 'Test Paper 1',
          authors: 'John Doe',
          tags: []
        }
      ]

      wrapper = mount(GraphView, {
        props: {
          items: itemsWithoutTags,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData

      expect(graphData.edges.length).toBe(0)
    })

    it('should handle items with null tags', () => {
      const itemsWithNullTags = [
        {
          id: 'item1',
          title: 'Test Paper 1',
          authors: 'John Doe',
          tags: null
        }
      ]

      wrapper = mount(GraphView, {
        props: {
          items: itemsWithNullTags,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData
      expect(graphData.edges.length).toBe(0)
    })

    it('should handle items with missing title', () => {
      const itemsWithoutTitle = [
        {
          id: 'item1',
          authors: 'John Doe',
          tags: ['tag1']
        }
      ]

      wrapper = mount(GraphView, {
        props: {
          items: itemsWithoutTitle as any,
          tags: mockTags
        }
      })

      const graphData = wrapper.vm.buildGraphData
      expect(graphData.nodes.length).toBeGreaterThan(0)
    })
  })
})
