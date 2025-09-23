<template>
  <v-row class="fill-height">
    <!-- Map Section -->
    <v-col cols="8">
      <v-card class="map-wrapper">
        <div
          id="map"
          ref="mapContainer"
          class="map-container"
          style="height: 100%; width: 100%"
        ></div>
      </v-card>
    </v-col>

    <!-- Data Table Section -->
    <v-col cols="4">
      <v-card>
        <v-card-title>Research Items</v-card-title>
        <v-data-table
          :headers="tableHeaders"
          :items="filteredItems"
          :loading="itemsStore.loading"
          item-key="id"
          density="compact"
          @click:row="openEditDialog"
        >
          <template v-slot:item.actions="{ item }">
            <v-btn
              icon="mdi-pencil"
              size="small"
              @click.stop="openEditDialog(null, item)"
            />
          </template>
        </v-data-table>
      </v-card>
    </v-col>
  </v-row>

  <!-- Edit Study Site Dialog -->
  <v-dialog v-model="editDialog" max-width="600px">
    <v-card>
      <v-card-title>
        <span class="text-h5">Edit Study Site</span>
      </v-card-title>
      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="editForm.title"
                label="Item Title"
                readonly
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="editForm.latitude"
                label="Latitude"
                type="number"
                step="any"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="editForm.longitude"
                label="Longitude"
                type="number"
                step="any"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="editForm.country"
                label="Country"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="editForm.context"
                label="Context"
              />
            </v-col>
            <v-col cols="6">
              <v-select
                v-model="editForm.extraction_method"
                :items="extractionMethods"
                label="Extraction Method"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="editForm.confidence_score"
                label="Confidence Score"
                type="number"
                step="0.1"
                min="0"
                max="1"
              />
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          color="grey-darken-1"
          variant="text"
          @click="closeEditDialog"
        >
          Cancel
        </v-btn>
        <v-btn
          color="blue-darken-1"
          variant="text"
          @click="saveStudySite"
          :loading="saving"
        >
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useZoteroStore } from '@/stores/zotero'
import { useNotificationStore } from '@/stores/notification'

// OpenLayers imports
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import OSM from 'ol/source/OSM'
import VectorSource from 'ol/source/Vector'
import Cluster from 'ol/source/Cluster'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import { Style, Fill, Stroke, Circle, Text } from 'ol/style'
import { fromLonLat } from 'ol/proj'
import Overlay from 'ol/Overlay'

// Import OpenLayers CSS
import 'ol/ol.css'

// Store setup
const itemsStore = useZoteroStore()
const notificationStore = useNotificationStore()
const { items } = storeToRefs(itemsStore)

// Reactive data
const mapContainer = ref(null)
const map = ref(null)
const vectorLayer = ref(null)
const hoveredClusterItems = ref([])
const editDialog = ref(false)
const saving = ref(false)

// Map configuration
const center = ref([
  parseFloat(import.meta.env.VITE_MAP_DEFAULT_CENTER_LNG),
  parseFloat(import.meta.env.VITE_MAP_DEFAULT_CENTER_LAT),
])
const zoom = ref(parseInt(import.meta.env.VITE_MAP_DEFAULT_ZOOM))

// Table configuration
const tableHeaders = [
  { title: 'Title', key: 'title', sortable: true },
  { title: 'Country', key: 'study_site.country', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, width: '80px' },
]

// Edit form
const editForm = ref({
  id: null,
  title: '',
  latitude: null,
  longitude: null,
  country: '',
  context: '',
  extraction_method: '',
  confidence_score: 0,
})

const extractionMethods = [
  'manual',
  'geocoded',
  'nlp_extracted',
  'coordinate_parsed',
]

// Computed filtered items based on hovered cluster
const filteredItems = computed(() => {
  if (hoveredClusterItems.value.length > 0) {
    return items.value.data?.filter(item =>
      hoveredClusterItems.value.some(clusteredItem =>
        clusteredItem.get('id') === `${item.id}-${item.study_site.id}`
      )
    ) || []
  }
  return items.value.data || []
})

// Create cluster style
const createClusterStyle = () => {
  const styleCache = {}
  return (feature) => {
    const size = feature.get('features').length
    let style = styleCache[size]
    if (!style) {
      if (size === 1) {
        // Single marker style
        style = new Style({
          image: new Circle({
            radius: 10,
            fill: new Fill({ color: '#3399CC' }),
            stroke: new Stroke({ color: '#fff', width: 2 }),
          }),
        })
      } else {
        // Cluster style
        style = new Style({
          image: new Circle({
            radius: Math.min(size * 2 + 10, 30),
            fill: new Fill({ color: '#3399CC' }),
            stroke: new Stroke({ color: '#fff', width: 2 }),
          }),
          text: new Text({
            text: size.toString(),
            fill: new Fill({ color: '#fff' }),
            font: 'bold 12px sans-serif',
          }),
        })
      }
      styleCache[size] = style
    }
    return style
  }
}

// Initialize map
const initializeMap = async () => {
  await nextTick()

  setTimeout(() => {
    if (!mapContainer.value) return

    map.value = new Map({
      target: mapContainer.value,
      layers: [
        new TileLayer({
          source: new OSM(),
        }),
      ],
      view: new View({
        center: fromLonLat(center.value),
        zoom: zoom.value,
      }),
    })

    // Add hover interaction
    map.value.on('pointermove', onMapHover)

    // Add click interaction
    map.value.on('click', onMapClick)

    // Reset hover when mouse leaves map
    map.value.getTargetElement().addEventListener('pointerleave', () => {
      hoveredClusterItems.value = []
    })

    map.value.updateSize()
    loadMarkers()
  }, 100)
}

// Handle map hover to filter table
const onMapHover = (evt) => {
  if (evt.dragging) {
    hoveredClusterItems.value = []
    return
  }

  const feature = map.value.forEachFeatureAtPixel(evt.pixel, (feature) => {
    return feature
  })

  if (feature) {
    const features = feature.get('features')
    if (features && features.length > 0) {
      hoveredClusterItems.value = features
    } else {
      hoveredClusterItems.value = []
    }
  } else {
    hoveredClusterItems.value = []
  }
}

// Handle map click to open edit dialog
const onMapClick = (evt) => {
  const feature = map.value.forEachFeatureAtPixel(evt.pixel, (feature) => {
    return feature
  })

  if (feature) {
    const features = feature.get('features')
    if (features && features.length === 1) {
      // Single feature clicked
      const clickedFeature = features[0]
      const itemId = clickedFeature.get('id').split('-')[0]
      const item = items.value.data?.find(item => item.id === itemId)
      if (item) {
        openEditDialog(null, item)
      }
    }
  }
}

// Load markers from store
const loadMarkers = async () => {
  try {
    const fetchedItems = await itemsStore.fetchItems()
    console.log('Items:', fetchedItems)

    // Create features from items
    const features = fetchedItems.data
      .filter(item => item.study_site?.latitude && item.study_site?.longitude)
      .map(item => {
        const feature = new Feature({
          geometry: new Point(fromLonLat([
            item.study_site.longitude,
            item.study_site.latitude
          ])),
        })

        // Set properties for identification
        feature.setProperties({
          id: `${item.id}-${item.study_site.id}`,
          name: item.title,
          country: item.study_site.country,
        })
        return feature
      })

    if (features.length > 0) {
      // Create vector source
      const vectorSource = new VectorSource({
        features: features,
      })

      // Create cluster source
      const clusterSource = new Cluster({
        distance: 40,
        minDistance: 20,
        source: vectorSource,
      })

      // Create vector layer with clustering
      vectorLayer.value = new VectorLayer({
        source: clusterSource,
        style: createClusterStyle(),
      })

      // Add layer to map
      map.value.addLayer(vectorLayer.value)

      // Fit view to show all markers
      const extent = vectorSource.getExtent()
      if (extent && extent.some(coord => coord !== Infinity && coord !== -Infinity)) {
        map.value.getView().fit(extent, {
          padding: [50, 50, 50, 50],
          maxZoom: 16,
        })
      }
    }
  } catch (error) {
    console.error('Error loading markers:', error)
  }
}

// Open edit dialog
const openEditDialog = (event, item) => {
  if (!item.study_site) return

  editForm.value = {
    id: item.study_site.id,
    title: item.title,
    latitude: item.study_site.latitude,
    longitude: item.study_site.longitude,
    country: item.study_site.country || '',
    context: item.study_site.context || '',
    extraction_method: item.study_site.extraction_method || 'manual',
    confidence_score: item.study_site.confidence_score || 0,
  }
  editDialog.value = true
}

// Close edit dialog
const closeEditDialog = () => {
  editDialog.value = false
  editForm.value = {
    id: null,
    title: '',
    latitude: null,
    longitude: null,
    country: '',
    context: '',
    extraction_method: '',
    confidence_score: 0,
  }
}

// Save study site changes
const saveStudySite = async () => {
  if (!editForm.value.id) return

  saving.value = true
  try {
    // Prepare update payload
    const updateData = {
      latitude: editForm.value.latitude,
      longitude: editForm.value.longitude,
      country: editForm.value.country,
      context: editForm.value.context,
      extraction_method: editForm.value.extraction_method,
      confidence_score: editForm.value.confidence_score,
    }

    // Make API call using the store's axios instance
    await itemsStore.updateStudySite(editForm.value.id, updateData)

    notificationStore.showNotification('Study site updated successfully!', 'success')

    // Refresh items and map
    await itemsStore.fetchItems()

    // Reload map markers
    if (vectorLayer.value) {
      map.value.removeLayer(vectorLayer.value)
    }
    await loadMarkers()

    closeEditDialog()
  } catch (error) {
    console.error('Error updating study site:', error)
    notificationStore.showNotification(
      error.response?.data?.detail || 'Failed to update study site',
      'error'
    )
  } finally {
    saving.value = false
  }
}

// Lifecycle
onMounted(() => {
  initializeMap()
})
</script>

<style scoped>
/* OpenLayers popup styles */
:deep(.ol-popup) {
  position: absolute;
  background-color: white;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  padding: 15px;
  border-radius: 10px;
  border: 1px solid #cccccc;
  bottom: 12px;
  left: -50px;
  min-width: 280px;
}

:deep(.ol-popup:after),
:deep(.ol-popup:before) {
  top: 100%;
  border: solid transparent;
  content: " ";
  height: 0;
  width: 0;
  position: absolute;
  pointer-events: none;
}

:deep(.ol-popup:after) {
  border-top-color: white;
  border-width: 10px;
  left: 48px;
  margin-left: -10px;
}

:deep(.ol-popup:before) {
  border-top-color: #cccccc;
  border-width: 11px;
  left: 48px;
  margin-left: -11px;
}

:deep(.ol-popup-closer) {
  text-decoration: none;
  position: absolute;
  top: 2px;
  right: 8px;
}

:deep(.ol-popup-closer:after) {
  content: "✖";
}

/* Map container */
#map {
  position: relative;
}

.map-wrapper {
  height: calc(100vh - 4rem);
  width: 100%;
  position: relative;
}

.map-container {
  height: 100%;
  width: 100%;
  min-height: 400px;
  min-width: 300px;
}

/* Table row cursor */
:deep(.v-data-table tbody tr) {
  cursor: pointer;
}

:deep(.v-data-table tbody tr:hover) {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>

