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
                @keydown="onSearchKeydown" />
              <button
                v-if="locationQuery"
                class="location-search-clear"
                type="button"
                aria-label="Clear search"
                @click="onClearSearch">
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
      @reposition="onStartReposition"
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
import { Tile as TileLayer } from 'ol/layer'
import { OSM } from 'ol/source'
import { Feature } from 'ol'
import { Point } from 'ol/geom'
import { fromLonLat, toLonLat, transformExtent } from 'ol/proj'
import { boundingExtent } from 'ol/extent'
import { DragBox, DragZoom, DragPan } from 'ol/interaction'
import { shiftKeyOnly } from 'ol/events/condition'
import { useStudySitesStore, type MapPoint } from '../../stores/studySites'
import { useAuthStore } from '../../stores/auth'
import type { Region } from '../../stores/regions'
import type { GISBufferedFeature } from '../../stores/gis'
import type { GeocodeResult } from '@/services/mapService'
import { useMapLayers } from '@/composables/useMapLayers'
import { useMapSearch } from '@/composables/useMapSearch'
import { useMapInteractions } from '@/composables/useMapInteractions'
import StudySiteEditDialog from './StudySiteEditDialog.vue'
import StudySiteCreateDialog from './StudySiteCreateDialog.vue'

const props = defineProps({
  initialCenter: {
    type: Array as unknown as PropType<[number, number]>,
    default: () => [0, 20],
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

// Stores
const studySitesStore = useStudySitesStore()
const authStore = useAuthStore()
const { mapPoints: allMapPoints, loading } = storeToRefs(studySitesStore)

// Composables
const layers = useMapLayers()
const search = useMapSearch()
const interactions = useMapInteractions()

// Re-export composable state for the template
const {
  locationQuery, searchResults, searching, searchError, highlightedSearchResultIndex,
  handleLocationSearchInput, clearLocationSearch,
} = search

const {
  boxZoomActive, clusterSelectionVisible, visibleClusterSelectionSites,
  clusterSelectionHiddenCount, clusterSelectionStyle, hideClusterSelection,
  isSameLocationCluster, showClusterSelection, repositioningSiteId, repositioningSiteName,
} = interactions

// Use filtered sites if provided, otherwise use all from store
const mapPoints = computed(() => props.sites || allMapPoints.value)

// Map refs
const mapContainer = ref<HTMLDivElement | null>(null)
const map = ref<Map | null>(null)
const mapInitialized = ref(false)
const resizeObserver = ref<ResizeObserver | null>(null)
const viewportEmitTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const dragBoxInteraction = ref<any>(null)
const dragPanInteraction = ref<any>(null)

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

// --- Viewport ---

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
  if (viewportEmitTimer.value) clearTimeout(viewportEmitTimer.value)
  viewportEmitTimer.value = setTimeout(() => {
    emitViewportChanged()
    viewportEmitTimer.value = null
  }, 120)
}

// --- Box zoom ---

const setBoxZoomState = (active: boolean) => {
  if (!map.value && active) return
  boxZoomActive.value = active
  const target = map.value?.getTargetElement() as HTMLElement | undefined
  if (target) target.style.cursor = active ? 'crosshair' : ''
  if (dragPanInteraction.value) dragPanInteraction.value.setActive(!active)
}

const toggleBoxZoom = () => setBoxZoomState(!boxZoomActive.value)

// --- Map init ---

const initMap = () => {
  if (!mapContainer.value || mapInitialized.value) return
  const { clientWidth, clientHeight } = mapContainer.value
  if (clientWidth === 0 || clientHeight === 0) return

  layers.createLayers()

  map.value = new Map({
    target: mapContainer.value,
    layers: [
      new TileLayer({ source: new OSM() }),
      layers.regionLayer.value,
      layers.analysisLayer.value,
      layers.clusterLayer.value,
      layers.searchPinLayer.value,
    ],
    view: new View({ center: fromLonLat(props.initialCenter), zoom: props.initialZoom }),
  })

  // Click handler
  map.value.on('click', (event) => {
    if (boxZoomActive.value) return
    hideClusterSelection()

    const feature = map.value?.forEachFeatureAtPixel(event.pixel, (f) => f) as Feature | undefined
    if (!feature) {
      const coords = toLonLat(event.coordinate)
      handleMapClick(coords as [number, number])
      return
    }

    const clusterFeatures = feature.get('features') as Feature[] | undefined
    if (!clusterFeatures) {
      const regionId = feature.get('regionId') as string | undefined
      if (regionId) emit('region-selected', regionId)
      return
    }

    if (clusterFeatures.length === 1) {
      const point = clusterFeatures[0].get('mapPoint') as MapPoint
      handleMarkerClick(point)
    } else {
      const points = clusterFeatures
        .map((f) => f.get('mapPoint') as MapPoint | undefined)
        .filter((point): point is MapPoint => !!point)

      if (isSameLocationCluster(points)) {
        const cw = mapContainer.value?.clientWidth || 260
        const ch = mapContainer.value?.clientHeight || 220
        showClusterSelection(points, event.pixel as [number, number], cw, ch)
        return
      }

      const extent = boundingExtent(
        clusterFeatures.map((f) => (f.getGeometry() as Point).getCoordinates()),
      )
      map.value?.getView().fit(extent, { padding: [80, 80, 80, 80], maxZoom: 16, duration: 500 })
    }
  })

  // Pointer cursor on hover
  map.value.on('pointermove', (event) => {
    if (boxZoomActive.value) return
    const hit = map.value?.hasFeatureAtPixel(event.pixel)
    const target = map.value?.getTargetElement()
    if (target) (target as HTMLElement).style.cursor = hit ? 'pointer' : ''
  })

  map.value.on('moveend', () => {
    hideClusterSelection()
    scheduleViewportEmit()
  })

  // Replace default DragZoom with our DragBox
  map.value.getInteractions().forEach((interaction) => {
    if (interaction instanceof DragZoom) map.value!.removeInteraction(interaction)
    if (interaction instanceof DragPan) dragPanInteraction.value = interaction
  })

  dragBoxInteraction.value = new DragBox({
    condition: (event) => boxZoomActive.value || shiftKeyOnly(event),
  })

  dragBoxInteraction.value.on('boxend', () => {
    const extent = dragBoxInteraction.value!.getGeometry().getExtent()
    map.value?.getView().fit(extent, { duration: 500 })
    if (boxZoomActive.value) setBoxZoomState(false)
  })

  dragBoxInteraction.value.on('boxcancel', () => {
    if (boxZoomActive.value) setBoxZoomState(false)
  })

  map.value.addInteraction(dragBoxInteraction.value)

  emit('map-ready', map.value)
  mapInitialized.value = true

  layers.updateMarkers(mapPoints.value)
  layers.updateRegions(props.regions)
  layers.updateAnalysisFeatures(props.bufferFeatures)
  scheduleViewportEmit()
}

const updateMapSize = () => {
  if (!mapInitialized.value || !map.value || !mapContainer.value) return
  const { clientWidth, clientHeight } = mapContainer.value
  if (clientWidth > 0 && clientHeight > 0) {
    map.value.updateSize()
    scheduleViewportEmit()
  }
}

const handleWindowResize = () => {
  if (!mapInitialized.value) initMap()
  updateMapSize()
  scheduleViewportEmit()
}

const handleWindowKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && clusterSelectionVisible.value) {
    hideClusterSelection()
    return
  }
  if (event.key === 'Escape' && boxZoomActive.value) setBoxZoomState(false)
}

// --- Site interaction ---

const clearSelection = () => {
  interactions.clearReposition()
  hideClusterSelection()
  selectedSite.value = null
  editDialogOpen.value = false
}

const handleMarkerClick = (point: MapPoint) => {
  if (repositioningSiteId.value) {
    search.searchError.value = 'Reposition mode is active. Click empty map to set new location.'
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

const onStartReposition = () => {
  if (!selectedSite.value) return
  interactions.startRepositionMode(selectedSite.value)
  editDialogOpen.value = false
  search.searchError.value = `Reposition mode active for "${repositioningSiteName.value}". Click the exact location.`
}

const applyReposition = async (coords: [number, number]) => {
  if (!repositioningSiteId.value) return
  const [lon, lat] = coords
  const siteId = repositioningSiteId.value
  const siteName = repositioningSiteName.value || 'Study site'

  search.searching.value = true
  const result = await studySitesStore.updateStudySite(siteId, { latitude: lat, longitude: lon })
  search.searching.value = false

  if (result) {
    await studySitesStore.fetchMapPoints()
    search.searchError.value = `${siteName} moved to the selected location.`
    clearSelection()
    return
  }
  search.searchError.value = `Failed to move ${siteName}. Try clicking again.`
}

const selectClusterSite = (point: MapPoint) => {
  hideClusterSelection()
  handleMarkerClick(point)
}

// --- Search integration ---

const onSearchKeydown = async (event: KeyboardEvent) => {
  const result = await search.handleLocationSearchKeydown(event)
  if (result) selectLocationResult(result)
}

const onClearSearch = () => {
  clearLocationSearch(true)
  layers.clearSearchPin()
  if (!repositioningSiteId.value) search.searchError.value = ''
}

const selectLocationResult = (result: GeocodeResult) => {
  locationQuery.value = result.label
  searchResults.value = []
  search.searchError.value = authStore.isAuthenticated
    ? 'Zoomed to result. Click the exact spot on the map to create the site.'
    : ''
  highlightedSearchResultIndex.value = -1
  layers.updateSearchPin(result.lon, result.lat)
  panTo(result.lat, result.lon, 10, 900)
}

// --- Navigation ---

const fitToMarkers = () => {
  if (!map.value || !layers.vectorSource.value) return
  const extent = layers.vectorSource.value.getExtent()
  if (extent && extent.some((v: number) => isFinite(v))) {
    map.value.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 15 })
  }
}

const panTo = (lat: number, lon: number, zoom?: number, duration = 1500) => {
  if (!map.value) return
  const view = map.value.getView()
  const center = fromLonLat([lon, lat])
  if (zoom !== undefined) {
    view.animate({ center, zoom, duration })
  } else {
    view.animate({ center, duration })
  }
}

const resetView = () => {
  if (!map.value) return
  map.value.getView().setCenter(fromLonLat(props.initialCenter))
  map.value.getView().setZoom(props.initialZoom)
}

const fitToRegion = (regionId: string) => {
  if (!map.value) return
  const extent = layers.fitToRegionExtent(regionId)
  if (extent) {
    map.value.getView().fit(extent, { padding: [50, 50, 50, 50], maxZoom: 15, duration: 500 })
  }
}

// --- CRUD callbacks ---

const handleSiteSaved = async () => {
  clearSelection()
  await studySitesStore.fetchMapPoints()
}

const handleSiteDeleted = async () => {
  clearSelection()
  await studySitesStore.fetchMapPoints()
}

const handleSiteCreated = async () => {
  createDialogOpen.value = false
  createCoordinates.value = null
  createItemId.value = null
  await studySitesStore.fetchMapPoints()
}

// --- Watchers ---

watch(
  () => mapPoints.value,
  () => {
    if (!mapInitialized.value) {
      nextTick(() => initMap())
      return
    }
    layers.updateMarkers(mapPoints.value)
    nextTick(() => updateMapSize())
  },
)

watch(
  () => props.regions,
  () => { if (mapInitialized.value) layers.updateRegions(props.regions) },
)

watch(
  () => props.bufferFeatures,
  () => { if (mapInitialized.value) layers.updateAnalysisFeatures(props.bufferFeatures) },
)

watch(editDialogOpen, (isOpen) => {
  if (!isOpen) clearSelection()
})

// --- Lifecycle ---

onMounted(() => {
  if (mapContainer.value) {
    resizeObserver.value = new ResizeObserver(() => {
      if (!mapInitialized.value) initMap()
      updateMapSize()
    })
    resizeObserver.value.observe(mapContainer.value)
  }

  window.addEventListener('resize', handleWindowResize)
  window.addEventListener('keydown', handleWindowKeydown)

  nextTick(() => {
    initMap()
    requestAnimationFrame(() => initMap())
    setTimeout(() => initMap(), 150)
  })

  setTimeout(() => {
    if (mapInitialized.value && mapPoints.value.length > 0) fitToMarkers()
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
