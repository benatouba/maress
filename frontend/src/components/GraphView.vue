<template>
  <div class="graph-container">
    <div
      ref="cytoscapeContainer"
      class="cytoscape-graph"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import cytoscape from 'cytoscape'

// Props for data input
const props = defineProps({
  items: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
})

// Template refs
const cytoscapeContainer = ref(null)
let cy = null

// get the initials from a title string
const getInitials = (title) => {
  if (!title) return ''

  // Split by spaces and filter out empty strings
  const words = title.split(' ').filter(word => word.length > 0)

  // Extract first letter of each word and make uppercase
  return words
    .map(word => word.charAt(0).toUpperCase())
    .join('')
    .substring(0, 3) // Limit to 3 initials max to avoid overcrowding
}

// Convert data to cytoscape format
const buildGraphData = () => {
  const nodes = []
  const edges = []

  // Add tag nodes (purple)
  props.tags.forEach((tag) => {
    nodes.push({
      group: 'nodes',
      data: { id: `tag_${tag.id}`, label: tag.name, type: 'tag', originalData: tag },
    })
  })

  // Add item nodes
  props.items.forEach((item) => {
    nodes.push({
      group: 'nodes',
      data: {
        id: `item_${item.id}`,
        label: getInitials(item.title) || "?",
        type: 'item',
        originalData: item,
      },
    })

    // Create edges from items to their tags
    if (item.tags && Array.isArray(item.tags)) {
      item.tags.forEach((tagId) => {
        edges.push({
          group: 'edges',
          data: {
            id: `edge_${item.id}_${tagId}`,
            source: `item_${item.id}`,
            target: `tag_${tagId}`,
          },
        })
      })
    }
  })

  return { nodes, edges }
}

// Initialize cytoscape
const initCytoscape = () => {
  if (!cytoscapeContainer.value) return

  const { nodes, edges } = buildGraphData()

  cy = cytoscape({
    container: cytoscapeContainer.value,

    elements: [...nodes, ...edges],

    style: [
      // Default node style
      {
        selector: 'node',
        style: {
          'background-color': '#6FB1FC',
          label: 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '12px',
          width: '60px',
          height: '60px',
          'border-width': '2px',
          'border-color': '#4A90C2',
        },
      },

      // Tag node style (purple)
      {
        selector: 'node[type="tag"]',
        style: {
          'background-color': '#8E44AD',
          'border-color': '#6C3483',
          shape: 'round-rectangle',
          width: '80px',
          height: '40px',
        },
      },

      // Item node style
      {
        selector: 'node[type="item"]',
        style: { 'background-color': '#3498DB', 'border-color': '#2980B9', shape: 'ellipse' },
      },

      // Edge styles
      {
        selector: 'edge',
        style: {
          width: 2,
          'line-color': '#BDC3C7',
          'target-arrow-color': '#BDC3C7',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
        },
      },

      // Hover effects
      { selector: 'node:hover', style: { 'border-width': '3px', 'border-color': '#E74C3C' } },

      // Selected node style
      {
        selector: 'node:selected',
        style: { 'background-color': '#E67E22', 'border-color': '#D35400', 'border-width': '4px' },
      },
    ],

    layout: { name: 'random', animate: true, animationDuration: 2000, fit: true, padding: 50 },

    // Enable interactions
    zoomingEnabled: true,
    userZoomingEnabled: true,
    panningEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: true,
    selectionType: 'single',
    autoungrabify: false,
    autounselectify: false,
  })

  // Add event listeners
  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    console.log('Node clicked:', node.data())
    // Emit event or handle node selection
  })

  cy.on('mouseover', 'node', (evt) => {
    const node = evt.target
    // Highlight connected edges and nodes
    const connectedElements = node.connectedEdges().union(node.connectedEdges().connectedNodes())
    cy.elements().removeClass('highlighted')
    connectedElements.addClass('highlighted')
    node.addClass('highlighted')
  })

  cy.on('mouseout', 'node', () => {
    cy.elements().removeClass('highlighted')
  })
}

// Update graph when data changes
const updateGraph = async () => {
  if (!cy) return

  await nextTick()
  const { nodes, edges } = buildGraphData()

  // Clear existing elements
  cy.elements().remove()

  // Add new elements
  cy.add([...nodes, ...edges])

  // Re-run layout
  cy.layout({ name: 'cose', animate: true, animationDuration: 800, fit: true }).run()
}

// Lifecycle hooks
onMounted(() => {
  initCytoscape()
})

// Watch for data changes
watch(
  [() => props.items, () => props.tags],
  () => {
    updateGraph()
  },
  { deep: true },
)

// Expose cytoscape instance for parent component access
defineExpose({ getCytoscape: () => cy, fitToView: () => cy?.fit(), center: () => cy?.center() })
</script>

<style scoped>
.graph-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.cytoscape-graph {
  width: 100%;
  height: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
}

/* Highlighted elements during hover */
:deep(.cy-container .highlighted) {
  opacity: 1 !important;
}

:deep(.cy-container .highlighted[opacity]) {
  opacity: 0.3 !important;
}
</style>
