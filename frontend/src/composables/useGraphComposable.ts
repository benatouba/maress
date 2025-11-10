import type { Core } from 'cytoscape'

export interface NodeImportanceMap {
  items: Record<string, number>
  tags: Record<string, number>
}

export interface ClusterResult {
  clusterId: number
  nodeIds: string[]
}

/**
 * Composable for graph visualization utilities
 * Provides helper functions for node styling, export, and analysis
 */
export function useGraphComposable() {
  /**
   * Get node color based on type and color scheme
   * @param type - Node type ('item', 'tag', etc.)
   * @param colorScheme - Color scheme name ('default', 'category', 'importance')
   * @param isBorder - Whether this is for border color
   * @returns Color hex string
   */
  const getNodeColor = (
    type: string,
    colorScheme: string = 'default',
    isBorder: boolean = false
  ): string => {
    if (colorScheme === 'default') {
      const colors: Record<string, string> = {
        item: isBorder ? '#1976D2' : '#2196F3',
        tag: isBorder ? '#388E3C' : '#4CAF50',
        author: isBorder ? '#F57C00' : '#FF9800',
        journal: isBorder ? '#7B1FA2' : '#9C27B0',
        default: isBorder ? '#455A64' : '#607D8B'
      }
      return colors[type] || colors.default
    } else if (colorScheme === 'category') {
      // Color by category/type with more distinct colors
      const colors: Record<string, string> = {
        item: '#E91E63',
        tag: '#00BCD4',
        author: '#FF5722',
        journal: '#673AB7',
        default: '#9E9E9E'
      }
      return colors[type] || colors.default
    } else if (colorScheme === 'importance') {
      // Color by importance (will be overridden per node)
      return '#2196F3'
    }
    return '#607D8B'
  }

  /**
   * Get node size based on type, importance, and size mode
   * @param type - Node type
   * @param importance - Importance score (0-1)
   * @param sizeMode - Sizing mode ('uniform', 'importance', 'connections')
   * @returns Size value
   */
  const getNodeSize = (
    type: string,
    importance: number = 0.5,
    sizeMode: string = 'uniform'
  ): number => {
    const baseSizes: Record<string, number> = {
      item: 30,
      tag: 20,
      author: 25,
      journal: 28,
      default: 22
    }

    const baseSize = baseSizes[type] || baseSizes.default

    if (sizeMode === 'uniform') {
      return baseSize
    } else if (sizeMode === 'importance') {
      // Scale size by importance (0.5x to 2x base size)
      return baseSize * (0.5 + importance * 1.5)
    } else if (sizeMode === 'connections') {
      // Size will be calculated based on degree in the component
      return baseSize
    }

    return baseSize
  }

  /**
   * Export graph to image
   * @param cy - Cytoscape instance
   * @param format - Image format ('png', 'jpg')
   * @param scale - Scale factor for export (1-5)
   * @returns Data URL of the exported image
   */
  const exportToImage = (
    cy: Core,
    format: 'png' | 'jpg' = 'png',
    scale: number = 2
  ): string => {
    if (!cy) {
      console.error('Cytoscape instance not available')
      return ''
    }

    try {
      const options = {
        output: 'blob-promise' as const,
        bg: format === 'jpg' ? '#FFFFFF' : 'transparent',
        full: true,
        scale: Math.min(Math.max(scale, 1), 5), // Clamp between 1 and 5
        maxWidth: 4096,
        maxHeight: 4096
      }

      // Get image as data URL
      const dataUrl = cy.png(options)
      return dataUrl
    } catch (error) {
      console.error('Failed to export graph:', error)
      return ''
    }
  }

  /**
   * Calculate node importance based on connections and centrality
   * @param items - Array of items (papers)
   * @param tags - Array of tags
   * @returns Object with importance scores for items and tags
   */
  const calculateNodeImportance = (
    items: any[],
    tags: any[]
  ): NodeImportanceMap => {
    const itemConnections: Record<string, number> = {}
    const tagConnections: Record<string, number> = {}

    // Count connections for each node
    items.forEach((item) => {
      const itemId = item.id
      itemConnections[itemId] = 0

      if (item.tags && Array.isArray(item.tags)) {
        itemConnections[itemId] += item.tags.length

        item.tags.forEach((tagId: any) => {
          const tid = typeof tagId === 'string' ? tagId : tagId.id || tagId
          tagConnections[tid] = (tagConnections[tid] || 0) + 1
        })
      }

      // Add connections from study sites
      if (item.study_sites && Array.isArray(item.study_sites)) {
        itemConnections[itemId] += item.study_sites.length * 0.5 // Weight study sites less
      }

      // Add connections from authors
      if (item.creators && Array.isArray(item.creators)) {
        itemConnections[itemId] += item.creators.length * 0.3 // Weight authors less
      }
    })

    // Normalize importance scores (0-1)
    const maxItemConnections = Math.max(...Object.values(itemConnections), 1)
    const maxTagConnections = Math.max(...Object.values(tagConnections), 1)

    const itemImportance: Record<string, number> = {}
    const tagImportance: Record<string, number> = {}

    Object.entries(itemConnections).forEach(([itemId, count]) => {
      itemImportance[itemId] = count / maxItemConnections
    })

    Object.entries(tagConnections).forEach(([tagId, count]) => {
      tagImportance[tagId] = count / maxTagConnections
    })

    return {
      items: itemImportance,
      tags: tagImportance
    }
  }

  /**
   * Cluster nodes based on connectivity and shared attributes
   * @param items - Array of items
   * @param tags - Array of tags
   * @returns Array of clusters with node IDs
   */
  const clusterNodes = (items: any[], tags: any[]): ClusterResult[] => {
    const clusters: ClusterResult[] = []
    const nodeToCluster: Record<string, number> = {}
    let nextClusterId = 0

    // Create tag-based clusters
    const tagToItems: Record<string, string[]> = {}

    items.forEach((item) => {
      if (item.tags && Array.isArray(item.tags)) {
        item.tags.forEach((tag: any) => {
          const tagId = typeof tag === 'string' ? tag : tag.id || tag.tag
          if (!tagToItems[tagId]) {
            tagToItems[tagId] = []
          }
          tagToItems[tagId].push(`item-${item.id}`)
        })
      }
    })

    // Group items with shared tags into clusters
    Object.entries(tagToItems).forEach(([tagId, itemIds]) => {
      if (itemIds.length >= 2) {
        // Only cluster if at least 2 items share the tag
        const clusterId = nextClusterId++

        itemIds.forEach((itemId) => {
          if (!nodeToCluster[itemId]) {
            nodeToCluster[itemId] = clusterId
          }
        })

        nodeToCluster[`tag-${tagId}`] = clusterId

        clusters.push({
          clusterId,
          nodeIds: [...itemIds, `tag-${tagId}`]
        })
      }
    })

    // Add unclustered nodes to singleton clusters
    items.forEach((item) => {
      const itemId = `item-${item.id}`
      if (!nodeToCluster[itemId]) {
        const clusterId = nextClusterId++
        nodeToCluster[itemId] = clusterId
        clusters.push({
          clusterId,
          nodeIds: [itemId]
        })
      }
    })

    return clusters
  }

  /**
   * Get color based on importance value
   * @param importance - Importance score (0-1)
   * @returns Color hex string
   */
  const getImportanceColor = (importance: number): string => {
    // Color gradient from light blue (low) to dark blue (high)
    const hue = 210 // Blue
    const saturation = 70
    const lightness = 70 - importance * 30 // 70% to 40%

    return `hsl(${hue}, ${saturation}%, ${lightness}%)`
  }

  /**
   * Get edge color based on edge type
   * @param edgeType - Type of edge ('has-tag', 'cites', 'similar')
   * @returns Color hex string
   */
  const getEdgeColor = (edgeType: string): string => {
    const colors: Record<string, string> = {
      'has-tag': '#90CAF9',
      'cites': '#A5D6A7',
      'similar': '#CE93D8',
      'co-author': '#FFCC80',
      default: '#BDBDBD'
    }
    return colors[edgeType] || colors.default
  }

  /**
   * Get edge width based on strength/weight
   * @param weight - Edge weight (0-1)
   * @returns Width value
   */
  const getEdgeWidth = (weight: number = 1): number => {
    return 1 + weight * 3 // 1px to 4px
  }

  /**
   * Format node label for display
   * @param label - Original label
   * @param maxLength - Maximum length before truncation
   * @returns Formatted label
   */
  const formatNodeLabel = (label: string, maxLength: number = 30): string => {
    if (!label) return 'Untitled'

    if (label.length <= maxLength) {
      return label
    }

    return label.substring(0, maxLength - 3) + '...'
  }

  /**
   * Calculate graph statistics
   * @param cy - Cytoscape instance
   * @returns Object with graph statistics
   */
  const calculateGraphStats = (cy: Core) => {
    if (!cy) {
      return {
        nodeCount: 0,
        edgeCount: 0,
        avgDegree: 0,
        density: 0,
        components: 0
      }
    }

    const nodes = cy.nodes()
    const edges = cy.edges()
    const nodeCount = nodes.length
    const edgeCount = edges.length

    // Calculate average degree
    let totalDegree = 0
    nodes.forEach((node) => {
      totalDegree += node.degree()
    })
    const avgDegree = nodeCount > 0 ? totalDegree / nodeCount : 0

    // Calculate density
    const maxEdges = (nodeCount * (nodeCount - 1)) / 2
    const density = maxEdges > 0 ? edgeCount / maxEdges : 0

    // Count connected components
    const components = cy.elements().components().length

    return {
      nodeCount,
      edgeCount,
      avgDegree: Math.round(avgDegree * 10) / 10,
      density: Math.round(density * 100) / 100,
      components
    }
  }

  return {
    getNodeColor,
    getNodeSize,
    exportToImage,
    calculateNodeImportance,
    clusterNodes,
    getImportanceColor,
    getEdgeColor,
    getEdgeWidth,
    formatNodeLabel,
    calculateGraphStats
  }
}
