<template>
  <div class="map-container">
    <LMap
      v-model:zoom="zoom"
      v-model:center="center"
      :use-global-leaflet="false"
      @ready="onMapReady"
      class="map"
    >
      <LTileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
        layer-type="base"
        name="OpenStreetMap"
      />
      
      <!-- Paper location markers -->
      <LMarkerClusterGroup v-if="papers.length > 0">
        <LMarker
          v-for="(paper, index) in papersWithCoordinates"
          :key="`paper-${paper.id}-${index}`"
          :lat-lng="[paper.latitude, paper.longitude]"
          @click="selectPaper(paper)"
        >
          <LPopup>
            <div class="popup-content">
              <h3>{{ paper.title }}</h3>
              <p v-if="paper.authors"><strong>Authors:</strong> {{ paper.authors }}</p>
              <p v-if="paper.journal"><strong>Journal:</strong> {{ paper.journal }}</p>
              <p><strong>Locations:</strong> {{ paper.locationCount }}</p>
              <button @click="viewPaperDetails(paper.id)" class="btn btn-primary btn-sm">
                View Details
              </button>
            </div>
          </LPopup>
        </LMarker>
      </LMarkerClusterGroup>
      
      <!-- Map controls -->
      <LControl position="topright">
        <div class="map-controls">
          <button @click="fitToMarkers" class="btn btn-secondary btn-sm">
            Fit All
          </button>
          <button @click="resetView" class="btn btn-secondary btn-sm">
            Reset View
          </button>
        </div>
      </LControl>
    </LMap>
    
    <!-- Map statistics -->
    <div class="map-stats">
      <div class="stat">
        <span class="stat-value">{{ papers.length }}</span>
        <span class="stat-label">Papers</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ papersWithCoordinates.length }}</span>
        <span class="stat-label">With Locations</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ totalLocations }}</span>
        <span class="stat-label">Total Locations</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  LMap,
  LTileLayer,
  LMarker,
  LPopup,
  LControl,
  LMarkerClusterGroup,
} from '@vue-leaflet/vue-leaflet'

const props = defineProps({
  papers: {
    type: Array,
    default: () => []
  },
  initialCenter: {
    type: Array,
    default: () => [51.505, -0.09]
  },
  initialZoom: {
    type: Number,
    default: 2
  }
})

const emit = defineEmits(['paper-selected', 'map-ready'])

const router = useRouter()
const map = ref(null)
const center = ref(props.initialCenter)
const zoom = ref(props.initialZoom)

// Computed properties
const papersWithCoordinates = computed(() => {
  return props.papers
    .filter(paper => paper.locations && paper.locations.length > 0)
    .flatMap(paper => 
      paper.locations
        .filter(loc => loc.latitude && loc.longitude)
        .map(location => ({
          ...paper,
          latitude: location.latitude,
          longitude: location.longitude,
          locationName: location.location_name,
          locationCount: paper.locations.length
        }))
    )
})

const totalLocations = computed(() => {
  return props.papers.reduce((total, paper) => {
    return total + (paper.locations ? paper.locations.length : 0)
  }, 0)
})

// Methods
function onMapReady(mapInstance) {
  map.value = mapInstance
  emit('map-ready', mapInstance)
  
  // Fit to markers if we have data
  if (papersWithCoordinates.value.length > 0) {
    fitToMarkers()
  }
}

function selectPaper(paper) {
  emit('paper-selected', paper)
}

function viewPaperDetails(paperId) {
  router.push(`/papers/${paperId}`)
}

function fitToMarkers() {
  if (!map.value || papersWithCoordinates.value.length === 0) return
  
  const group = new L.featureGroup(
    papersWithCoordinates.value.map(paper => 
      L.marker([paper.latitude, paper.longitude])
    )
  )
  
  map.value.fitBounds(group.getBounds().pad(0.1))
}

function resetView() {
  center.value = props.initialCenter
  zoom.value = props.initialZoom
}

// Watch for papers changes
watch(() => props.papers, (newPapers) => {
  if (newPapers.length > 0 && papersWithCoordinates.value.length > 0) {
    // Auto-fit when papers are loaded
    setTimeout(fitToMarkers, 500)
  }
}, { immediate: true })

onMounted(() => {
  // Import Leaflet markercluster if not already loaded
  import('leaflet.markercluster')
})
</script>

<style scoped>
.map-container {
  position: relative;
  height: 100%;
  width: 100%;
}

.map {
  height: 100%;
  width: 100%;
}

.map-controls {
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
  border-radius: 5px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}

.map-stats {
  position: absolute;
  bottom: 20px;
  left: 20px;
  display: flex;
  gap: 15px;
  background: rgba(255, 255, 255, 0.9);
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.2);
  z-index: 1000;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #2c3e50;
}

.stat-label {
  font-size: 0.8rem;
  color: #7f8c8d;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.popup-content {
  max-width: 300px;
}

.popup-content h3 {
  margin: 0 0 10px 0;
  font-size: 1.1rem;
  color: #2c3e50;
}

.popup-content p {
  margin: 5px 0;
  font-size: 0.9rem;
  color: #34495e;
}

.btn {
  padding: 5px 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  text-decoration: none;
  display: inline-block;
  text-align: center;
}

.btn-primary {
  background-color: #3498db;
  color: white;
}

.btn-secondary {
  background-color: #95a5a6;
  color: white;
}

.btn-sm {
  padding: 3px 8px;
  font-size: 0.75rem;
}

.btn:hover {
  opacity: 0.8;
}
</style>
