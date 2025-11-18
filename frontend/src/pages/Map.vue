<template>
  <v-container
    fluid
    class="pa-0"
    style="height: calc(100vh - 64px)"
    @keydown.esc="selectedSite = null; selectedPaper = null">
    <v-row
      no-gutters
      class="fill-height">
      <!-- Papers Sidebar (Left) -->
      <v-col
        cols="12"
        md="3"
        class="fill-height sidebar sidebar-left">
        <v-card
          class="fill-height d-flex flex-column"
          elevation="4">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Papers</span>
            <div class="d-flex align-center gap-2">
              <v-btn
                icon
                size="small"
                variant="text"
                :loading="papersLoading"
                @click="refreshPapers">
                <v-icon>mdi-refresh</v-icon>
                <v-tooltip
                  activator="parent"
                  location="bottom">
                  Refresh papers
                </v-tooltip>
              </v-btn>
              <v-chip
                :color="selectedPaper ? 'primary' : 'default'"
                size="small">
                {{ totalPapers }} papers
              </v-chip>
            </div>
          </v-card-title>

          <v-divider />

          <!-- Filters -->
          <v-card-text class="flex-grow-0">
            <v-text-field
              v-model="paperSearchQuery"
              label="Search papers"
              prepend-inner-icon="mdi-magnify"
              clearable
              density="compact"
              variant="outlined"
              hide-details
              class="mb-3" />

            <v-select
              v-model="paperFilterType"
              :items="paperFilterOptions"
              label="Filter papers"
              prepend-inner-icon="mdi-filter"
              density="compact"
              variant="outlined"
              hide-details />
          </v-card-text>

          <v-divider />

          <!-- Papers List -->
          <v-card-text class="flex-grow-1 overflow-y-auto pa-0">
            <v-list
              density="compact"
              v-if="filteredPapers.length > 0">
              <v-list-item
                v-for="paper in filteredPapers"
                :key="paper.id"
                :active="selectedPaper?.id === paper.id"
                @click="handlePaperClick(paper)"
                class="cursor-pointer">
                <template #prepend>
                  <v-avatar
                    color="primary"
                    size="32">
                    <v-icon
                      size="16"
                      color="white">
                      mdi-file-document
                    </v-icon>
                  </v-avatar>
                </template>

                <v-list-item-title class="text-wrap">
                  {{ paper.title || 'Untitled Paper' }}
                </v-list-item-title>

                <v-list-item-subtitle class="text-wrap">
                  {{ formatPaperSubtitle(paper) }}
                </v-list-item-subtitle>

                <template #append>
                  <div class="d-flex flex-column align-end gap-1">
                    <v-chip
                      v-if="paper.study_sites && paper.study_sites.length > 0"
                      :color="getStudySitesColor(paper.study_sites)"
                      size="x-small"
                      @click.stop="showPaperStudySites(paper)">
                      <v-icon start size="x-small">mdi-map-marker</v-icon>
                      {{ paper.study_sites.length }}
                    </v-chip>
                    <v-chip
                      v-else
                      size="x-small"
                      color="default"
                      variant="outlined">
                      <v-icon size="x-small">mdi-minus</v-icon>
                    </v-chip>
                  </div>
                </template>
              </v-list-item>
            </v-list>

            <v-empty-state
              v-else
              icon="mdi-file-document-off"
              title="No papers found"
              text="Try adjusting your filters or sync your library" />
          </v-card-text>

          <v-divider />

          <!-- Actions -->
          <v-card-actions class="flex-grow-0">
            <v-btn
              v-if="selectedPaper"
              block
              variant="outlined"
              prepend-icon="mdi-close"
              @click="clearPaperSelection">
              Clear Selection
            </v-btn>
            <v-btn
              v-else
              block
              color="primary"
              prepend-icon="mdi-refresh"
              @click="refreshPapers"
              :loading="papersLoading">
              Refresh
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Map Section -->
      <v-col
        cols="12"
        md="6"
        class="fill-height">
        <StudySiteMap
          ref="mapComponent"
          :initial-center="[0, 20]"
          :initial-zoom="2"
          :sites="filteredSites"
          @site-selected="handleSiteSelected"
          @map-ready="handleMapReady" />
      </v-col>

      <!-- Study Sites Sidebar (Right) -->
      <v-col
        cols="12"
        md="3"
        class="fill-height sidebar sidebar-right">
        <v-card
          class="fill-height d-flex flex-column"
          elevation="4">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Study Sites</span>
            <div class="d-flex align-center gap-2">
              <v-btn
                icon
                size="small"
                variant="text"
                :loading="loading"
                @click="refreshSites">
                <v-icon>mdi-refresh</v-icon>
                <v-tooltip
                  activator="parent"
                  location="bottom">
                  Refresh study sites
                </v-tooltip>
              </v-btn>
              <v-chip
                :color="selectedSite ? 'primary' : 'default'"
                size="small">
                {{ totalSites }} sites
              </v-chip>
            </div>
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

          <!-- Info Banner -->
          <v-alert
            type="info"
            variant="tonal"
            density="compact"
            class="ma-3 mb-2">
            <div class="text-caption">
              <v-icon size="small" class="mr-1">mdi-information</v-icon>
              Study sites appear after extraction tasks complete. Click refresh to see new sites.
            </div>
          </v-alert>

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

    <!-- Paper Study Sites Dialog -->
    <v-dialog
      v-model="studySitesDialog"
      max-width="900"
      scrollable>
      <v-card v-if="dialogPaper">
        <v-card-title class="d-flex align-center justify-space-between">
          <div>
            <div class="text-h6">Study Sites</div>
            <div class="text-subtitle-2 text-medium-emphasis">{{ dialogPaper.title }}</div>
          </div>
          <v-btn
            icon="mdi-close"
            variant="text"
            @click="studySitesDialog = false" />
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-alert
            v-if="!dialogPaper.study_sites || dialogPaper.study_sites.length === 0"
            type="info"
            variant="tonal"
            class="mb-4">
            No study sites have been extracted for this paper yet.
          </v-alert>

          <v-list
            v-else
            lines="three"
            class="bg-transparent">
            <v-list-item
              v-for="(site, index) in dialogPaper.study_sites"
              :key="site.id"
              class="mb-3 pa-3"
              border
              rounded>
              <template #prepend>
                <v-avatar
                  :color="site.is_manual ? 'success' : 'info'"
                  size="48">
                  <v-icon
                    size="24"
                    color="white">
                    {{ site.is_manual ? 'mdi-account' : 'mdi-robot' }}
                  </v-icon>
                </v-avatar>
              </template>

              <v-list-item-title class="text-h6 mb-2">
                {{ site.name || `Study Site ${index + 1}` }}
              </v-list-item-title>

              <v-list-item-subtitle class="text-body-2">
                <div class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-map-marker</v-icon>
                  <strong>Location:</strong>
                  {{ site.location?.latitude?.toFixed(4) }}, {{ site.location?.longitude?.toFixed(4) }}
                </div>

                <div v-if="site.context" class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-text</v-icon>
                  <strong>Context:</strong>
                  <div class="mt-1 text-medium-emphasis context-text">
                    {{ site.context }}
                  </div>
                </div>

                <div class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-chart-line</v-icon>
                  <strong>Confidence:</strong>
                  {{ (site.confidence_score * 100).toFixed(1) }}%
                  <v-progress-linear
                    :model-value="site.confidence_score * 100"
                    :color="getConfidenceColor(site.confidence_score)"
                    height="6"
                    rounded
                    class="mt-1" />
                </div>

                <div class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-information</v-icon>
                  <strong>Method:</strong> {{ formatExtractionMethod(site.extraction_method) }}
                  <v-chip
                    :color="site.is_manual ? 'success' : 'info'"
                    size="x-small"
                    class="ml-2">
                    {{ site.is_manual ? 'Manual' : 'Automatic' }}
                  </v-chip>
                </div>

                <div v-if="site.section" class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-book-open-page-variant</v-icon>
                  <strong>Section:</strong> {{ site.section }}
                </div>
              </v-list-item-subtitle>

              <template #append>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  @click="panToStudySite(site)">
                  <v-icon>mdi-crosshairs-gps</v-icon>
                  <v-tooltip activator="parent" location="top">
                    View on Map
                  </v-tooltip>
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>

        <v-divider />

        <v-card-actions>
          <v-spacer />
          <v-btn @click="studySitesDialog = false">Close</v-btn>
          <v-btn
            v-if="dialogPaper.study_sites && dialogPaper.study_sites.length > 0"
            color="primary"
            @click="filterByDialogPaper">
            Show on Map
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useStudySitesStore, type StudySiteWithItem } from '../stores/studySites'
import { useZoteroStore } from '../stores/zotero'
import StudySiteMap from '../components/maps/StudySiteMap.vue'

// Route
const route = useRoute()

// Stores
const studySitesStore = useStudySitesStore()
const zoteroStore = useZoteroStore()
const { studySites, loading } = storeToRefs(studySitesStore)
const { items, loading: papersLoading } = storeToRefs(zoteroStore)

// State - Study Sites
const selectedSite = ref<StudySiteWithItem | null>(null)
const searchQuery = ref('')
const filterType = ref('all')
const mapReady = ref(false)
const mapComponent = ref<InstanceType<typeof StudySiteMap> | null>(null)

// State - Papers
const selectedPaper = ref<any | null>(null)
const paperSearchQuery = ref('')
const paperFilterType = ref('all')
const studySitesDialog = ref(false)
const dialogPaper = ref<any | null>(null)

// Filter options - Study Sites
const filterOptions = [
  { title: 'All Sites', value: 'all' },
  { title: 'Manual Only', value: 'manual' },
  { title: 'Automatic Only', value: 'automatic' },
]

// Filter options - Papers
const paperFilterOptions = [
  { title: 'All Papers', value: 'all' },
  { title: 'With Study Sites', value: 'with_sites' },
  { title: 'Without Study Sites', value: 'without_sites' },
]

// Computed - Papers
const papers = computed(() => items.value?.data || [])

const totalPapers = computed(() => papers.value.length)

const filteredPapers = computed(() => {
  let result = papers.value

  // Filter by type
  if (paperFilterType.value === 'with_sites') {
    result = result.filter((p: any) => p.study_sites && p.study_sites.length > 0)
  } else if (paperFilterType.value === 'without_sites') {
    result = result.filter((p: any) => !p.study_sites || p.study_sites.length === 0)
  }

  // Filter by search query
  if (paperSearchQuery.value) {
    const query = paperSearchQuery.value.toLowerCase()
    result = result.filter(
      (p: any) =>
        p.title?.toLowerCase().includes(query) ||
        p.abstractNote?.toLowerCase().includes(query) ||
        p.publicationTitle?.toLowerCase().includes(query),
    )
  }

  return result
})

// Computed - Study Sites
const totalSites = computed(() => studySites.value.length)

const filteredSites = computed(() => {
  let sites = studySites.value

  // Filter by selected paper
  if (selectedPaper.value) {
    sites = sites.filter((s) => s.item_id === selectedPaper.value.id)
  }

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
  if (selectedSite.value.id === site.id) {
    selectedSite.value = null
    return
  }
  selectedSite.value = site
}

/**
 * Handle site click from list - Pan map to location
 */
const handleSiteClick = (site: StudySiteWithItem) => {
  if (!site) {
    console.warn('Invalid site clicked')
    return
  }

  // Toggle selection
  if (selectedSite.value?.id === site.id) {
    selectedSite.value = null
  } else {
    selectedSite.value = site
  }

  if (!site.location) {
    console.warn(`Site "${site.name}" has no location object`)
    return
  }

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

/**
 * Refresh sites (alias for refreshData)
 */
const refreshSites = refreshData

/**
 * Refresh papers
 */
const refreshPapers = async () => {
  await zoteroStore.fetchItems()
}

/**
 * Handle paper click - Filter study sites by paper
 */
const handlePaperClick = (paper: any) => {
  if (selectedPaper.value?.id === paper.id) {
    // Toggle off if already selected
    selectedPaper.value = null
  } else {
    selectedPaper.value = paper
  }
}

/**
 * Clear paper selection
 */
const clearPaperSelection = () => {
  selectedPaper.value = null
}

/**
 * Show paper study sites dialog
 */
const showPaperStudySites = (paper: any) => {
  dialogPaper.value = paper
  studySitesDialog.value = true
}

/**
 * Filter by dialog paper and close dialog
 */
const filterByDialogPaper = () => {
  selectedPaper.value = dialogPaper.value
  studySitesDialog.value = false
}

/**
 * Pan to study site from dialog
 */
const panToStudySite = (site: any) => {
  studySitesDialog.value = false

  if (!mapComponent.value) {
    console.warn('Map component not initialized yet')
    return
  }

  if (!site.location?.latitude || !site.location?.longitude) {
    console.warn(`Site "${site.name}" has no valid location data`)
    return
  }

  // Pan to site location with zoom level 12
  mapComponent.value.panTo(
    site.location.latitude,
    site.location.longitude,
    12,
    1500,
  )

  // Select the site
  selectedSite.value = site
}

/**
 * Format paper subtitle (author and year)
 */
const formatPaperSubtitle = (paper: any): string => {
  const parts: string[] = []

  if (paper.publicationTitle) {
    parts.push(paper.publicationTitle)
  }

  if (paper.date) {
    const year = new Date(paper.date).getFullYear()
    if (!isNaN(year)) {
      parts.push(year.toString())
    }
  }

  return parts.length > 0 ? parts.join(' • ') : 'No publication info'
}

/**
 * Get study sites color based on manual/auto
 */
const getStudySitesColor = (studySites: any[]): string => {
  if (!studySites || studySites.length === 0) return 'default'

  const hasManual = studySites.some((site) => site.is_manual)
  return hasManual ? 'success' : 'info'
}

/**
 * Get confidence color
 */
const getConfidenceColor = (score: number): string => {
  if (score >= 0.8) return 'success'
  if (score >= 0.5) return 'warning'
  return 'error'
}

/**
 * Format extraction method
 */
const formatExtractionMethod = (method: string): string => {
  if (!method) return 'Unknown'

  // Convert snake_case to Title Case
  return method
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

// Lifecycle
onMounted(async () => {
  await Promise.all([
    studySitesStore.fetchAllStudySites(),
    zoteroStore.fetchItems(),
  ])

  // Read query params for initial item selection
  if (route.query.itemTitle) {
    searchQuery.value = route.query.itemTitle as string
  }
})

watch(
  () => route.query.itemTitle,
  (newVal) => {
    if (newVal) {
      searchQuery.value = newVal as string
    }
  },
)

// Watch for paper selection changes and fit map to filtered sites
watch(
  () => selectedPaper.value,
  (newVal) => {
    // Wait for the map to update markers, then fit to them
    setTimeout(() => {
      if (mapComponent.value && filteredSites.value.length > 0) {
        mapComponent.value.fitToMarkers()
      }
    }, 300)
  },
)
</script>

<style scoped>
.fill-height {
  height: 100%;
}

.cursor-pointer {
  cursor: pointer;
}

.sidebar-left {
  border-right: 1px solid rgba(0, 0, 0, 0.12);
}

.sidebar-right {
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

/* Context text styling */
.context-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  padding: 8px;
  background-color: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
  font-style: italic;
}

/* Gap utility for flex items */
.gap-1 {
  gap: 4px;
}

.gap-2 {
  gap: 8px;
}
</style>
