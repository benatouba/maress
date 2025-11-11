<template>
  <v-container
    fluid
    class="pa-0"
    style="height: calc(100vh - 64px)">
    <v-row
      no-gutters
      class="fill-height">
      <!-- Map Section -->
      <v-col
        cols="12"
        md="9"
        class="fill-height">
        <StudySiteMap
          ref="mapComponent"
          :initial-center="[0, 20]"
          :initial-zoom="2"
          @site-selected="handleSiteSelected"
          @map-ready="handleMapReady" />
      </v-col>

      <!-- Sidebar Section -->
      <v-col
        cols="12"
        md="3"
        class="fill-height sidebar">
        <v-card
          class="fill-height d-flex flex-column"
          elevation="4">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Study Sites</span>
            <v-chip
              :color="selectedSite ? 'primary' : 'default'"
              size="small">
              {{ totalSites }} sites
            </v-chip>
          </v-card-title>

          <v-divider />

          <!-- Filters -->
          <v-card-text class="flex-grow-0">
            <v-text-field
              v-model="searchQuery"
              label="Search sites or papers"
              prepend-inner-icon="mdi-magnify"
              clearable
              density="compact"
              variant="outlined"
              hide-details
              class="mb-3" />

            <v-select
              v-model="filterType"
              :items="filterOptions"
              label="Filter by type"
              prepend-inner-icon="mdi-filter"
              density="compact"
              variant="outlined"
              hide-details />
          </v-card-text>

          <v-divider />

          <!-- Sites List -->
          <v-card-text class="flex-grow-1 overflow-y-auto pa-0">
            <v-list
              density="compact"
              v-if="filteredSites.length > 0">
              <v-list-item
                v-for="site in filteredSites"
                :key="site.id"
                :active="selectedSite?.id === site.id"
                @click="handleSiteClick(site)"
                class="cursor-pointer">
                <template #prepend>
                  <v-avatar
                    :color="site.is_manual ? 'success' : 'info'"
                    size="32">
                    <v-icon
                      size="16"
                      color="white">
                      {{ site.is_manual ? 'mdi-account' : 'mdi-robot' }}
                    </v-icon>
                  </v-avatar>
                </template>

                <v-list-item-title class="text-wrap">
                  {{ site.name || 'Unnamed Site' }}
                </v-list-item-title>

                <v-list-item-subtitle class="text-wrap">
                  {{ site.item_title || 'Unknown Paper' }}
                </v-list-item-subtitle>

                <template #append>
                  <v-chip
                    size="x-small"
                    :color="site.is_manual ? 'success' : 'info'">
                    {{ site.is_manual ? 'Manual' : 'Auto' }}
                  </v-chip>
                </template>
              </v-list-item>
            </v-list>

            <v-empty-state
              v-else
              icon="mdi-map-marker-off"
              title="No study sites found"
              text="Try adjusting your filters or create a new study site by clicking on the map" />
          </v-card-text>

          <v-divider />

          <!-- Actions -->
          <v-card-actions class="flex-grow-0">
            <v-btn
              block
              color="primary"
              prepend-icon="mdi-refresh"
              @click="refreshData"
              :loading="loading">
              Refresh
            </v-btn>
          </v-card-actions>

          <!-- Legend -->
          <v-card-text class="flex-grow-0 pt-2 pb-3">
            <div class="text-caption text-medium-emphasis mb-2">Legend:</div>
            <div class="d-flex align-center mb-1">
              <v-icon
                color="success"
                size="small"
                class="mr-2"
                >mdi-circle</v-icon
              >
              <span class="text-caption">Manual (Human-created)</span>
            </div>
            <div class="d-flex align-center">
              <v-icon
                color="info"
                size="small"
                class="mr-2"
                >mdi-circle</v-icon
              >
              <span class="text-caption">Automatic (Algorithm-extracted)</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useStudySitesStore, type StudySiteWithItem } from '../stores/studySites'
import StudySiteMap from '../components/maps/StudySiteMap.vue'

// Store
const studySitesStore = useStudySitesStore()
const { studySites, loading } = storeToRefs(studySitesStore)

// State
const selectedSite = ref<StudySiteWithItem | null>(null)
const searchQuery = ref('')
const filterType = ref('all')
const mapReady = ref(false)
const mapComponent = ref<InstanceType<typeof StudySiteMap> | null>(null)

// Filter options
const filterOptions = [
  { title: 'All Sites', value: 'all' },
  { title: 'Manual Only', value: 'manual' },
  { title: 'Automatic Only', value: 'automatic' },
]

// Computed
const totalSites = computed(() => studySites.value.length)

const filteredSites = computed(() => {
  let sites = studySites.value

  // Filter by type
  if (filterType.value === 'manual') {
    sites = sites.filter((s) => s.is_manual)
  } else if (filterType.value === 'automatic') {
    sites = sites.filter((s) => !s.is_manual)
  }

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    sites = sites.filter(
      (s) =>
        s.name?.toLowerCase().includes(query) ||
        s.item_title?.toLowerCase().includes(query) ||
        s.context?.toLowerCase().includes(query),
    )
  }

  return sites
})

/**
 * Handle site selection from map
 */
const handleSiteSelected = (site: StudySiteWithItem) => {
  selectedSite.value = site
}

/**
 * Handle site click from list - Pan map to location
 */
const handleSiteClick = (site: StudySiteWithItem) => {
  selectedSite.value = site

  // Check if map component is ready
  if (!mapComponent.value) {
    console.warn('Map component not initialized yet')
    return
  }

  // Check if site has valid location data
  if (!site.location?.latitude || !site.location?.longitude) {
    console.warn(`Site "${site.name}" has no valid location data`)
    return
  }

  // Pan to site location with zoom level 12
  mapComponent.value.panTo(
    site.location.latitude,
    site.location.longitude,
    12, // zoom level
    1500, // animation duration in milliseconds
  )
}

/**
 * Handle map ready
 */
const handleMapReady = (map: any) => {
  mapReady.value = true
  console.log('Map ready:', map)
}

/**
 * Refresh data
 */
const refreshData = async () => {
  await studySitesStore.fetchAllStudySites()
}

// Lifecycle
onMounted(async () => {
  await studySitesStore.fetchAllStudySites()
})
</script>

<style scoped>
.fill-height {
  height: 100%;
}

.cursor-pointer {
  cursor: pointer;
}

.sidebar {
  border-left: 1px solid rgba(0, 0, 0, 0.12);
}

.overflow-y-auto {
  overflow-y: auto;
}

/* Custom scrollbar for the list */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
