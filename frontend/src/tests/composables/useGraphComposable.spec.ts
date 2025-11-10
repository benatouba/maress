import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useGraphComposable } from '@/composables/useGraphComposable'
import type { Core } from 'cytoscape'

describe('useGraphComposable', () => {
  let composable: ReturnType<typeof useGraphComposable>

  beforeEach(() => {
    composable = useGraphComposable()
  })

  describe('getNodeColor', () => {
    it('should return default colors for item type', () => {
      const color = composable.getNodeColor('item', 'default')
      expect(color).toBe('#2196F3')
    })

    it('should return default colors for tag type', () => {
      const color = composable.getNodeColor('tag', 'default')
      expect(color).toBe('#4CAF50')
    })

    it('should return border colors when isBorder is true', () => {
      const color = composable.getNodeColor('item', 'default', true)
      expect(color).toBe('#1976D2')
    })

    it('should return category colors when colorScheme is category', () => {
      const color = composable.getNodeColor('item', 'category')
      expect(color).toBe('#E91E63')
    })

    it('should return importance colors when colorScheme is importance', () => {
      const color = composable.getNodeColor('item', 'importance')
      expect(color).toBe('#2196F3')
    })

    it('should return default color for unknown type', () => {
      const color = composable.getNodeColor('unknown', 'default')
      expect(color).toBe('#607D8B')
    })

    it('should handle all node types', () => {
      const types = ['item', 'tag', 'author', 'journal']
      types.forEach(type => {
        const color = composable.getNodeColor(type, 'default')
        expect(color).toBeTruthy()
        expect(typeof color).toBe('string')
        expect(color).toMatch(/^#[0-9A-F]{6}$/i)
      })
    })
  })

  describe('getNodeSize', () => {
    it('should return base size for uniform mode', () => {
      const size = composable.getNodeSize('item', 0.5, 'uniform')
      expect(size).toBe(30)
    })

    it('should scale size by importance in importance mode', () => {
      const lowImportance = composable.getNodeSize('item', 0, 'importance')
      const midImportance = composable.getNodeSize('item', 0.5, 'importance')
      const highImportance = composable.getNodeSize('item', 1, 'importance')

      expect(lowImportance).toBe(15) // 30 * 0.5
      expect(midImportance).toBe(37.5) // 30 * (0.5 + 0.5 * 1.5)
      expect(highImportance).toBe(60) // 30 * (0.5 + 1 * 1.5)
    })

    it('should return base size for connections mode', () => {
      const size = composable.getNodeSize('tag', 0.5, 'connections')
      expect(size).toBe(20)
    })

    it('should handle different node types', () => {
      const itemSize = composable.getNodeSize('item', 0.5, 'uniform')
      const tagSize = composable.getNodeSize('tag', 0.5, 'uniform')
      const authorSize = composable.getNodeSize('author', 0.5, 'uniform')

      expect(itemSize).toBe(30)
      expect(tagSize).toBe(20)
      expect(authorSize).toBe(25)
    })

    it('should return default size for unknown type', () => {
      const size = composable.getNodeSize('unknown', 0.5, 'uniform')
      expect(size).toBe(22)
    })
  })

  describe('exportToImage', () => {
    it('should return empty string if cy is null', () => {
      const result = composable.exportToImage(null as any)
      expect(result).toBe('')
    })

    it('should call cy.png with correct options', () => {
      const mockPng = vi.fn().mockReturnValue('data:image/png;base64,...')
      const mockCy = {
        png: mockPng
      } as unknown as Core

      const result = composable.exportToImage(mockCy, 'png', 2)

      expect(mockPng).toHaveBeenCalledWith({
        output: 'blob-promise',
        bg: 'transparent',
        full: true,
        scale: 2,
        maxWidth: 4096,
        maxHeight: 4096
      })
      expect(result).toBe('data:image/png;base64,...')
    })

    it('should use white background for jpg format', () => {
      const mockPng = vi.fn().mockReturnValue('data:image/jpg;base64,...')
      const mockCy = {
        png: mockPng
      } as unknown as Core

      composable.exportToImage(mockCy, 'jpg', 2)

      expect(mockPng).toHaveBeenCalledWith(
        expect.objectContaining({
          bg: '#FFFFFF'
        })
      )
    })

    it('should clamp scale between 1 and 5', () => {
      const mockPng = vi.fn().mockReturnValue('data:image/png;base64,...')
      const mockCy = {
        png: mockPng
      } as unknown as Core

      composable.exportToImage(mockCy, 'png', 0)
      expect(mockPng).toHaveBeenCalledWith(expect.objectContaining({ scale: 1 }))

      composable.exportToImage(mockCy, 'png', 10)
      expect(mockPng).toHaveBeenCalledWith(expect.objectContaining({ scale: 5 }))
    })

    it('should handle errors gracefully', () => {
      const mockPng = vi.fn().mockImplementation(() => {
        throw new Error('Export failed')
      })
      const mockCy = {
        png: mockPng
      } as unknown as Core

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const result = composable.exportToImage(mockCy, 'png', 2)

      expect(result).toBe('')
      expect(consoleSpy).toHaveBeenCalledWith('Failed to export graph:', expect.any(Error))

      consoleSpy.mockRestore()
    })
  })

  describe('calculateNodeImportance', () => {
    it('should calculate importance for items and tags', () => {
      const items = [
        {
          id: 'item1',
          tags: ['tag1', 'tag2'],
          study_sites: [],
          creators: []
        },
        {
          id: 'item2',
          tags: ['tag1'],
          study_sites: [],
          creators: []
        }
      ]
      const tags = [
        { id: 'tag1', name: 'Tag 1' },
        { id: 'tag2', name: 'Tag 2' }
      ]

      const result = composable.calculateNodeImportance(items, tags)

      expect(result).toHaveProperty('items')
      expect(result).toHaveProperty('tags')
      expect(result.items['item1']).toBe(1) // Most connections
      expect(result.items['item2']).toBeLessThan(result.items['item1'])
      expect(result.tags['tag1']).toBe(1) // Most connections
      expect(result.tags['tag2']).toBeLessThan(result.tags['tag1'])
    })

    it('should handle items without tags', () => {
      const items = [
        {
          id: 'item1',
          tags: [],
          study_sites: [],
          creators: []
        }
      ]
      const tags: any[] = []

      const result = composable.calculateNodeImportance(items, tags)

      expect(result.items['item1']).toBe(1) // Normalized to 1
      expect(Object.keys(result.tags)).toHaveLength(0)
    })

    it('should weight study sites correctly', () => {
      const items = [
        {
          id: 'item1',
          tags: [],
          study_sites: [{ id: 'site1' }, { id: 'site2' }],
          creators: []
        }
      ]
      const tags: any[] = []

      const result = composable.calculateNodeImportance(items, tags)

      expect(result.items['item1']).toBe(1)
    })

    it('should weight authors correctly', () => {
      const items = [
        {
          id: 'item1',
          tags: [],
          study_sites: [],
          creators: [{ name: 'Author 1' }, { name: 'Author 2' }]
        }
      ]
      const tags: any[] = []

      const result = composable.calculateNodeImportance(items, tags)

      expect(result.items['item1']).toBe(1)
    })

    it('should normalize scores to 0-1 range', () => {
      const items = [
        {
          id: 'item1',
          tags: ['tag1', 'tag2', 'tag3'],
          study_sites: [],
          creators: []
        },
        {
          id: 'item2',
          tags: ['tag1'],
          study_sites: [],
          creators: []
        }
      ]
      const tags = [
        { id: 'tag1', name: 'Tag 1' },
        { id: 'tag2', name: 'Tag 2' },
        { id: 'tag3', name: 'Tag 3' }
      ]

      const result = composable.calculateNodeImportance(items, tags)

      Object.values(result.items).forEach(importance => {
        expect(importance).toBeGreaterThanOrEqual(0)
        expect(importance).toBeLessThanOrEqual(1)
      })

      Object.values(result.tags).forEach(importance => {
        expect(importance).toBeGreaterThanOrEqual(0)
        expect(importance).toBeLessThanOrEqual(1)
      })
    })

    it('should handle tag objects with different structures', () => {
      const items = [
        {
          id: 'item1',
          tags: ['tag1', { id: 'tag2' }, { tag: 'tag3' }],
          study_sites: [],
          creators: []
        }
      ]
      const tags = [
        { id: 'tag1', name: 'Tag 1' },
        { id: 'tag2', name: 'Tag 2' },
        { id: 'tag3', name: 'Tag 3' }
      ]

      const result = composable.calculateNodeImportance(items, tags)

      expect(result.tags['tag1']).toBeTruthy()
      expect(result.tags['tag2']).toBeTruthy()
      expect(result.tags['tag3']).toBeTruthy()
    })
  })

  describe('clusterNodes', () => {
    it('should create clusters based on shared tags', () => {
      const items = [
        { id: 'item1', tags: ['tag1', 'tag2'] },
        { id: 'item2', tags: ['tag1', 'tag2'] },
        { id: 'item3', tags: ['tag3'] }
      ]
      const tags = [
        { id: 'tag1', name: 'Tag 1' },
        { id: 'tag2', name: 'Tag 2' },
        { id: 'tag3', name: 'Tag 3' }
      ]

      const result = composable.clusterNodes(items, tags)

      expect(result.length).toBeGreaterThan(0)
      expect(result[0]).toHaveProperty('clusterId')
      expect(result[0]).toHaveProperty('nodeIds')
      expect(Array.isArray(result[0].nodeIds)).toBe(true)
    })

    it('should only cluster items with at least 2 shared tags', () => {
      const items = [
        { id: 'item1', tags: ['tag1'] },
        { id: 'item2', tags: ['tag2'] }
      ]
      const tags = [
        { id: 'tag1', name: 'Tag 1' },
        { id: 'tag2', name: 'Tag 2' }
      ]

      const result = composable.clusterNodes(items, tags)

      // Should create singleton clusters for isolated items
      expect(result.length).toBeGreaterThan(0)
    })

    it('should handle items without tags', () => {
      const items = [
        { id: 'item1', tags: [] },
        { id: 'item2', tags: null }
      ]
      const tags: any[] = []

      const result = composable.clusterNodes(items, tags)

      // Should create singleton clusters
      expect(result.length).toBeGreaterThan(0)
    })

    it('should assign unique cluster IDs', () => {
      const items = [
        { id: 'item1', tags: ['tag1'] },
        { id: 'item2', tags: ['tag1'] },
        { id: 'item3', tags: ['tag2'] },
        { id: 'item4', tags: ['tag2'] }
      ]
      const tags = [
        { id: 'tag1', name: 'Tag 1' },
        { id: 'tag2', name: 'Tag 2' }
      ]

      const result = composable.clusterNodes(items, tags)

      const clusterIds = result.map(c => c.clusterId)
      const uniqueIds = new Set(clusterIds)
      expect(clusterIds.length).toBe(uniqueIds.size)
    })

    it('should include tag node in cluster', () => {
      const items = [
        { id: 'item1', tags: ['tag1'] },
        { id: 'item2', tags: ['tag1'] }
      ]
      const tags = [{ id: 'tag1', name: 'Tag 1' }]

      const result = composable.clusterNodes(items, tags)

      const cluster = result.find(c => c.nodeIds.includes('tag-tag1'))
      expect(cluster).toBeTruthy()
      expect(cluster!.nodeIds).toContain('item-item1')
      expect(cluster!.nodeIds).toContain('item-item2')
    })
  })

  describe('getImportanceColor', () => {
    it('should return color in HSL format', () => {
      const color = composable.getImportanceColor(0.5)
      expect(color).toMatch(/^hsl\(\d+,\s*\d+%,\s*\d+%\)$/)
    })

    it('should return darker color for higher importance', () => {
      const lowImportance = composable.getImportanceColor(0.2)
      const highImportance = composable.getImportanceColor(0.8)

      // Extract lightness values
      const lowLightness = parseInt(lowImportance.match(/(\d+)%\)$/)?.[1] || '0')
      const highLightness = parseInt(highImportance.match(/(\d+)%\)$/)?.[1] || '0')

      expect(lowLightness).toBeGreaterThan(highLightness)
    })

    it('should handle edge cases', () => {
      const minColor = composable.getImportanceColor(0)
      const maxColor = composable.getImportanceColor(1)

      expect(minColor).toBeTruthy()
      expect(maxColor).toBeTruthy()
    })
  })

  describe('getEdgeColor', () => {
    it('should return correct color for has-tag edges', () => {
      const color = composable.getEdgeColor('has-tag')
      expect(color).toBe('#90CAF9')
    })

    it('should return correct color for cites edges', () => {
      const color = composable.getEdgeColor('cites')
      expect(color).toBe('#A5D6A7')
    })

    it('should return correct color for similar edges', () => {
      const color = composable.getEdgeColor('similar')
      expect(color).toBe('#CE93D8')
    })

    it('should return default color for unknown edge type', () => {
      const color = composable.getEdgeColor('unknown')
      expect(color).toBe('#BDBDBD')
    })

    it('should handle all edge types', () => {
      const types = ['has-tag', 'cites', 'similar', 'co-author']
      types.forEach(type => {
        const color = composable.getEdgeColor(type)
        expect(color).toBeTruthy()
        expect(typeof color).toBe('string')
        expect(color).toMatch(/^#[0-9A-F]{6}$/i)
      })
    })
  })

  describe('getEdgeWidth', () => {
    it('should return minimum width for weight 0', () => {
      const width = composable.getEdgeWidth(0)
      expect(width).toBe(1)
    })

    it('should return maximum width for weight 1', () => {
      const width = composable.getEdgeWidth(1)
      expect(width).toBe(4)
    })

    it('should scale width linearly with weight', () => {
      const lowWeight = composable.getEdgeWidth(0.25)
      const midWeight = composable.getEdgeWidth(0.5)
      const highWeight = composable.getEdgeWidth(0.75)

      expect(lowWeight).toBe(1.75)
      expect(midWeight).toBe(2.5)
      expect(highWeight).toBe(3.25)
    })

    it('should use default weight of 1', () => {
      const width = composable.getEdgeWidth()
      expect(width).toBe(4)
    })
  })

  describe('formatNodeLabel', () => {
    it('should return label as-is if shorter than maxLength', () => {
      const label = composable.formatNodeLabel('Short label', 30)
      expect(label).toBe('Short label')
    })

    it('should truncate long labels', () => {
      const longLabel = 'This is a very long label that should be truncated'
      const label = composable.formatNodeLabel(longLabel, 30)
      expect(label).toBe('This is a very long label t...')
      expect(label.length).toBe(30)
    })

    it('should return "Untitled" for empty label', () => {
      const label = composable.formatNodeLabel('', 30)
      expect(label).toBe('Untitled')
    })

    it('should return "Untitled" for null label', () => {
      const label = composable.formatNodeLabel(null as any, 30)
      expect(label).toBe('Untitled')
    })

    it('should use default maxLength of 30', () => {
      const longLabel = 'This is a very long label that should be truncated to thirty characters'
      const label = composable.formatNodeLabel(longLabel)
      expect(label.length).toBe(30)
    })
  })

  describe('calculateGraphStats', () => {
    it('should return zero stats for null cy', () => {
      const stats = composable.calculateGraphStats(null as any)

      expect(stats.nodeCount).toBe(0)
      expect(stats.edgeCount).toBe(0)
      expect(stats.avgDegree).toBe(0)
      expect(stats.density).toBe(0)
      expect(stats.components).toBe(0)
    })

    it('should calculate correct stats for graph', () => {
      const mockNodes = [
        { degree: () => 2 },
        { degree: () => 3 },
        { degree: () => 1 }
      ]
      const mockEdges = [{}, {}]

      const mockCy = {
        nodes: () => ({ length: 3, forEach: (fn: any) => mockNodes.forEach(fn) }),
        edges: () => ({ length: 2 }),
        elements: () => ({
          components: () => ({ length: 1 })
        })
      } as unknown as Core

      const stats = composable.calculateGraphStats(mockCy)

      expect(stats.nodeCount).toBe(3)
      expect(stats.edgeCount).toBe(2)
      expect(stats.avgDegree).toBeCloseTo(2, 1)
      expect(stats.density).toBeCloseTo(0.67, 2)
      expect(stats.components).toBe(1)
    })

    it('should handle empty graph', () => {
      const mockCy = {
        nodes: () => ({ length: 0, forEach: () => {} }),
        edges: () => ({ length: 0 }),
        elements: () => ({
          components: () => ({ length: 0 })
        })
      } as unknown as Core

      const stats = composable.calculateGraphStats(mockCy)

      expect(stats.nodeCount).toBe(0)
      expect(stats.edgeCount).toBe(0)
      expect(stats.avgDegree).toBe(0)
      expect(stats.density).toBe(0)
    })

    it('should round avgDegree and density', () => {
      const mockNodes = [
        { degree: () => 2 },
        { degree: () => 3 }
      ]

      const mockCy = {
        nodes: () => ({ length: 2, forEach: (fn: any) => mockNodes.forEach(fn) }),
        edges: () => ({ length: 1 }),
        elements: () => ({
          components: () => ({ length: 1 })
        })
      } as unknown as Core

      const stats = composable.calculateGraphStats(mockCy)

      expect(stats.avgDegree).toBe(2.5)
      expect(stats.density).toBe(1)
    })
  })
})
