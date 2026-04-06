import { ref, computed } from 'vue'
import type { MapPoint } from '@/stores/studySites'

const MAX_CLUSTER_SELECTION_ITEMS = 8

export function useMapInteractions() {
  const boxZoomActive = ref(false)
  const repositioningSiteId = ref<string | null>(null)
  const repositioningSiteName = ref<string | null>(null)

  // Cluster selection popover
  const clusterSelectionSites = ref<MapPoint[]>([])
  const clusterSelectionPosition = ref<{ x: number; y: number } | null>(null)

  const clusterSelectionVisible = computed(() =>
    clusterSelectionSites.value.length > 0 && clusterSelectionPosition.value !== null,
  )

  const sortedClusterSelectionSites = computed(() => {
    return [...clusterSelectionSites.value].sort((a, b) => {
      if (a.is_manual !== b.is_manual) return a.is_manual ? -1 : 1
      const aName = (a.name || '').trim().toLowerCase()
      const bName = (b.name || '').trim().toLowerCase()
      if (aName !== bName) return aName.localeCompare(bName)
      return (a.item_title || '').localeCompare(b.item_title || '')
    })
  })

  const visibleClusterSelectionSites = computed(() =>
    sortedClusterSelectionSites.value.slice(0, MAX_CLUSTER_SELECTION_ITEMS),
  )

  const clusterSelectionHiddenCount = computed(() =>
    Math.max(0, sortedClusterSelectionSites.value.length - MAX_CLUSTER_SELECTION_ITEMS),
  )

  const clusterSelectionStyle = computed(() => {
    if (!clusterSelectionPosition.value) return {}
    return {
      left: `${clusterSelectionPosition.value.x}px`,
      top: `${clusterSelectionPosition.value.y}px`,
    }
  })

  const hideClusterSelection = () => {
    clusterSelectionSites.value = []
    clusterSelectionPosition.value = null
  }

  const isSameLocationCluster = (points: MapPoint[]) => {
    if (points.length <= 1) return false
    const first = points[0]
    const epsilon = 1e-9
    return points.every(
      (point) =>
        Math.abs(point.latitude - first.latitude) <= epsilon
        && Math.abs(point.longitude - first.longitude) <= epsilon,
    )
  }

  const showClusterSelection = (
    points: MapPoint[],
    pixel: [number, number],
    containerWidth: number,
    containerHeight: number,
  ) => {
    clusterSelectionSites.value = points
    const offsetX = 14
    const offsetY = -8
    const fallbackWidth = 260
    const fallbackHeight = 220
    const x = Math.max(8, Math.min(pixel[0] + offsetX, containerWidth - fallbackWidth - 8))
    const y = Math.max(8, Math.min(pixel[1] + offsetY, containerHeight - fallbackHeight - 8))
    clusterSelectionPosition.value = { x, y }
  }

  const startRepositionMode = (site: MapPoint) => {
    repositioningSiteId.value = site.id
    repositioningSiteName.value = site.name || 'Unnamed site'
  }

  const clearReposition = () => {
    repositioningSiteId.value = null
    repositioningSiteName.value = null
  }

  return {
    boxZoomActive,
    repositioningSiteId,
    repositioningSiteName,
    clusterSelectionVisible,
    visibleClusterSelectionSites,
    clusterSelectionHiddenCount,
    clusterSelectionStyle,
    hideClusterSelection,
    isSameLocationCluster,
    showClusterSelection,
    startRepositionMode,
    clearReposition,
  }
}
