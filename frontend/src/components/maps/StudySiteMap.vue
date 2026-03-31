<template>
  <div class="study-site-map">
    <div
      ref="mapContainer"
      class="map-container"></div>

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
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { Map, View } from 'ol'
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer'
import { OSM, Vector as VectorSource, Cluster } from 'ol/source'
import { Feature } from 'ol'
import { Point } from 'ol/geom'
import { fromLonLat, toLonLat, transformExtent } from 'ol/proj'
import { Style, Circle, Fill, Stroke, Text } from 'ol/style'
import { boundingExtent } from 'ol/extent'
import { useStudySitesStore, type MapPoint } from '../../stores/studySites'
import { useAuthStore } from '../../stores/auth'
import StudySiteEditDialog from './StudySiteEditDialog.vue'
import StudySiteCreateDialog from './StudySiteCreateDialog.vue'

const props = defineProps({
  initialCenter: {
    type: Array as () => [number, number],
    default: () => [0, 20], // [lon, lat]
  },
  initialZoom: { type: Number, default: 2 },
  sites: {
    type: Array as () => MapPoint[],
    default: null,
  },
})

const emit = defineEmits(['site-selected', 'map-ready', 'viewport-changed'])

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
const vectorSource = ref<VectorSource | null>(null)
const clusterSource = ref<Cluster | null>(null)
const clusterLayer = ref<VectorLayer<Cluster> | null>(null)
const resizeObserver = ref<ResizeObserver | null>(null)
const viewportEmitTimer = ref<ReturnType<typeof setTimeout> | null>(null)

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

// Dialog state
const editDialogOpen = ref(false)
const createDialogOpen = ref(false)
const selectedSite = ref<MapPoint | null>(null)
const createItemId = ref<string | null>(null)
const createCoordinates = ref<[number, number] | null>(null)

// Computed
const totalSites = computed(() => mapPoints.value.length)
const manualCount = computed(() => mapPoints.value.filter((s) => s.is_manual).length)
const automaticCount = computed(() => mapPoints.value.filter((s) => !s.is_manual).length)

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

  // Create map
  map.value = new Map({
    target: mapContainer.value,
    layers: [new TileLayer({ source: new OSM() }), clusterLayer.value],
    view: new View({ center: fromLonLat(props.initialCenter), zoom: props.initialZoom }),
  })

  // Click handler — works for both clusters and single points
  map.value.on('click', (event) => {
    const feature = map.value?.forEachFeatureAtPixel(event.pixel, (f) => f) as Feature | undefined

    if (!feature) {
      // Empty area click → create dialog
      const coords = toLonLat(event.coordinate)
      handleMapClick(coords as [number, number])
      return
    }

    const clusterFeatures = feature.get('features') as Feature[] | undefined
    if (!clusterFeatures) return

    if (clusterFeatures.length === 1) {
      // Single point — open edit dialog
      const point = clusterFeatures[0].get('mapPoint') as MapPoint
      handleMarkerClick(point)
    } else {
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
    const hit = map.value?.hasFeatureAtPixel(event.pixel)
    const target = map.value?.getTargetElement()
    if (target) {
      ;(target as HTMLElement).style.cursor = hit ? 'pointer' : ''
    }
  })

  map.value.on('moveend', () => {
    scheduleViewportEmit()
  })

  emit('map-ready', map.value)
  mapInitialized.value = true

  // Populate features
  updateMarkers()
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
 * Clear map selection
 */
const clearSelection = () => {
  selectedSite.value = null
  editDialogOpen.value = false
}

/**
 * Handle marker click - open edit dialog
 */
const handleMarkerClick = (point: MapPoint) => {
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
  createCoordinates.value = coords
  createItemId.value = null
  createDialogOpen.value = true
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
    console.warn('Map instance not initialized')
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
  if (viewportEmitTimer.value) {
    clearTimeout(viewportEmitTimer.value)
    viewportEmitTimer.value = null
  }

  window.removeEventListener('resize', handleWindowResize)
  resizeObserver.value?.disconnect()
  resizeObserver.value = null
  mapInitialized.value = false

  if (map.value) {
    map.value.setTarget(undefined)
    map.value = null
  }
})

defineExpose({ panTo, fitToMarkers, resetView, map })
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
</style>
