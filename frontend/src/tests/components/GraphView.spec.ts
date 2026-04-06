import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import GraphView from '@/components/GraphView.vue'
import { setupTest, teardownTest } from '../utils/test-utils'

const {
  mockCyInstance,
  mockCytoscapeFactory,
  mockCytoscapeUse,
  mockExportToImage,
  mockCalculateNodeImportance,
} = vi.hoisted(() => {
  const styleChain: any = {}
  styleChain.selector = vi.fn(() => styleChain)
  styleChain.style = vi.fn(() => styleChain)
  styleChain.update = vi.fn()

  const collection: any = {}
  collection.remove = vi.fn()
  collection.forEach = vi.fn()
  collection.components = vi.fn(() => ({ length: 1 }))
  collection.removeClass = vi.fn(() => collection)
  collection.addClass = vi.fn(() => collection)
  collection.difference = vi.fn(() => collection)
  collection.union = vi.fn(() => collection)
  collection.connectedNodes = vi.fn(() => collection)

  const layout = {
    run: vi.fn(),
    stop: vi.fn(),
  }

  const mockCyInstance = {
    nodes: vi.fn(() => ({ length: 0, forEach: vi.fn() })),
    edges: vi.fn(() => ({ length: 0, forEach: vi.fn() })),
    elements: vi.fn(() => collection),
    add: vi.fn(),
    remove: vi.fn(),
    layout: vi.fn(() => layout),
    fit: vi.fn(),
    center: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    startBatch: vi.fn(),
    endBatch: vi.fn(),
    style: vi.fn(() => styleChain),
    zoom: vi.fn(() => 1),
    pan: vi.fn(() => ({ x: 0, y: 0 })),
    destroy: vi.fn(),
  }

  const mockCytoscapeFactory = vi.fn(() => mockCyInstance)
  const mockCytoscapeUse = vi.fn()

  const mockExportToImage = vi.fn(async () => new Blob(['graph'], { type: 'image/png' }))
  const mockCalculateNodeImportance = vi.fn((items: any[], tags: any[]) => ({
    items: Object.fromEntries(items.map((item, idx) => [item.id, idx === 0 ? 1 : 0.5])),
    tags: Object.fromEntries(tags.map((tag, idx) => [tag.id, idx === 0 ? 1 : 0.5])),
  }))

  return {
    mockCyInstance,
    mockCytoscapeFactory,
    mockCytoscapeUse,
    mockExportToImage,
    mockCalculateNodeImportance,
  }
})

vi.mock('cytoscape', () => ({
  default: Object.assign(mockCytoscapeFactory, {
    use: mockCytoscapeUse,
  }),
}))

vi.mock('cytoscape-fcose', () => ({
  default: vi.fn(),
}))

vi.mock('cytoscape-dagre', () => ({
  default: vi.fn(),
}))

vi.mock('@/composables/useGraphComposable', () => ({
  useGraphComposable: () => ({
    getNodeColor: vi.fn(() => '#2196F3'),
    getNodeSize: vi.fn(() => 30),
    exportToImage: mockExportToImage,
    calculateNodeImportance: mockCalculateNodeImportance,
    clusterNodes: vi.fn(() => []),
  }),
}))

describe('GraphView.vue', () => {
  let wrapper: any

  const mockItems = [
    {
      id: 'item1',
      title: 'Test Paper 1',
      tags: ['tag1', 'tag2'],
      study_sites: [],
      creators: [],
    },
    {
      id: 'item2',
      title: 'Test Paper 2',
      tags: ['tag1'],
      study_sites: [],
      creators: [],
    },
  ]

  const mockTags = [
    { id: 'tag1', name: 'Machine Learning' },
    { id: 'tag2', name: 'Deep Learning' },
  ]

  const mountGraphView = (props: Record<string, any> = {}) => {
    return mount(GraphView, {
      props: {
        items: mockItems,
        tags: mockTags,
        ...props,
      },
      global: {
        stubs: {
          VCard: { template: '<div><slot /></div>' },
          NodeInfoDialog: { template: '<div class="node-info-dialog-stub" />' },
        },
      },
    })
  }

  beforeEach(() => {
    setupTest()
    vi.clearAllMocks()
    ;(globalThis.URL as any).createObjectURL = vi.fn(() => 'blob:graph')
    ;(globalThis.URL as any).revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
    teardownTest()
  })

  it('renders graph container and controls by default', () => {
    wrapper = mountGraphView()

    expect(wrapper.find('.graph-container').exists()).toBe(true)
    expect(wrapper.find('.graph-controls').exists()).toBe(true)
    expect(wrapper.find('.cytoscape-graph').exists()).toBe(true)
  })

  it('hides controls when showControls is false', () => {
    wrapper = mountGraphView({ showControls: false })
    expect(wrapper.find('.graph-controls').exists()).toBe(false)
  })

  it('builds nodes and edges from items and tags', () => {
    wrapper = mountGraphView()
    const graphData = wrapper.vm.buildGraphData

    const itemNodes = graphData.nodes.filter((n: any) => n.data.type === 'item')
    const tagNodes = graphData.nodes.filter((n: any) => n.data.type === 'tag')

    expect(itemNodes).toHaveLength(2)
    expect(tagNodes).toHaveLength(2)
    expect(graphData.edges).toHaveLength(3)
  })

  it('filters graph data with search query', async () => {
    wrapper = mountGraphView()
    wrapper.vm.searchQuery = 'Test Paper 1'
    await wrapper.vm.$nextTick()

    const graphData = wrapper.vm.buildGraphData
    const itemNodes = graphData.nodes.filter((n: any) => n.data.type === 'item')
    expect(itemNodes).toHaveLength(1)
    expect(itemNodes[0].data.originalData.id).toBe('item1')
  })

  it('clears the search query', async () => {
    wrapper = mountGraphView()
    wrapper.vm.searchQuery = 'Machine'
    await wrapper.vm.$nextTick()

    wrapper.vm.clearSearch()
    expect(wrapper.vm.searchQuery).toBe('')
  })

  it('changes layout when selected layout changes', async () => {
    wrapper = mountGraphView()
    await flushPromises()

    const initialCalls = mockCyInstance.layout.mock.calls.length
    wrapper.vm.selectedLayout = 'dagre'
    await wrapper.vm.$nextTick()

    expect(mockCyInstance.layout.mock.calls.length).toBeGreaterThan(initialCalls)
  })

  it('emits graphUpdated after node update handler', async () => {
    wrapper = mountGraphView()
    await wrapper.vm.handleNodeUpdated()

    expect(wrapper.emitted('graphUpdated')).toBeTruthy()
  })

  it('exports the graph through composable', async () => {
    wrapper = mountGraphView({ enableExport: true })
    await flushPromises()

    await wrapper.vm.exportGraph()

    expect(mockExportToImage).toHaveBeenCalled()
    expect(mockExportToImage).toHaveBeenCalledWith(mockCyInstance, 'png', 2)
  })

  it('generates initials from title text', () => {
    wrapper = mountGraphView()
    expect(wrapper.vm.getInitials('John Doe Smith')).toBe('JDS')
    expect(wrapper.vm.getInitials('')).toBe('?')
    expect(wrapper.vm.getInitials(null)).toBe('?')
  })

  it('destroys cytoscape instance on unmount', async () => {
    wrapper = mountGraphView()
    await flushPromises()

    wrapper.unmount()
    expect(mockCyInstance.destroy).toHaveBeenCalled()
  })
})
