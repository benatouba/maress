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
      <v-card elevation="2">
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
      <v-card elevation="2">
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
      v-model="editDialogOpen"
      :study-site="selectedSite"
      @saved="handleSiteSaved"
      @deleted="handleSiteDeleted"
      />

    <!-- Create Dialog -->
    <StudySiteCreateDialog
      v-model="createDialogOpen"
      :item-id="createItemId"
      :coordinates="createCoordinates"
      @created="handleSiteCreated" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Map, View } from 'ol'
import { Tile as TileLayer, Vector as VectorLayer } from 'ol/layer'
import { OSM, Vector as VectorSource } from 'ol/source'
import { Feature } from 'ol'
import { Point } from 'ol/geom'
import { fromLonLat, toLonLat } from 'ol/proj'
import { Style, Circle, Fill, Stroke, Text } from 'ol/style'
import { click } from 'ol/events/condition'
import { Select } from 'ol/interaction'
import { useStudySitesStore, type StudySiteWithItem } from '../../stores/studySites'
import StudySiteEditDialog from './StudySiteEditDialog.vue'
import StudySiteCreateDialog from './StudySiteCreateDialog.vue'

const props = defineProps({
  initialCenter: {
    type: Array as () => [number, number],
    default: () => [0, 20], // [lon, lat]
  },
  initialZoom: { type: Number, default: 2 },
  sites: {
    type: Array as () => StudySiteWithItem[],
    default: null,
  },
})

const emit = defineEmits(['site-selected', 'map-ready'])

// Store
const studySitesStore = useStudySitesStore()
const { studySites: allStudySites, loading } = storeToRefs(studySitesStore)

// Use filtered sites if provided, otherwise use all sites from store
const studySites = computed(() => props.sites || allStudySites.value)

// Map refs
const mapContainer = ref<HTMLDivElement | null>(null)
const map = ref<Map | null>(null)
const vectorSource = ref<VectorSource | null>(null)
const vectorLayer = ref<VectorLayer<VectorSource> | null>(null)
const selectInteraction = ref<Select | null>(null)

// Dialog state
const editDialogOpen = ref(false)
const createDialogOpen = ref(false)
const selectedSite = ref<StudySiteWithItem | null>(null)
const createItemId = ref<string | null>(null)
const createCoordinates = ref<[number, number] | null>(null)

// Computed
const totalSites = computed(() => studySites.value.length)
const manualCount = computed(() => studySites.value.filter((s) => s.is_manual).length)
const automaticCount = computed(() => studySites.value.filter((s) => !s.is_manual).length)

/**
 * Create style for a study site marker
 * Manual sites: green, Automatic sites: blue
 */
const createMarkerStyle = (studySite: StudySiteWithItem, selected = false) => {
  const color = studySite.is_manual ? '#4CAF50' : '#2196F3' // Green for manual, blue for automatic
  const strokeColor = selected ? '#FF5722' : '#FFFFFF'
  const strokeWidth = selected ? 3 : 2
  const radius = selected ? 8 : 6

  return new Style({
    image: new Circle({
      radius,
      fill: new Fill({ color }),
      stroke: new Stroke({ color: strokeColor, width: strokeWidth }),
    }),
  })
}

/**
 * Initialize the OpenLayers map
 */
const initMap = () => {
  if (!mapContainer.value) return

  // Create vector source for markers
  vectorSource.value = new VectorSource()

  // Create vector layer
  vectorLayer.value = new VectorLayer({ source: vectorSource.value })

  // Create map
  map.value = new Map({
    target: mapContainer.value,
    layers: [new TileLayer({ source: new OSM() }), vectorLayer.value],
    view: new View({ center: fromLonLat(props.initialCenter), zoom: props.initialZoom }),
  })

  // Add click interaction for selecting markers
  selectInteraction.value = new Select({
    condition: click,
    layers: [vectorLayer.value],
    style: (feature) => {
      const studySite = feature.get('studySite')
      return createMarkerStyle(studySite, true)
    },
  })

  selectInteraction.value.on('select', (event) => {
    if (event.selected.length > 0) {
      const feature = event.selected[0]
      const studySite = feature.get('studySite') as StudySiteWithItem
      handleMarkerClick(studySite)
    }
  })

  map.value.addInteraction(selectInteraction.value)

  // Add click interaction for creating new sites
  map.value.on('click', (event) => {
    const features = map.value?.getFeaturesAtPixel(event.pixel)

    // If no features at click location, open create dialog
    if (!features || features.length === 0) {
      const coords = toLonLat(event.coordinate)
      handleMapClick(coords as [number, number])
    }
  })

  // Emit map-ready event
  emit('map-ready', map.value)

  // Update markers
  updateMarkers()
}

/**
 * Update markers on the map based on study sites
 */
const updateMarkers = () => {
  if (!vectorSource.value) return

  // Clear existing features
  vectorSource.value.clear()

  // Add features for each study site
  studySites.value.forEach((site) => {
    // Get coordinates from the location object
    if (!site.location || !site.location.latitude || !site.location.longitude) return

    const feature = new Feature({
      geometry: new Point(fromLonLat([site.location.longitude, site.location.latitude])),
      studySite: site,
    })

    feature.setStyle(createMarkerStyle(site))

    // Add tooltip on hover
    feature.set('name', site.item_title || 'Unknown')

    vectorSource.value?.addFeature(feature)
  })
}

/**
 * Clear map selection
 */
const clearSelection = () => {
  selectedSite.value = null
  editDialogOpen.value = false
  if (selectInteraction.value) {
    selectInteraction.value.getFeatures().clear()
  }
}

/**
 * Handle marker click - open edit dialog
 */
const handleMarkerClick = (studySite: StudySiteWithItem) => {
  if (selectedSite.value?.id === studySite.id) {
    clearSelection()
    return
  }
  if (!studySite) {
    console.warn('Invalid study site clicked')
    return
  }
  selectedSite.value = studySite
  editDialogOpen.value = true
  emit('site-selected', studySite)
}

/**
 * Handle map click (empty area) - open create dialog
 */
const handleMapClick = (coords: [number, number]) => {
  // For creating a new site, we need to know which item it belongs to
  // For now, we'll open a dialog that lets the user select an item
  // Or we can require an item to be selected before allowing creation
  createCoordinates.value = coords
  createItemId.value = null // Will be selected in dialog
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
    // Animate both center and zoom
    view.animate({ center: center, zoom: zoom, duration: duration })
  } else {
    // Just animate center, keep current zoom
    view.animate({ center: center, duration: duration })
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
const handleSiteSaved = () => {
  clearSelection()
  updateMarkers()
}

/**
 * Handle site deleted from edit dialog
 */
const handleSiteDeleted = () => {
  clearSelection()
  updateMarkers()
}

/**
 * Handle site created from create dialog
 */
const handleSiteCreated = () => {
  createDialogOpen.value = false
  createCoordinates.value = null
  createItemId.value = null
  updateMarkers()
}

// Watch for changes in study sites
watch(
  () => studySites.value,
  () => {
    updateMarkers()
  },
  { deep: true },
)

// Watch for changes in the sites prop
watch(
  () => props.sites,
  () => {
    updateMarkers()
  },
  { deep: true },
)

watch(editDialogOpen, (isOpen) => {
  if (!isOpen) {
    clearSelection()
  }
})

// Lifecycle
onMounted(async () => {
  // Fetch all study sites
  await studySitesStore.fetchAllStudySites()

  // Initialize map
  initMap()

  // Fit to markers after data loads
  setTimeout(() => {
    if (studySites.value.length > 0) {
      fitToMarkers()
    }
  }, 500)
})

onUnmounted(() => {
  // Clean up map
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
  width: 100%;
  height: 100%;
  min-height: 600px;
}

.map-container {
  width: 100%;
  height: 100%;
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

/* Add pointer cursor for map to indicate it's clickable */
.map-container :deep(.ol-viewport) {
  cursor: pointer;
}
</style>
