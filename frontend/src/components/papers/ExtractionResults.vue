<template>
  <v-card>
    <v-card-title>
      <div class="d-flex align-center justify-space-between">
        <div>
          <span>Extraction Results</span>
          <v-chip v-if="results" size="small" class="ml-2">
            {{ results.count }} candidate{{ results.count !== 1 ? 's' : '' }} found
          </v-chip>
          <v-chip v-if="results && results.top_10_count > 0" color="success" size="small" class="ml-2">
            {{ results.top_10_count }} saved
          </v-chip>
        </div>
        <v-btn icon variant="text" @click="$emit('close')">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </div>
    </v-card-title>

    <v-card-subtitle v-if="results">
      <div class="d-flex align-center gap-2 mt-2">
        <v-icon size="small" color="info">mdi-information-outline</v-icon>
        <span class="text-caption">
          Shows all {{ results.count }} location candidates detected during extraction.
          The top {{ results.top_10_count }} with highest confidence were saved as study sites.
        </span>
      </div>
    </v-card-subtitle>

    <v-divider />

    <v-card-text>
      <!-- Loading State -->
      <div v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate color="primary" size="48" />
        <p class="text-body-2 text-medium-emphasis mt-4">Loading extraction results...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="text-center py-8">
        <v-icon size="64" color="error" class="mb-4">mdi-alert-circle-outline</v-icon>
        <div class="text-h6 text-error">{{ error }}</div>
        <v-btn color="primary" class="mt-4" @click="loadResults">
          Retry
        </v-btn>
      </div>

      <!-- Empty State -->
      <div v-else-if="!results || results.count === 0" class="text-center py-8">
        <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-map-marker-off-outline</v-icon>
        <div class="text-h6 text-medium-emphasis">No extraction results found</div>
        <p class="text-body-2 text-medium-emphasis mt-2">
          This item hasn't been processed yet or no coordinates were detected.
        </p>
      </div>

      <!-- Results Table -->
      <div v-else>
        <!-- Filters -->
        <v-row class="mb-4">
          <v-col cols="12" sm="6" md="3">
            <v-select
              v-model="filterSaved"
              :items="[
                { title: 'All Results', value: 'all' },
                { title: 'Saved Only', value: 'saved' },
                { title: 'Not Saved', value: 'not_saved' },
              ]"
              label="Filter by Status"
              density="compact"
              hide-details
            />
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-select
              v-model="filterSection"
              :items="sectionOptions"
              label="Filter by Section"
              density="compact"
              hide-details
            />
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-text-field
              v-model="searchQuery"
              label="Search context"
              prepend-inner-icon="mdi-magnify"
              density="compact"
              hide-details
              clearable
            />
          </v-col>

          <v-col cols="12" sm="6" md="3">
            <v-slider
              v-model="minConfidence"
              label="Min Confidence"
              :min="0"
              :max="1"
              :step="0.05"
              thumb-label
              hide-details
            >
              <template #prepend>
                <v-icon>mdi-filter-variant</v-icon>
              </template>
            </v-slider>
          </v-col>
        </v-row>

        <!-- Data Table -->
        <v-data-table
          :items="filteredResults"
          :headers="headers"
          :items-per-page="10"
          :items-per-page-options="[10, 25, 50, 100]"
          item-value="id"
        >
          <!-- Rank Column -->
          <template #item.rank="{ item }">
            <v-chip
              :color="item.rank <= 10 ? 'success' : 'default'"
              size="small"
              :variant="item.rank <= 10 ? 'flat' : 'outlined'"
            >
              #{{ item.rank }}
            </v-chip>
          </template>

          <!-- Name Column -->
          <template #item.name="{ item }">
            <div class="text-truncate" style="max-width: 200px">
              {{ item.name || 'Unnamed' }}
            </div>
          </template>

          <!-- Coordinates Column -->
          <template #item.coordinates="{ item }">
            <code class="text-caption">
              {{ item.latitude.toFixed(4) }}, {{ item.longitude.toFixed(4) }}
            </code>
          </template>

          <!-- Confidence Column -->
          <template #item.confidence_score="{ item }">
            <div class="d-flex align-center" style="min-width: 120px">
              <v-progress-linear
                :model-value="item.confidence_score * 100"
                :color="getConfidenceColor(item.confidence_score)"
                height="8"
                rounded
                class="flex-grow-1"
              />
              <span class="ml-2 text-caption">
                {{ (item.confidence_score * 100).toFixed(0) }}%
              </span>
            </div>
          </template>

          <!-- Section Column -->
          <template #item.section="{ item }">
            <v-chip size="small" variant="tonal">
              {{ formatSection(item.section) }}
            </v-chip>
          </template>

          <!-- Method Column -->
          <template #item.extraction_method="{ item }">
            <v-chip size="x-small" variant="outlined">
              {{ formatMethod(item.extraction_method) }}
            </v-chip>
          </template>

          <!-- Saved Column -->
          <template #item.is_saved="{ item }">
            <v-icon
              :color="item.is_saved ? 'success' : 'grey'"
              :icon="item.is_saved ? 'mdi-check-circle' : 'mdi-circle-outline'"
            />
          </template>

          <!-- Context Column -->
          <template #item.context="{ item }">
            <v-tooltip location="top" max-width="400">
              <template #activator="{ props }">
                <div v-bind="props" class="text-truncate" style="max-width: 300px; cursor: help">
                  {{ item.context || 'No context' }}
                </div>
              </template>
              <span>{{ item.context || 'No context' }}</span>
            </v-tooltip>
          </template>

          <!-- Actions Column -->
          <template #item.actions="{ item }">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="viewOnMap(item)"
            >
              <v-icon>mdi-map-marker</v-icon>
            </v-btn>
          </template>
        </v-data-table>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useZoteroStore } from '@/stores/zotero'

interface ExtractionResult {
  id: string
  item_id: string
  name: string | null
  latitude: number
  longitude: number
  context: string | null
  confidence_score: number
  extraction_method: string
  source_type: string
  section: string
  rank: number
  is_saved: boolean
  created_at: string
}

interface Props {
  itemId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  viewOnMap: [result: ExtractionResult]
}>()

const zoteroStore = useZoteroStore()

const loading = ref(false)
const error = ref<string | null>(null)
const results = ref<{
  data: ExtractionResult[]
  count: number
  top_10_count: number
} | null>(null)

// Filters
const filterSaved = ref<'all' | 'saved' | 'not_saved'>('all')
const filterSection = ref<string>('all')
const searchQuery = ref<string>('')
const minConfidence = ref<number>(0)

const headers = [
  { title: 'Rank', key: 'rank', sortable: true, width: 80 },
  { title: 'Name', key: 'name', sortable: true },
  { title: 'Coordinates', key: 'coordinates', sortable: false },
  { title: 'Confidence', key: 'confidence_score', sortable: true },
  { title: 'Section', key: 'section', sortable: true },
  { title: 'Method', key: 'extraction_method', sortable: true },
  { title: 'Saved', key: 'is_saved', sortable: true, width: 80 },
  { title: 'Context', key: 'context', sortable: false },
  { title: '', key: 'actions', sortable: false, width: 60 },
]

const sectionOptions = computed(() => {
  if (!results.value) return [{ title: 'All Sections', value: 'all' }]

  const sections = new Set(results.value.data.map((r) => r.section))
  return [
    { title: 'All Sections', value: 'all' },
    ...Array.from(sections).map((s) => ({
      title: formatSection(s),
      value: s,
    })),
  ]
})

const filteredResults = computed(() => {
  if (!results.value) return []

  return results.value.data.filter((result) => {
    // Filter by saved status
    if (filterSaved.value === 'saved' && !result.is_saved) return false
    if (filterSaved.value === 'not_saved' && result.is_saved) return false

    // Filter by section
    if (filterSection.value !== 'all' && result.section !== filterSection.value) return false

    // Filter by confidence
    if (result.confidence_score < minConfidence.value) return false

    // Search in context
    if (searchQuery.value && result.context) {
      const query = searchQuery.value.toLowerCase()
      const context = result.context.toLowerCase()
      if (!context.includes(query)) return false
    }

    return true
  })
})

const getConfidenceColor = (confidence: number): string => {
  if (confidence >= 0.9) return 'success'
  if (confidence >= 0.75) return 'primary'
  if (confidence >= 0.5) return 'warning'
  return 'error'
}

const formatSection = (section: string): string => {
  return section
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

const formatMethod = (method: string): string => {
  const methodMap: Record<string, string> = {
    COORDINATE: 'Regex',
    GPE: 'Geocoded',
    LOC: 'Geocoded',
    SPATIAL_RELATION: 'Spatial',
    TABLE_PARSING: 'Table',
    MANUAL: 'Manual',
  }
  return methodMap[method] || method
}

const viewOnMap = (result: ExtractionResult) => {
  emit('viewOnMap', result)
}

const loadResults = async () => {
  loading.value = true
  error.value = null

  try {
    const data = await zoteroStore.getExtractionResults(props.itemId)
    if (data) {
      results.value = data
    } else {
      error.value = 'Failed to load extraction results'
    }
  } catch (err) {
    console.error('Error loading extraction results:', err)
    error.value = 'An error occurred while loading extraction results'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadResults()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
