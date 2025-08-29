<template>
  <div class="map-wrapper">
    <div
      id="map"
      ref="mapContainer"
      class="map-container"
      style="height: 100%; width: 100%"
    ></div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useZoteroStore } from '@/stores/zotero'

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

// Reactive data
const mapContainer = ref(null)
const map = ref(null)
const itemsStore = useZoteroStore()
const { items } = storeToRefs(itemsStore)

// Map configuration
const center = ref([
  parseFloat(import.meta.env.VITE_MAP_DEFAULT_CENTER_LNG),
  parseFloat(import.meta.env.VITE_MAP_DEFAULT_CENTER_LAT),
])
const zoom = ref(parseInt(import.meta.env.VITE_MAP_DEFAULT_ZOOM))

// Create popup overlay
const createPopup = () => {
  const popupElement = document.createElement('div')
  popupElement.className = 'ol-popup'
  popupElement.innerHTML = `
    <a href="#" id="popup-closer" class="ol-popup-closer"></a>
    <div id="popup-content"></div>
  `

  const popupOverlay = new Overlay({
    element: popupElement,
    autoPan: {
      animation: {
        duration: 250,
      },
    },
  })

  // Close popup handler
  const closer = popupElement.querySelector('#popup-closer')
  closer.onclick = () => {
    popupOverlay.setPosition(undefined)
    closer.blur()
    return false
  }

  return { popupOverlay, popupElement }
}

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
  // Wait for DOM to be fully rendered
  await nextTick()

  // Add small delay to ensure container is sized
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

    // Force map to update size
    map.value.updateSize()

    // Load markers after map is initialized
    loadMarkers()

  }, 100) // 100ms delay
}

// Load markers from store
const loadMarkers = async (popupOverlay, popupElement) => {
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

        // Set properties for popup
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
      const vectorLayer = new VectorLayer({
        source: clusterSource,
        style: createClusterStyle(),
      })

      // Add layer to map
      map.value.addLayer(vectorLayer)

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
  min-height: 400px; /* Ensure minimum height */
  min-width: 300px;  /* Ensure minimum width */
}
</style>

