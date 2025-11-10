<template>
  <v-card class="graph-container">
    <!-- Search and Controls -->
    <div
      class="graph-controls"
      v-if="showControls">
      <div class="search-section">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search nodes..."
          class="search-input" />
        <button
          @click="clearSearch"
          class="clear-btn">
          ×
        </button>
      </div>

      <div class="filter-section">
        <select
          v-model="filterType"
          class="filter-select">
          <option value="all">All Nodes</option>
          <option value="items">Items Only</option>
          <option value="tags">Tags Only</option>
        </select>
      </div>

      <div class="layout-section">
        <select
          v-model="selectedLayout"
          class="layout-select">
          <option value="random">Random</option>
          <option value="fcose">fCoSE (Force-directed)</option>
          <option value="dagre">Dagre (Hierarchical)</option>
          <option value="grid">Grid</option>
          <option value="circle">Circle</option>
        </select>

        <button
          @click="fitGraph"
          class="control-btn">
          Fit
        </button>
        <button
          @click="centerGraph"
          class="control-btn">
          Center
        </button>
        <button
          @click="exportGraph"
          class="control-btn">
          Export
        </button>
      </div>
    </div>

    <!-- Main Graph -->
    <div class="graph-content">
      <div
        ref="cytoscapeContainer"
        class="cytoscape-graph"></div>
    </div>

    <!-- Minimap -->
    <div
      v-if="showMinimap && cy"
      ref="minimapContainer"
      class="minimap-container"></div>

    <!-- Node Info Dialog -->
    <NodeInfoDialog
      v-model="showNodeDialog"
      :node-data="selectedNodeData"
      :node-type="selectedNodeType"
      :all-items="items"
      :all-tags="tags"
      @updated="handleNodeUpdated" />
  </v-card>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, computed, onUnmounted } from 'vue'
import cytoscape from 'cytoscape'
import fcose from 'cytoscape-fcose'
import dagre from 'cytoscape-dagre'
import { useGraphComposable } from '@/composables/useGraphComposable'
import NodeInfoDialog from './NodeInfoDialog.vue'

// Register layout extensions
cytoscape.use(fcose)
cytoscape.use(dagre)

// Define emits
const emit = defineEmits(['nodeSelected', 'graphUpdated'])

// Props with enhanced configuration
const props = defineProps({
  items: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
  layoutType: { type: String, default: 'random' },
  showControls: { type: Boolean, default: true },
  showMinimap: { type: Boolean, default: false },
  enableClustering: { type: Boolean, default: false },
  colorScheme: { type: String, default: 'default' },
  nodeSize: { type: String, default: 'uniform' }, // uniform, degree, importance
  enableExport: { type: Boolean, default: true },
  maxNodes: { type: Number, default: 1000 }, // Performance limit
})

// Reactive state
const cytoscapeContainer = ref(null)
const minimapContainer = ref(null)
const searchQuery = ref('')
const selectedLayout = ref(props.layoutType)
const filterType = ref('all')
const selectedNode = ref(null)
const showNodeDialog = ref(false)
const selectedNodeData = ref(null)
const selectedNodeType = ref('item')
let cy = null
let minimap = null

// Use composable for graph utilities
const { getNodeColor, getNodeSize, exportToImage, calculateNodeImportance, clusterNodes } =
  useGraphComposable()

// Enhanced initials function with better handling
const getInitials = (title) => {
  if (!title) return '?'
  const words = title
    .trim()
    .split(/\s+/)
    .filter((word) => word.length > 0)
  if (words.length === 0) return '?'

  return words
    .map((word) => word.charAt(0).toUpperCase())
    .join('')
    .substring(0, 3)
}

// Optimized computed graph data with search and type filtering
const buildGraphData = computed(() => {
  // Performance check
  if (props.items.length > props.maxNodes) {
    console.warn(
      `Dataset too large (${props.items.length} > ${props.maxNodes}). Consider pagination.`,
    )
  }

  // Filter nodes by search query
  let filteredItems =
    searchQuery.value ?
      props.items.filter(
        (item) =>
          item.title?.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
          item.description?.toLowerCase().includes(searchQuery.value.toLowerCase()),
      )
    : props.items

  let filteredTags =
    searchQuery.value ?
      props.tags.filter((tag) => tag.name?.toLowerCase().includes(searchQuery.value.toLowerCase()))
    : props.tags

  // Apply type filter
  if (filterType.value === 'items') {
    filteredTags = []
  } else if (filterType.value === 'tags') {
    filteredItems = []
  }

  const nodes = []
  const edges = []
  const nodeImportance = calculateNodeImportance(filteredItems, filteredTags)

  // Add tag nodes with enhanced styling
  filteredTags.forEach((tag) => {
    const importance = nodeImportance.tags[tag.id] || 0
    nodes.push({
      group: 'nodes',
      data: { id: `tag_${tag.id}`, label: tag.name, type: 'tag', importance, originalData: tag },
    })
  })

  // Add item nodes with enhanced styling
  filteredItems.forEach((item) => {
    const importance = nodeImportance.items[item.id] || 0
    nodes.push({
      group: 'nodes',
      data: {
        id: `item_${item.id}`,
        label: getInitials(item.authors),
        type: 'item',
        importance,
        originalData: item,
      },
    })

    // Create edges from items to their tags
    if (item.tags && Array.isArray(item.tags)) {
      item.tags.forEach((tagId) => {
        // Only create edge if tag exists in filtered set
        if (filteredTags.some((tag) => tag.id === tagId)) {
          edges.push({
            group: 'edges',
            data: {
              id: `edge_${item.id}_${tagId}`,
              source: `item_${item.id}`,
              target: `tag_${tagId}`,
            },
          })
        }
      })
    }
  })

  return { nodes, edges }
})

// Enhanced layout configurations
const getLayoutConfig = (layoutName = selectedLayout.value) => {
  const nodeCount = buildGraphData.value.nodes.length

  // Auto-select layout based on size [web:8]
  if (nodeCount > 1000 && layoutName === 'fcose') {
    layoutName = 'grid' // Grid is much faster for large datasets
  }

  const configs = {
    random: {
      name: 'random',
      fit: true,
      padding: 30,
      // CRITICAL: Add these parameters for true randomness
      boundingBox: undefined, // Use full viewport
      animate: false, // Disable animation for instant randomness
      animationDuration: 0,
      refresh: 0,
      // Force random positioning regardless of node connections
      randomize: true,
      // Set explicit boundaries to prevent clustering
      avoidOverlap: true,
      avoidOverlapPadding: 10,
    },
    fcose: {
      name: 'fcose',
      quality: nodeCount > 500 ? 'draft' : 'default', // Use draft quality for large graphs
      randomize: false, // Don't randomize for faster convergence
      animate: nodeCount < 200 ? 'end' : false, // Disable animation for large datasets
      animationDuration: 500, // Reduce animation time
      fit: true,
      padding: 20,

      // Performance optimizations
      numIter: Math.min(2500, Math.max(50, 5000 / nodeCount)), // Adaptive iterations
      coolingFactor: 0.99,
      nodeRepulsion: () => Math.max(1000, 10000 / nodeCount), // Adaptive repulsion
    },

    // Grid layout is fastest for large datasets
    grid: {
      name: 'grid',
      fit: true,
      padding: 20,
      avoidOverlap: true,
      avoidOverlapPadding: 5,
      animate: false, // No animation for grid
      spacingFactor: 1.2,
    },
  }

  return configs[layoutName] || configs.grid
}

// Enhanced styling with dynamic colors and sizes
const getStylesheet = () => [
  // Base node style
  {
    selector: 'node',
    style: {
      'background-color': (ele) => getNodeColor(ele.data('type'), props.colorScheme),
      'border-color': (ele) => getNodeColor(ele.data('type'), props.colorScheme, true),
      'border-width': 2,
      label: 'data(label)',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-family': 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
      'font-size': (ele) => {
        if (props.nodeSize === 'importance') {
          const importance = ele.data('importance') || 0
          return Math.max(10, Math.min(18, 10 + importance * 2))
        }
        return '12px'
      },
      'font-weight': '600',
      width: (ele) => getNodeSize(ele.data('type'), ele.data('importance'), props.nodeSize),
      height: (ele) => getNodeSize(ele.data('type'), ele.data('importance'), props.nodeSize),
      'text-wrap': 'wrap',
      'text-max-width': '80px',
      'transition-property': 'background-color, border-color, width, height',
      'transition-duration': '0.3s',
      'transition-timing-function': 'ease-out',
    },
  },

  // Tag-specific styles
  {
    selector: 'node[type="tag"]',
    style: {
      shape: 'round-rectangle',
      'background-color': '#8E44AD',
      'border-color': '#6C3483',
      'text-outline-color': '#ffffff',
      'text-outline-width': 1,
      color: '#ffffff',
    },
  },

  // Item-specific styles
  {
    selector: 'node[type="item"]',
    style: {
      shape: 'ellipse',
      'background-color': '#3498DB',
      'border-color': '#2980B9',
      color: '#ffffff',
      'text-outline-color': '#2980B9',
      'text-outline-width': 1,
    },
  },

  // Enhanced edge styles
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#BDC3C7',
      'target-arrow-color': '#BDC3C7',
      'target-arrow-shape': 'triangle-backcurve',
      'arrow-scale': 1.5,
      'curve-style': 'straight',
      opacity: 0.8,
      'transition-property': 'line-color, width, opacity',
      'transition-duration': '0.2s',
    },
  },

  // Selection states
  {
    selector: 'node:selected',
    style: {
      'background-color': '#E67E22',
      'border-color': '#D35400',
      'border-width': '3px',
      'z-index': 10,
    },
  },

  // Hover/highlight states
  {
    selector: 'node.highlighted',
    style: {
      'border-width': '3px',
      'border-color': '#E74C3C',
      'z-index': 10,
      'font-size': '14px',
      'font-weight': 'bold',
      'text-outline-width': 2,
    },
  },

  {
    selector: 'edge.highlighted',
    style: {
      'line-color': '#E74C3C',
      'target-arrow-color': '#E74C3C',
      width: 4,
      opacity: 1,
      'z-index': 10,
    },
  },

  // Dimmed states for search
  { selector: 'node.dimmed', style: { opacity: 0.3 } },

  { selector: 'edge.dimmed', style: { opacity: 0.1 } },
]

// Initialize cytoscape with all optimizations
const initCytoscape = async () => {
  if (!cytoscapeContainer.value) return

  try {
    const { nodes, edges } = buildGraphData.value

    cy = cytoscape({
      container: cytoscapeContainer.value,
      elements: [...nodes, ...edges],
      style: getStylesheet(),
      layout: getLayoutConfig(),
      renderer: 'webgl', // Use WebGL renderer for better performance

      // CRITICAL PERFORMANCE SETTINGS
      textureOnViewport: true, // Use textures when viewport changes [web:32][web:52]
      motionBlur: true, // Enable motion blur for smooth animations [web:8][web:32]
      motionBlurOpacity: 0.2,
      pixelRatio: 'auto',

      minZoom: 0.1, // Prevent excessive zoom out
      maxZoom: 5.0, // Prevent excessive zoom in

      // Disable expensive features during interaction
      hideEdgesOnViewport: nodes.length > 500, // Hide edges during pan/zoom [web:8]
      hideLabelsOnViewport: nodes.length > 200, // Hide labels during interaction [web:47]

      // Interaction settings
      zoomingEnabled: true,
      userZoomingEnabled: true,
      panningEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false, // Disable if not needed
      selectionType: 'single',
      autoungrabify: false,
      autounselectify: false,
    })

    // Enhanced event handling
    setupEventHandlers()

    // Initialize minimap if enabled
    if (props.showMinimap) {
      initMinimap()
    }
  } catch (error) {
    console.error('Failed to initialize cytoscape:', error)
  }
}

// Comprehensive event handling
const setupEventHandlers = () => {
  if (!cy) return

  // Node interaction events
  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    const nodeData = node.data()

    // Set selected node data and type
    selectedNodeData.value = nodeData.originalData
    selectedNodeType.value = nodeData.type
    showNodeDialog.value = true

    // Emit custom events for parent component
    emit('nodeSelected', nodeData)
  })

  cy.on('mouseover', 'node', (evt) => {
    const node = evt.target
    const connectedElements = node.connectedEdges().union(node.connectedEdges().connectedNodes())

    // Performance optimization: batch style changes
    cy.startBatch()
    cy.elements().removeClass('highlighted')
    connectedElements.addClass('highlighted')
    node.addClass('highlighted')
    cy.endBatch()

    // Update cursor
    cytoscapeContainer.value.style.cursor = 'pointer'
  })

  cy.on('mouseout', 'node', () => {
    cy.elements().removeClass('highlighted')
    cytoscapeContainer.value.style.cursor = 'default'
  })

  // Graph-level events
  cy.on('zoom', () => {
    // Update minimap if it exists
    if (minimap) {
      updateMinimap()
    }
  })

  cy.on('pan', () => {
    if (minimap) {
      updateMinimap()
    }
  })

  // Double-click to fit
  cy.on('tap', (evt) => {
    if (evt.target === cy && evt.originalEvent.detail === 2) {
      fitGraph()
    }
  })
}

// Minimap functionality
const initMinimap = () => {
  // Implementation would depend on cytoscape-minimap extension
  // This is a placeholder for the concept
  console.log('Minimap initialized')
}

const updateMinimap = () => {
  // Update minimap viewport indicator
  console.log('Minimap updated')
}

const setupZoomOptimization = () => {
  if (!cy) return

  let zoomTimeout
  let isZooming = false

  cy.on('zoom', () => {
    // Enable performance mode during zoom
    if (!isZooming) {
      isZooming = true
      cy.style()
        .selector('node')
        .style('text-opacity', 0.3) // Fade labels during zoom
        .selector('edge')
        .style('opacity', 0.5) // Fade edges during zoom
        .update()
    }

    // Clear existing timeout
    if (zoomTimeout) clearTimeout(zoomTimeout)

    // Restore full quality after zoom ends
    zoomTimeout = setTimeout(() => {
      isZooming = false
      cy.style()
        .selector('node')
        .style('text-opacity', 1)
        .selector('edge')
        .style('opacity', 0.8)
        .update()
    }, 100) // 100ms delay after zoom stops
  })
}

// Adapt to user's zoom behavior instead of forcing sensitivity
const setupAdaptiveZoom = () => {
  if (!cy) return

  const zoom = cy.zoom()

  // Provide zoom controls that work consistently
  const addZoomControls = () => {
    const controlsHtml = `
      <div class="zoom-controls">
        <button class="zoom-btn zoom-in">+</button>
        <button class="zoom-btn zoom-out">−</button>
        <button class="zoom-btn zoom-fit">⌂</button>
      </div>
    `

    cytoscapeContainer.value.insertAdjacentHTML('beforeend', controlsHtml)

    // Consistent zoom behavior regardless of hardware
    cytoscapeContainer.value.querySelector('.zoom-in').onclick = () => {
      cy.zoom(cy.zoom() * 1.5)
      cy.center()
    }

    cytoscapeContainer.value.querySelector('.zoom-out').onclick = () => {
      cy.zoom(cy.zoom() * 0.75)
      cy.center()
    }

    cytoscapeContainer.value.querySelector('.zoom-fit').onclick = () => {
      cy.fit(cy.elements(), 50)
    }
  }

  addZoomControls()
}

// Optimize the updateGraph function with better batching
const updateGraph = async () => {
  if (!cy) return

  try {
    await nextTick()

    // Show loading state
    cytoscapeContainer.value.style.cursor = 'wait'

    const { nodes, edges } = buildGraphData.value

    // More aggressive batching
    cy.startBatch()

    // Remove elements efficiently
    cy.elements().remove()

    // Add elements in chunks for large datasets
    const CHUNK_SIZE = 100
    for (let i = 0; i < nodes.length; i += CHUNK_SIZE) {
      const chunk = nodes.slice(i, i + CHUNK_SIZE)
      cy.add(chunk)

      // Yield to browser occasionally
      if (i % 500 === 0) {
        await new Promise((resolve) => setTimeout(resolve, 0))
      }
    }

    // Add edges in chunks
    for (let i = 0; i < edges.length; i += CHUNK_SIZE) {
      const chunk = edges.slice(i, i + CHUNK_SIZE)
      cy.add(chunk)

      if (i % 500 === 0) {
        await new Promise((resolve) => setTimeout(resolve, 0))
      }
    }

    cy.endBatch()

    // Run layout
    const layout = cy.layout(getLayoutConfig())
    layout.run()

    // Setup performance optimizations
    setupZoomOptimization()
    setupAdaptiveZoom()
    if (nodes.length > 1000) {
      implementViewportCulling()
    }

    cytoscapeContainer.value.style.cursor = 'default'
  } catch (error) {
    console.error('Failed to update graph:', error)
    cytoscapeContainer.value.style.cursor = 'default'
  }
}

// Control functions
const clearSearch = () => {
  searchQuery.value = ''
}

const handleNodeUpdated = () => {
  // Emit event to parent component to refetch data
  emit('graphUpdated')
  // Re-render the graph with updated data
  updateGraph()
}

const fitGraph = () => {
  if (cy) {
    cy.fit(cy.elements(), 50)
  }
}

const centerGraph = () => {
  if (cy) {
    cy.center()
  }
}

const exportGraph = async () => {
  if (cy && props.enableExport) {
    try {
      const blob = await exportToImage(cy, 'png', 2)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `graph-${Date.now()}.png`
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
    }
  }
}

// Lifecycle and watchers
onMounted(async () => {
  await initCytoscape()
})

onUnmounted(() => {
  if (cy) {
    cy.destroy()
  }
})

// Watch for changes with debouncing for better performance
let updateTimeout = null
const DEBOUNCE_TIME = 500
watch(
  [() => props.items, () => props.tags, () => searchQuery.value],
  () => {
    if (updateTimeout) clearTimeout(updateTimeout)
    updateTimeout = setTimeout(() => {
      updateGraph()
    }, DEBOUNCE_TIME) // Longer debounce for better performance
  },
  { deep: true },
)

watch(
  () => selectedLayout.value,
  (newLayout) => {
    if (cy) {
      const layout = cy.layout(getLayoutConfig(newLayout))
      layout.run()
    }
  },
)

// Emits for parent component
const emit = defineEmits(['nodeSelected', 'layoutChanged', 'searchChanged'])

// Expose methods for parent component
defineExpose({
  getCytoscape: () => cy,
  fitToView: fitGraph,
  center: centerGraph,
  export: exportGraph,
  clearSearch,
  getSelectedNode: () => selectedNode.value,
})
</script>

<style scoped>
.graph-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 1200px; /* SET EXPLICIT HEIGHT */
  min-height: 400px;
  max-height: 1200px; /* PREVENT INFINITE GROWTH */
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.graph-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  gap: 16px;
  flex-wrap: wrap;
}

.search-section {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 200px;
}

.search-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: #3498db;
}

.clear-btn {
  padding: 6px 10px;
  background: #ff8979;
  border: none;
  border-radius: 20%;
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
  transition: background-color 0.2s;
}

.clear-btn:hover {
  background: #d24b3d;
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  background: white;
  cursor: pointer;
}

.filter-select:focus {
  outline: 2px solid #3498db;
  outline-offset: 2px;
}

.layout-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.layout-select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.control-btn {
  padding: 8px 16px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.control-btn:hover {
  background: #2980b9;
}

.cytoscape-graph {
  width: 100%;
  height: calc(100% - 60px);
  background: #ffffff;
}

.minimap-container {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 200px;
  height: 150px;
  border: 2px solid #ddd;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(5px);
}

.node-info-panel {
  position: absolute;
  top: 20%;
  left: 20%;
  right: 20%;
  width: 60%;
  height: 60%;
  background: white;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
}

.node-info-panel h4 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 16px;
}

.node-info-panel p {
  margin: 8px 0;
  font-size: 14px;
  color: #666;
}

.close-panel {
  position: absolute;
  top: 8px;
  right: 8px;
}

.close-panel:hover {
  color: #666;
}

/* Responsive design */
@media (max-width: 768px) {
  .graph-controls {
    flex-direction: column;
    gap: 12px;
  }

  .layout-section {
    width: 100%;
    justify-content: center;
  }

  .node-info-panel {
    width: calc(100% - 40px);
    left: 20px;
    right: 20px;
  }
}

/* Loading states */
.graph-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  font-size: 16px;
  color: #666;
}

/* Accessibility improvements */
.control-btn:focus,
.search-input:focus,
.layout-select:focus {
  outline: 2px solid #3498db;
  outline-offset: 2px;
}

/* Dark theme support */
@media (prefers-color-scheme: dark) {
  .graph-controls {
    border-bottom-color: #4a5f7a;
  }

  .cytoscape-graph {
    width: 100%;
    height: 100%;
  }

  .search-input,
  .layout-select {
    border-color: #4a5f7a;
  }

  .node-info-panel {
    border-color: #4a5f7a;
  }
}
.zoom-controls {
  position: absolute;
  top: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 1000;
}

.zoom-btn {
  width: 40px;
  height: 40px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  transition: all 0.2s ease;
  backdrop-filter: blur(5px);
}

.zoom-btn:hover {
  border-color: #3498db;
  transform: translateY(-1px);
}

.zoom-btn:active {
  transform: translateY(0);
}
.graph-content {
  flex: 1; /* FILL REMAINING SPACE */
  display: flex;
  overflow: hidden; /* PREVENT OVERFLOW */
  position: relative;
}
</style>
