<template>
  <div class="study-site-map">
    <div
      ref="mapContainer"
      class="map-container"></div>

    <div
      v-if="clusterSelectionVisible"
      class="cluster-selection-popover"
      :style="clusterSelectionStyle"
      @click.stop>
      <div class="cluster-selection-title">Select study site</div>
      <ul class="cluster-selection-list">
        <li
          v-for="site in visibleClusterSelectionSites"
          :key="site.id">
          <button
            class="cluster-selection-item"
            type="button"
            @click.stop="selectClusterSite(site)">
            <span class="cluster-selection-name">{{ site.name || 'Unnamed site' }}</span>
            <span class="cluster-selection-meta">{{ site.item_title || 'Unknown item' }}</span>
          </button>
        </li>
        <li
          v-if="clusterSelectionHiddenCount > 0"
          class="cluster-selection-more">
          +{{ clusterSelectionHiddenCount }} more sites
        </li>
      </ul>
    </div>

    <!-- Map loading indicator -->
    <v-overlay
      :model-value="loading"
      contained
      class="align-center justify-center">
      <v-progress-circular
        indeterminate
        size="64"
        color="primary"></v-progress-circular>
    </v-overlay>

    <!-- Map controls -->
    <div class="map-controls">
        <v-card elevation="1">
          <v-card-text>
            <div class="location-search">
              <input
                v-model="locationQuery"
                class="location-search-input"
                type="text"
                placeholder="Search location..."
                aria-label="Search location"
                @input="handleLocationSearchInput"
                @keydown="handleLocationSearchKeydown" />
              <button
                v-if="locationQuery"
                class="location-search-clear"
                type="button"
                aria-label="Clear search"
                @click="clearLocationSearch(true)">
                ×
              </button>
              <div
                v-if="searching"
                class="location-search-status">
                Searching...
              </div>
              <div
                v-else-if="searchError"
                class="location-search-status error">
                {{ searchError }}
              </div>
              <ul
                v-else-if="searchResults.length > 0"
                class="location-search-results"
                role="listbox"
                aria-label="Location search results">
                <li
                  v-for="(result, index) in searchResults"
                  :key="result.id">
                  <button
                    class="location-search-result"
                    :class="{ active: index === highlightedSearchResultIndex }"
                    type="button"
                    @click="selectLocationResult(result)">
                    {{ result.label }}
                  </button>
                </li>
              </ul>
            </div>

            <v-btn
              @click="fitToMarkers"
              size="small"
              variant="text"
              prepend-icon="mdi-fit-to-page-outline">
            Fit All
          </v-btn>
          <v-btn
            @click="resetView"
            size="small"
            variant="text"
            prepend-icon="mdi-restore">
            Reset
          </v-btn>
          <v-btn
            @click="toggleBoxZoom"
            size="small"
            :variant="boxZoomActive ? 'tonal' : 'text'"
            :color="boxZoomActive ? 'primary' : undefined"
            prepend-icon="mdi-selection-drag">
            Box Zoom
          </v-btn>
        </v-card-text>
      </v-card>
    </div>

    <!-- Map statistics -->
    <div class="map-stats">
      <v-card elevation="1">
        <v-card-text class="pa-3">
          <div class="d-flex gap-4">
            <div class="stat-item">
              <div class="stat-value">{{ totalSites }}</div>
              <div class="stat-label">Total Sites</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-success">{{ manualCount }}</div>
              <div class="stat-label">Manual</div>
            </div>
            <div class="stat-item">
              <div class="stat-value text-info">{{ automaticCount }}</div>
              <div class="stat-label">Automatic</div>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>

    <!-- Edit Dialog -->
    <StudySiteEditDialog
      v-if="authStore.isAuthenticated"
      v-model="editDialogOpen"
      :study-site="selectedSite"
      @saved="handleSiteSaved"
      @deleted="handleSiteDeleted"
      @reposition="startRepositionMode"
      />

    <!-- Create Dialog -->
    <StudySiteCreateDialog
      v-if="authStore.isAuthenticated"
      v-model="createDialogOpen"
      :item-id="createItemId"
      :coordinates="createCoordinates"
      @created="handleSiteCreated" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick, type PropType } from 'vue'
import { storeToRefs } from 'pinia'
import { Map, View } from 'ol'
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer'
import { OSM, Vector as VectorSource, Cluster } from 'ol/source'
import { Feature } from 'ol'
import { Point } from 'ol/geom'
import { fromLonLat, toLonLat, transformExtent } from 'ol/proj'
import { Style, Circle, Fill, Stroke, Text } from 'ol/style'
import { boundingExtent } from 'ol/extent'
import { DragBox, DragZoom, DragPan } from 'ol/interaction'
import { shiftKeyOnly } from 'ol/events/condition'
import GeoJSON from 'ol/format/GeoJSON'
import { useStudySitesStore, type MapPoint } from '../../stores/studySites'
import logger from '@/utils/logger'
import { useRegionsStore, type Region } from '../../stores/regions'
import { useAuthStore } from '../../stores/auth'
import type { GISBufferedFeature } from '../../stores/gis'
import { searchLocations, type GeocodeResult } from '@/services/mapService'
import StudySiteEditDialog from './StudySiteEditDialog.vue'
import StudySiteCreateDialog from './StudySiteCreateDialog.vue'

const props = defineProps({
  initialCenter: {
    type: Array as unknown as PropType<[number, number]>,
    default: () => [0, 20], // [lon, lat]
  },
  initialZoom: { type: Number, default: 2 },
  sites: {
    type: Array as () => MapPoint[],
    default: null,
  },
  regions: {
    type: Array as () => Region[],
    default: () => [],
  },
  bufferFeatures: {
    type: Array as () => GISBufferedFeature[],
    default: () => [],
  },
})

const emit = defineEmits(['site-selected', 'map-ready', 'viewport-changed', 'region-selected'])

// Store
const studySitesStore = useStudySitesStore()
const authStore = useAuthStore()
const { mapPoints: allMapPoints, loading } = storeToRefs(studySitesStore)

// Use filtered sites if provided, otherwise use all from store
const mapPoints = computed(() => props.sites || allMapPoints.value)

// Map refs
const mapContainer = ref<HTMLDivElement | null>(null)
const map = ref<Map | null>(null)
const mapInitialized = ref(false)
const vectorSource = ref<any>(null)
const clusterSource = ref<any>(null)
const clusterLayer = ref<any>(null)
const resizeObserver = ref<ResizeObserver | null>(null)
const viewportEmitTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const boxZoomActive = ref(false)
const dragBoxInteraction = ref<any>(null)
const dragPanInteraction = ref<any>(null)
const regionSource = ref<any>(null)
const regionLayer = ref<any>(null)
const analysisSource = ref<any>(null)
const analysisLayer = ref<any>(null)
const searchPinSource = ref<any>(null)
const searchPinLayer = ref<any>(null)
const geojsonFormat = new GeoJSON()

const emitViewportChanged = () => {
  if (!map.value) return

  const size = map.value.getSize()
  if (!size) return

  const extent3857 = map.value.getView().calculateExtent(size)
  const [minLon, minLat, maxLon, maxLat] = transformExtent(extent3857, 'EPSG:3857', 'EPSG:4326')

  emit('viewport-changed', {
    minLon: Math.max(-180, minLon),
    minLat: Math.max(-90, minLat),
    maxLon: Math.min(180, maxLon),
    maxLat: Math.min(90, maxLat),
  })
}

const scheduleViewportEmit = () => {
  if (viewportEmitTimer.value) {
    clearTimeout(viewportEmitTimer.value)
  }
  viewportEmitTimer.value = setTimeout(() => {
    emitViewportChanged()
    viewportEmitTimer.value = null
  }, 120)
}

const handleWindowResize = () => {
  if (!mapInitialized.value) {
    initMap()
  }
  updateMapSize()
  scheduleViewportEmit()
}

const setBoxZoomState = (active: boolean) => {
  if (!map.value && active) return

  boxZoomActive.value = active
  const target = map.value?.getTargetElement() as HTMLElement | undefined
  if (target) {
    target.style.cursor = active ? 'crosshair' : ''
  }
  if (dragPanInteraction.value) {
    dragPanInteraction.value.setActive(!active)
  }
}

const handleWindowKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && clusterSelectionVisible.value) {
    hideClusterSelection()
    return
  }

  if (event.key === 'Escape' && boxZoomActive.value) {
    setBoxZoomState(false)
  }
}

// Dialog state
const editDialogOpen = ref(false)
const createDialogOpen = ref(false)
const selectedSite = ref<MapPoint | null>(null)
const createItemId = ref<string | null>(null)
const createCoordinates = ref<[number, number] | null>(null)
const repositioningSiteId = ref<string | null>(null)
const repositioningSiteName = ref<string | null>(null)
const clusterSelectionSites = ref<MapPoint[]>([])
const clusterSelectionPosition = ref<{ x: number; y: number } | null>(null)
const locationQuery = ref('')
const searchResults = ref<GeocodeResult[]>([])
const searching = ref(false)
const searchError = ref('')
const locationSearchDebounce = ref<ReturnType<typeof setTimeout> | null>(null)
const locationSearchAbortController = ref<AbortController | null>(null)
const highlightedSearchResultIndex = ref(-1)

// Computed
const totalSites = computed(() => mapPoints.value.length)
const manualCount = computed(() => mapPoints.value.filter((s) => s.is_manual).length)
const automaticCount = computed(() => mapPoints.value.filter((s) => !s.is_manual).length)
const MAX_CLUSTER_SELECTION_ITEMS = 8
const clusterSelectionVisible = computed(() =>
  clusterSelectionSites.value.length > 0 && clusterSelectionPosition.value !== null,
)
const sortedClusterSelectionSites = computed(() => {
  return [...clusterSelectionSites.value].sort((a, b) => {
    if (a.is_manual !== b.is_manual) {
      return a.is_manual ? -1 : 1
    }

    const aName = (a.name || '').trim().toLowerCase()
    const bName = (b.name || '').trim().toLowerCase()

    if (aName !== bName) {
      return aName.localeCompare(bName)
    }

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
  if (!clusterSelectionPosition.value) {
    return {}
  }

  return {
    left: `${clusterSelectionPosition.value.x}px`,
    top: `${clusterSelectionPosition.value.y}px`,
  }
})

// Style cache to avoid creating new Style objects on every render
const styleCache: Record<string, Style> = {}

/**
 * Create cluster style: single marker or count badge
 */
const clusterStyleFunction = (feature: Feature): Style => {
  const clusterFeatures = feature.get('features') as Feature[]
  const size = clusterFeatures.length

  if (size === 1) {
    // Single point — use manual/auto color
    const point = clusterFeatures[0].get('mapPoint') as MapPoint
    const color = point.is_manual ? '#4CAF50' : '#2196F3'
    const key = `single-${color}`
    if (!styleCache[key]) {
      styleCache[key] = new Style({
        image: new Circle({
          radius: 6,
          fill: new Fill({ color }),
          stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
        }),
      })
    }
    return styleCache[key]
  }

  // Cluster badge
  const key = `cluster-${size}`
  if (!styleCache[key]) {
    const radius = Math.min(8 + Math.log2(size) * 4, 24)
    styleCache[key] = new Style({
      image: new Circle({
        radius,
        fill: new Fill({ color: 'rgba(33, 150, 243, 0.7)' }),
        stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
      }),
      text: new Text({
        text: size.toString(),
        fill: new Fill({ color: '#FFFFFF' }),
        font: 'bold 12px sans-serif',
      }),
    })
  }
  return styleCache[key]
}

/**
 * Initialize the OpenLayers map
 */
const initMap = () => {
  if (!mapContainer.value || mapInitialized.value) return

  const { clientWidth, clientHeight } = mapContainer.value
  if (clientWidth === 0 || clientHeight === 0) return

  // Create vector source for individual point features
  vectorSource.value = new VectorSource()

  // Wrap in a Cluster source
  clusterSource.value = new Cluster({
    distance: 40, // px
    minDistance: 20,
    source: vectorSource.value,
  })

  // Cluster layer
  clusterLayer.value = new VectorLayer({
    source: clusterSource.value,
    style: clusterStyleFunction as any,
  })

  // Region polygon layer (rendered between tiles and markers)
  regionSource.value = new VectorSource()
  regionLayer.value = new VectorLayer({
    source: regionSource.value,
    style: new Style({
      fill: new Fill({ color: 'rgba(255, 152, 0, 0.1)' }),
      stroke: new Stroke({ color: '#FF9800', width: 2 }),
    }),
  })

  // Analysis result layer (rendered above regions)
  analysisSource.value = new VectorSource()
  analysisLayer.value = new VectorLayer({
    source: analysisSource.value,
    style: new Style({
      fill: new Fill({ color: 'rgba(233, 30, 99, 0.15)' }),
      stroke: new Stroke({ color: '#E91E63', width: 2 }),
    }),
  })

  // Search pin layer
  searchPinSource.value = new VectorSource()
  searchPinLayer.value = new VectorLayer({
    source: searchPinSource.value,
    style: new Style({
      image: new Circle({
        radius: 8,
        fill: new Fill({ color: '#EF5350' }),
        stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
      }),
    }),
  })

  // Create map — layer order: tiles, regions, analysis, clusters
  map.value = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({ source: new OSM() }),
      regionLayer.value,
      analysisLayer.value,
      clusterLayer.value,
      searchPinLayer.value,
    ],
    view: new View({ center: fromLonLat(props.initialCenter), zoom: props.initialZoom }),
  })

  // Click handler — works for both clusters and single points
  map.value.on('click', (event) => {
    if (boxZoomActive.value) return // Ignore clicks during box zoom
    hideClusterSelection()

    const feature = map.value?.forEachFeatureAtPixel(event.pixel, (f) => f) as Feature | undefined

    if (!feature) {
      // Empty area click → create dialog
      const coords = toLonLat(event.coordinate)
      handleMapClick(coords as [number, number])
      return
    }

    const clusterFeatures = feature.get('features') as Feature[] | undefined
    if (!clusterFeatures) {
      // Could be a region polygon click
      const regionId = feature.get('regionId') as string | undefined
      if (regionId) {
        emit('region-selected', regionId)
      }
      return
    }

    if (clusterFeatures.length === 1) {
      // Single point — open edit dialog
      const point = clusterFeatures[0].get('mapPoint') as MapPoint
      handleMarkerClick(point)
    } else {
      const points = clusterFeatures
        .map((f) => f.get('mapPoint') as MapPoint | undefined)
        .filter((point): point is MapPoint => !!point)

      if (isSameLocationCluster(points)) {
        showClusterSelection(points, event.pixel as [number, number])
        return
      }

      // Multi-point cluster — zoom to its extent
      const extent = boundingExtent(
        clusterFeatures.map((f) => (f.getGeometry() as Point).getCoordinates()),
      )
      map.value?.getView().fit(extent, {
        padding: [80, 80, 80, 80],
        maxZoom: 16,
        duration: 500,
      })
    }
  })

  // Pointer cursor on hover over features
  map.value.on('pointermove', (event) => {
    if (boxZoomActive.value) return // Keep crosshair cursor during box zoom
    const hit = map.value?.hasFeatureAtPixel(event.pixel)
    const target = map.value?.getTargetElement()
    if (target) {
      ;(target as HTMLElement).style.cursor = hit ? 'pointer' : ''
    }
  })

  map.value.on('moveend', () => {
    hideClusterSelection()
    scheduleViewportEmit()
  })

  // Remove default DragZoom to avoid conflict with our DragBox
  map.value.getInteractions().forEach((interaction) => {
    if (interaction instanceof DragZoom) {
      map.value!.removeInteraction(interaction)
    }
    if (interaction instanceof DragPan) {
      dragPanInteraction.value = interaction
    }
  })

  // Box zoom interaction — fires on button toggle OR shift+drag
  dragBoxInteraction.value = new DragBox({
    condition: (event) => boxZoomActive.value || shiftKeyOnly(event),
  })

  dragBoxInteraction.value.on('boxend', () => {
    const extent = dragBoxInteraction.value!.getGeometry().getExtent()
    map.value?.getView().fit(extent, { duration: 500 })
    // Only deactivate button mode if it was button-triggered
    if (boxZoomActive.value) {
      setBoxZoomState(false)
    }
  })

  dragBoxInteraction.value.on('boxcancel', () => {
    if (boxZoomActive.value) {
      setBoxZoomState(false)
    }
  })

  map.value.addInteraction(dragBoxInteraction.value)

  emit('map-ready', map.value)
  mapInitialized.value = true

  // Populate features
  updateMarkers()
  updateRegions()
  updateAnalysisFeatures()
  scheduleViewportEmit()
}

/**
 * Ensure OpenLayers recomputes its viewport size after layout changes
 */
const updateMapSize = () => {
  if (!mapInitialized.value || !map.value || !mapContainer.value) return
  const { clientWidth, clientHeight } = mapContainer.value
  if (clientWidth > 0 && clientHeight > 0) {
    map.value.updateSize()
    scheduleViewportEmit()
  }
}

/**
 * Update markers on the map based on map points
 */
const updateMarkers = () => {
  if (!vectorSource.value) return

  vectorSource.value.clear()

  // Clear style cache when data changes
  Object.keys(styleCache).forEach((key) => delete styleCache[key])

  const features: Feature[] = []
  mapPoints.value.forEach((point) => {
    if (point.latitude == null || point.longitude == null) return

    features.push(new Feature({
      geometry: new Point(fromLonLat([point.longitude, point.latitude])),
      mapPoint: point,
    }))
  })

  if (features.length > 0) {
    vectorSource.value.addFeatures(features)
  }
}

/**
 * Update region polygons on the map
 */
const updateRegions = () => {
  if (!regionSource.value) return
  regionSource.value.clear()

  props.regions.forEach((region) => {
    if (!region.geojson) return

    const featureObj = {
      type: 'Feature' as const,
      geometry: region.geojson,
      properties: { regionId: region.id, name: region.name },
    }

    const features = geojsonFormat.readFeatures(featureObj, {
      dataProjection: 'EPSG:4326',
      featureProjection: 'EPSG:3857',
    })

    features.forEach((f) => {
      f.set('regionId', region.id)
      f.set('regionName', region.name)
    })

    regionSource.value!.addFeatures(features)
  })
}

/**
 * Update analysis result geometries (e.g. buffer output)
 */
const updateAnalysisFeatures = () => {
  if (!analysisSource.value) return
  analysisSource.value.clear()

  props.bufferFeatures.forEach((bufferFeature) => {
    if (!bufferFeature.geometry) return

    const featureObj = {
      type: 'Feature' as const,
      geometry: bufferFeature.geometry,
      properties: { sourceId: bufferFeature.source_id },
    }

    const features = geojsonFormat.readFeatures(featureObj, {
      dataProjection: 'EPSG:4326',
      featureProjection: 'EPSG:3857',
    })

    analysisSource.value!.addFeatures(features)
  })
}

/**
 * Zoom map to fit a specific region's extent
 */
const fitToRegion = (regionId: string) => {
  if (!regionSource.value || !map.value) return
  const features = regionSource.value.getFeatures().filter(
    (f) => f.get('regionId') === regionId,
  )
  if (features.length === 0) return

  const extent = features[0].getGeometry()!.getExtent()
  for (let i = 1; i < features.length; i++) {
    const e = features[i].getGeometry()!.getExtent()
    extent[0] = Math.min(extent[0], e[0])
    extent[1] = Math.min(extent[1], e[1])
    extent[2] = Math.max(extent[2], e[2])
    extent[3] = Math.max(extent[3], e[3])
  }
  map.value.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 15, duration: 500 })
}

const hideClusterSelection = () => {
  clusterSelectionSites.value = []
  clusterSelectionPosition.value = null
}

const isSameLocationCluster = (points: MapPoint[]) => {
  if (points.length <= 1) {
    return false
  }

  const first = points[0]
  const epsilon = 1e-9

  return points.every(
    (point) =>
      Math.abs(point.latitude - first.latitude) <= epsilon
      && Math.abs(point.longitude - first.longitude) <= epsilon,
  )
}

const showClusterSelection = (points: MapPoint[], pixel: [number, number]) => {
  clusterSelectionSites.value = points

  const offsetX = 14
  const offsetY = -8
  const fallbackWidth = 260
  const fallbackHeight = 220
  const containerWidth = mapContainer.value?.clientWidth || fallbackWidth
  const containerHeight = mapContainer.value?.clientHeight || fallbackHeight

  const x = Math.max(8, Math.min(pixel[0] + offsetX, containerWidth - fallbackWidth - 8))
  const y = Math.max(8, Math.min(pixel[1] + offsetY, containerHeight - fallbackHeight - 8))

  clusterSelectionPosition.value = { x, y }
}

const selectClusterSite = (point: MapPoint) => {
  hideClusterSelection()
  handleMarkerClick(point)
}

/**
 * Clear map selection
 */
const clearSelection = () => {
  repositioningSiteId.value = null
  repositioningSiteName.value = null
  hideClusterSelection()
  selectedSite.value = null
  editDialogOpen.value = false
}

/**
 * Handle marker click - open edit dialog
 */
const handleMarkerClick = (point: MapPoint) => {
  if (repositioningSiteId.value) {
    searchError.value = 'Reposition mode is active. Click empty map to set new location.'
    return
  }

  if (selectedSite.value?.id === point.id) {
    clearSelection()
    return
  }
  selectedSite.value = point
  editDialogOpen.value = true
  emit('site-selected', point)
}

/**
 * Handle map click (empty area) - open create dialog
 */
const handleMapClick = (coords: [number, number]) => {
  if (!authStore.isAuthenticated) return

  if (repositioningSiteId.value) {
    void applyReposition(coords)
    return
  }

  createCoordinates.value = coords
  createItemId.value = null
  createDialogOpen.value = true
}

const startRepositionMode = () => {
  if (!selectedSite.value) return

  repositioningSiteId.value = selectedSite.value.id
  repositioningSiteName.value = selectedSite.value.name || 'Unnamed site'
  editDialogOpen.value = false
  searchError.value = `Reposition mode active for "${repositioningSiteName.value}". Click the exact location.`
}

const applyReposition = async (coords: [number, number]) => {
  if (!repositioningSiteId.value) return

  const [lon, lat] = coords
  const siteId = repositioningSiteId.value
  const siteName = repositioningSiteName.value || 'Study site'

  searching.value = true
  const result = await studySitesStore.updateStudySite(siteId, {
    latitude: lat,
    longitude: lon,
  })
  searching.value = false

  if (result) {
    await studySitesStore.fetchMapPoints()
    searchError.value = `${siteName} moved to the selected location.`
    clearSelection()
    return
  }

  searchError.value = `Failed to move ${siteName}. Try clicking again.`
}

const clearLocationSearch = (clearQuery = false) => {
  if (locationSearchDebounce.value) {
    clearTimeout(locationSearchDebounce.value)
    locationSearchDebounce.value = null
  }

  if (locationSearchAbortController.value) {
    locationSearchAbortController.value.abort()
    locationSearchAbortController.value = null
  }

  searchResults.value = []
  if (!repositioningSiteId.value) {
    searchError.value = ''
  }
  searching.value = false
  highlightedSearchResultIndex.value = -1

  if (clearQuery) {
    locationQuery.value = ''
    searchPinSource.value?.clear()
  }
}

const runLocationSearch = async (query: string) => {
  const normalizedQuery = query.trim()
  if (normalizedQuery.length < 3) {
    searchResults.value = []
    searchError.value = ''
    return
  }

  if (locationSearchAbortController.value) {
    locationSearchAbortController.value.abort()
  }

  locationSearchAbortController.value = new AbortController()
  searching.value = true
  searchError.value = ''

  try {
    const results = await searchLocations(normalizedQuery, locationSearchAbortController.value.signal)
    searchResults.value = results
    highlightedSearchResultIndex.value = results.length > 0 ? 0 : -1
    if (results.length === 0) {
      searchError.value = 'No locations found'
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    logger.error('Location search failed', error)
    searchError.value = 'Location search unavailable'
    searchResults.value = []
    highlightedSearchResultIndex.value = -1
  } finally {
    searching.value = false
  }
}

const handleLocationSearchInput = () => {
  const query = locationQuery.value.trim()
  if (query.length < 3) {
    clearLocationSearch(false)
    return
  }

  if (locationSearchDebounce.value) {
    clearTimeout(locationSearchDebounce.value)
  }

  locationSearchDebounce.value = setTimeout(() => {
    runLocationSearch(query)
    locationSearchDebounce.value = null
  }, 350)
}

const handleLocationSearchEnter = async () => {
  if (searchResults.value.length > 0) {
    const selectedIndex = highlightedSearchResultIndex.value >= 0
      ? highlightedSearchResultIndex.value
      : 0
    selectLocationResult(searchResults.value[selectedIndex])
    return
  }

  await runLocationSearch(locationQuery.value)
  if (searchResults.value.length > 0) {
    selectLocationResult(searchResults.value[0])
  }
}

const handleLocationSearchKeydown = async (event: KeyboardEvent) => {
  if (event.key === 'ArrowDown' && searchResults.value.length > 0) {
    event.preventDefault()
    highlightedSearchResultIndex.value =
      (highlightedSearchResultIndex.value + 1 + searchResults.value.length) % searchResults.value.length
    return
  }

  if (event.key === 'ArrowUp' && searchResults.value.length > 0) {
    event.preventDefault()
    highlightedSearchResultIndex.value =
      (highlightedSearchResultIndex.value - 1 + searchResults.value.length) % searchResults.value.length
    return
  }

  if (event.key === 'Escape') {
    clearLocationSearch(false)
    return
  }

  if (event.key === 'Enter') {
    event.preventDefault()
    await handleLocationSearchEnter()
  }
}

const updateSearchPin = (result: GeocodeResult) => {
  if (!searchPinSource.value) return
  searchPinSource.value.clear()
  searchPinSource.value.addFeature(new Feature({
    geometry: new Point(fromLonLat([result.lon, result.lat])),
  }))
}

const selectLocationResult = (result: GeocodeResult) => {
  locationQuery.value = result.label
  searchResults.value = []
  searchError.value = authStore.isAuthenticated
    ? 'Zoomed to result. Click the exact spot on the map to create the site.'
    : ''
  highlightedSearchResultIndex.value = -1
  updateSearchPin(result)
  panTo(result.lat, result.lon, 10, 900)
}

/**
 * Fit map to show all markers
 */
const fitToMarkers = () => {
  if (!map.value || !vectorSource.value) return

  const extent = vectorSource.value.getExtent()
  if (extent && extent.some((v) => isFinite(v))) {
    map.value.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 15 })
  }
}

/**
 * Pan map to specific coordinates with smooth animation
 */
const panTo = (lat: number, lon: number, zoom?: number, duration = 1500) => {
  if (!map.value) {
    logger.warn('Map instance not initialized')
    return
  }

  const view = map.value.getView()
  const center = fromLonLat([lon, lat])

  if (zoom !== undefined) {
    view.animate({ center, zoom, duration })
  } else {
    view.animate({ center, duration })
  }
}

/**
 * Toggle box zoom mode
 */
const toggleBoxZoom = () => {
  setBoxZoomState(!boxZoomActive.value)
}

/**
 * Reset map view to initial state
 */
const resetView = () => {
  if (!map.value) return
  map.value.getView().setCenter(fromLonLat(props.initialCenter))
  map.value.getView().setZoom(props.initialZoom)
}

/**
 * Handle site saved from edit dialog
 */
const handleSiteSaved = async () => {
  clearSelection()
  await studySitesStore.fetchMapPoints()
}

/**
 * Handle site deleted from edit dialog
 */
const handleSiteDeleted = async () => {
  clearSelection()
  await studySitesStore.fetchMapPoints()
}

/**
 * Handle site created from create dialog
 */
const handleSiteCreated = async () => {
  createDialogOpen.value = false
  createCoordinates.value = null
  createItemId.value = null
  await studySitesStore.fetchMapPoints()
}

// Single shallow watcher — the store replaces the whole array on fetch
watch(
  () => mapPoints.value,
  () => {
    if (!mapInitialized.value) {
      nextTick(() => initMap())
      return
    }
    updateMarkers()
    nextTick(() => updateMapSize())
  },
)

watch(
  () => props.regions,
  () => {
    if (mapInitialized.value) {
      updateRegions()
    }
  },
)

watch(
  () => props.bufferFeatures,
  () => {
    if (mapInitialized.value) {
      updateAnalysisFeatures()
    }
  },
)

watch(editDialogOpen, (isOpen) => {
  if (!isOpen) {
    clearSelection()
  }
})

// Lifecycle
onMounted(() => {
  if (mapContainer.value) {
    resizeObserver.value = new ResizeObserver(() => {
      if (!mapInitialized.value) {
        initMap()
      }
      updateMapSize()
    })
    resizeObserver.value.observe(mapContainer.value)
  }

  window.addEventListener('resize', handleWindowResize)
  window.addEventListener('keydown', handleWindowKeydown)

  // Initialize map only when container has non-zero size
  nextTick(() => {
    initMap()
    requestAnimationFrame(() => initMap())
    setTimeout(() => initMap(), 150)
  })

  // Fit to markers after data loads
  setTimeout(() => {
    if (mapInitialized.value && mapPoints.value.length > 0) {
      fitToMarkers()
    }
  }, 500)
})

onUnmounted(() => {
  clearLocationSearch(false)

  if (viewportEmitTimer.value) {
    clearTimeout(viewportEmitTimer.value)
    viewportEmitTimer.value = null
  }

  window.removeEventListener('resize', handleWindowResize)
  window.removeEventListener('keydown', handleWindowKeydown)
  resizeObserver.value?.disconnect()
  resizeObserver.value = null
  mapInitialized.value = false

  if (map.value) {
    setBoxZoomState(false)
    map.value.setTarget(undefined)
    map.value = null
  }
})

defineExpose({ panTo, fitToMarkers, fitToRegion, resetView, toggleBoxZoom, map })
</script>

<style scoped>
.study-site-map {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 600px;
}

.map-container {
  flex: 1 1 auto;
  width: 100%;
  min-height: 600px;
}

.map-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1000;
}

.location-search {
  position: relative;
  margin-bottom: 0.5rem;
  width: 100%;
  min-width: 260px;
}

.location-search-input {
  width: 100%;
  padding: 0.45rem 2rem 0.45rem 0.6rem;
  border: 1px solid rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.9rem;
}

.location-search-input:focus {
  outline: 2px solid rgba(var(--v-theme-primary), 0.45);
  border-color: rgb(var(--v-theme-primary));
}

.location-search-clear {
  position: absolute;
  top: 0.25rem;
  right: 0.25rem;
  border: none;
  border-radius: 4px;
  width: 1.5rem;
  height: 1.5rem;
  background-color: transparent;
  color: rgba(0, 0, 0, 0.6);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}

.location-search-clear:hover {
  background-color: rgba(0, 0, 0, 0.06);
}

.location-search-status {
  margin-top: 0.25rem;
  padding: 0.3rem 0.45rem;
  font-size: 0.8rem;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.05);
  color: rgba(0, 0, 0, 0.72);
}

.location-search-status.error {
  color: rgb(var(--v-theme-error));
  background-color: rgba(var(--v-theme-error), 0.08);
}

.location-search-results {
  list-style: none;
  margin: 0.25rem 0 0;
  padding: 0;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  background-color: rgb(var(--v-theme-surface));
}

.location-search-result {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0.5rem 0.6rem;
  cursor: pointer;
  font-size: 0.85rem;
  color: rgb(var(--v-theme-on-surface));
}

.location-search-result:hover {
  background-color: rgba(var(--v-theme-primary), 0.08);
}

.location-search-result.active {
  background-color: rgba(var(--v-theme-primary), 0.14);
}

.cluster-selection-popover {
  position: absolute;
  z-index: 1100;
  width: 260px;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid rgba(0, 0, 0, 0.16);
  border-radius: 8px;
  background-color: rgb(var(--v-theme-surface));
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.cluster-selection-title {
  position: sticky;
  top: 0;
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.72);
  background-color: rgb(var(--v-theme-surface));
}

.cluster-selection-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.cluster-selection-item {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  padding: 0.55rem 0.65rem;
  cursor: pointer;
}

.cluster-selection-item:hover {
  background-color: rgba(var(--v-theme-primary), 0.08);
}

.cluster-selection-name {
  display: block;
  font-size: 0.85rem;
  color: rgb(var(--v-theme-on-surface));
}

.cluster-selection-meta {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.72rem;
  color: rgba(0, 0, 0, 0.62);
}

.cluster-selection-more {
  padding: 0.45rem 0.65rem;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  font-size: 0.72rem;
  color: rgba(0, 0, 0, 0.58);
}

.map-stats {
  position: absolute;
  bottom: 20px;
  left: 20px;
  z-index: 1000;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.6);
  letter-spacing: 0.5px;
}
</style>

<!-- Unscoped overrides for OpenLayers controls (OL's own CSS uses high specificity) -->
<style>
.study-site-map .ol-zoom {
  top: auto !important;
  left: auto !important;
  bottom: 2.5rem !important;
  right: 0.5rem !important;
}

.study-site-map .ol-rotate {
  top: auto !important;
  left: auto !important;
  bottom: 7rem !important;
  right: 0.5rem !important;
}

.study-site-map .ol-attribution {
  top: auto !important;
  left: auto !important;
  bottom: 0.5rem !important;
  right: 0.5rem !important;
}

.study-site-map .ol-zoom,
.study-site-map .ol-rotate,
.study-site-map .ol-attribution {
  position: absolute !important;
  background: none;
  padding: 0;
}

.study-site-map .ol-zoom button,
.study-site-map .ol-rotate button {
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  border: none;
  border-radius: 4px;
  margin: 2px 0;
  width: 2rem;
  height: 2rem;
  font-size: 1.1rem;
  font-weight: 500;
  box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.2), 0 4px 5px 0 rgba(0, 0, 0, 0.14);
  cursor: pointer;
  transition: background-color 0.15s;
}

.study-site-map .ol-zoom button:hover,
.study-site-map .ol-rotate button:hover {
  background-color: rgb(var(--v-theme-surface-variant));
}

.study-site-map .ol-zoom button:focus,
.study-site-map .ol-rotate button:focus {
  outline: none;
}

.study-site-map .ol-attribution button,
.study-site-map .ol-attribution ul {
  background-color: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.7rem;
  border-radius: 4px;
  box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.2), 0 4px 5px 0 rgba(0, 0, 0, 0.14);
}

.study-site-map .ol-attribution button {
  border: none;
  cursor: pointer;
}

.study-site-map .ol-attribution ul {
  padding: 2px 6px;
}

.study-site-map .ol-dragbox {
  border: 2px solid rgb(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.15);
}
</style>
