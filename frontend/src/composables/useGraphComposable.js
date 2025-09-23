import { ref } from 'vue'

export function useGraphComposable() {
  // Color schemes
  const colorSchemes = {
    default: {
      tag: '#8E44AD',
      tagBorder: '#6C3483',
      item: '#3498DB',
      itemBorder: '#2980B9'
    },
    vibrant: {
      tag: '#E91E63',
      tagBorder: '#C2185B',
      item: '#FF9800',
      itemBorder: '#F57C00'
    },
    minimal: {
      tag: '#95A5A6',
      tagBorder: '#7F8C8D',
      item: '#34495E',
      itemBorder: '#2C3E50'
    }
  }

  const getNodeColor = (type, scheme = 'default', isBorder = false) => {
    const colors = colorSchemes[scheme] || colorSchemes.default
    const suffix = isBorder ? 'Border' : ''
    return colors[`${type}${suffix}`] || colors[`item${suffix}`]
  }

  const getNodeSize = (type, importance = 0, sizeMode = 'uniform') => {
    const baseSizes = { tag: 40, item: 30 }
    const baseSize = baseSizes[type] || 30

    if (sizeMode === 'importance') {
      return `${Math.max(20, Math.min(80, baseSize + importance * 10))}px`
    }

    return `${baseSize}px`
  }

  const calculateNodeImportance = (items, tags) => {
    const tagConnections = {}
    const itemConnections = {}

    // Count connections for each tag
    tags.forEach(tag => {
      tagConnections[tag.id] = 0
    })

    items.forEach(item => {
      itemConnections[item.id] = item.tags?.length || 0

      if (item.tags) {
        item.tags.forEach(tagId => {
          if (tagConnections[tagId] !== undefined) {
            tagConnections[tagId]++
          }
        })
      }
    })

    // Normalize to 0-1 scale
    const maxTagConnections = Math.max(...Object.values(tagConnections), 1)
    const maxItemConnections = Math.max(...Object.values(itemConnections), 1)

    return {
      tags: Object.fromEntries(
        Object.entries(tagConnections).map(([id, count]) => [
          id, count / maxTagConnections
        ])
      ),
      items: Object.fromEntries(
        Object.entries(itemConnections).map(([id, count]) => [
          id, count / maxItemConnections
        ])
      )
    }
  }

  const exportToImage = async (cy, format = 'png', scale = 2) => {
    if (!cy) throw new Error('Cytoscape instance not available')

    const options = {
      output: 'blob',
      format,
      bg: 'white',
      full: true,
      scale
    }

    return cy.png(options)
  }

  const clusterNodes = (nodes, edges, algorithm = 'louvain') => {
    // Placeholder for clustering implementation
    // Would integrate with community detection algorithms
    console.log(`Clustering ${nodes.length} nodes using ${algorithm}`)
    return { clusters: [], modularity: 0 }
  }

  return {
    getNodeColor,
    getNodeSize,
    calculateNodeImportance,
    exportToImage,
    clusterNodes
  }
}

