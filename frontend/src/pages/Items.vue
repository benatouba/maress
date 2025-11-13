<template>
  <v-container fluid>
    <!-- Header -->
    <v-row class="mb-4">
      <v-col cols="12" md="6">
        <h2 class="text-h4 font-weight-bold">Research Library</h2>
        <p class="text-subtitle-1 text-medium-emphasis">
          Manage your research papers and study sites
        </p>
      </v-col>
      <v-col cols="12" md="6" class="d-flex justify-end align-center flex-wrap">
        <v-switch
          v-model="forceReload"
          color="warning"
          density="compact"
          hide-details
          class="mr-4"
          label="Force Reload"
          :disabled="isProcessing"
        />
        <v-btn
          color="primary"
          prepend-icon="mdi-sync"
          @click="handleSync"
          :loading="syncing || isProcessing"
          :disabled="isProcessing && !syncing || selectedCollectionIndex === -1"
          class="mr-2"
        >
          {{ syncButtonText }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-download"
          @click="handleDownloadAttachments"
          :loading="downloading || isProcessing"
          :disabled="isProcessing && !downloading"
          class="mr-2"
        >
          {{ downloading ? 'Downloading...' : 'Download Files' }}
        </v-btn>
        <v-btn
          v-if="hasSelectedItems"
          color="error"
          prepend-icon="mdi-close"
          @click="clearSelection"
          variant="outlined"
          :disabled="isProcessing"
          class="mr-2"
        >
          Clear ({{ selectedItems.length }})
        </v-btn>
        <v-btn
          :color="hasSelectedItems ? 'success' : 'accent'"
          prepend-icon="mdi-map-marker-plus"
          @click="handleExtractAll"
          :loading="isProcessing"
          :disabled="isProcessing"
          class="mr-2"
        >
          {{ hasSelectedItems ? `Extract ${selectedItems.length} Selected` : 'Extract All Sites' }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-refresh"
          @click="handleRefresh"
          :loading="isProcessing"
          :disabled="isProcessing"
        >
          Refresh
        </v-btn>
      </v-col>
    </v-row>

    <!-- Zotero Collections -->
    <v-card class="mb-4" elevation="2" v-if="zoteroCollections.length > 0">
      <v-card-title class="text-subtitle-1">
        <v-icon class="mr-2">mdi-folder-multiple</v-icon>
        Zotero Collections
      </v-card-title>
      <v-card-text>
        <v-chip-group
          v-model="selectedCollectionIndex"
          selected-class="text-primary"
          mandatory
          column
        >
          <v-chip
            value="-1"
            prepend-icon="mdi-library"
            variant="outlined"
          >
            All Library
          </v-chip>
          <v-chip
            v-for="(collection, index) in zoteroCollections"
            :key="collection.key"
            :value="index"
            prepend-icon="mdi-folder"
            variant="outlined"
          >
            {{ collection.name }}
          </v-chip>
        </v-chip-group>
      </v-card-text>
    </v-card>

    <!-- Filters and Search -->
    <v-card class="mb-4" elevation="2">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="search"
              label="Search papers"
              prepend-inner-icon="mdi-magnify"
              clearable
              density="compact"
              variant="outlined"
              hide-details
              placeholder="Title, authors, DOI..."
              @update:model-value="debouncedSearch"
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="filterType"
              :items="itemTypeOptions"
              label="Item Type"
              prepend-inner-icon="mdi-filter"
              clearable
              density="compact"
              variant="outlined"
              hide-details
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="filterStudySites"
              :items="studySiteOptions"
              label="Study Sites"
              prepend-inner-icon="mdi-map-marker"
              clearable
              density="compact"
              variant="outlined"
              hide-details
            />
          </v-col>
          <v-col cols="12" md="2" class="d-flex align-center">
            <v-btn
              block
              color="secondary"
              variant="outlined"
              @click="clearFilters"
              :disabled="!hasActiveFilters"
            >
              Clear Filters
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Download Progress Banner -->
    <v-alert
      v-if="downloading"
      type="info"
      variant="tonal"
      class="mb-4"
      prominent
      border="start"
    >
      <template #prepend>
        <v-progress-circular
          v-if="downloadProgress && downloadProgress.total > 0"
          :model-value="(downloadProgress.current / downloadProgress.total) * 100"
          size="24"
          width="3"
        />
        <v-progress-circular
          v-else
          indeterminate
          size="24"
          width="3"
        />
      </template>
      <v-alert-title>Downloading Attachments</v-alert-title>
      <div v-if="downloadProgress && downloadProgress.total > 0">
        Processing item {{ downloadProgress.current }} of {{ downloadProgress.total }}
        <br />
        <span class="text-caption">
          Downloaded: {{ downloadProgress.downloaded }} | Skipped: {{ downloadProgress.skipped }} | Failed: {{ downloadProgress.failed }}
        </span>
        <br />
        <span class="text-caption text-medium-emphasis">
          The table will update automatically as attachments are found.
        </span>
      </div>
      <div v-else>
        Starting download... The table will update automatically as attachments are found.
      </div>
    </v-alert>

    <!-- Data Table -->
    <v-card elevation="2">
      <v-data-table
        v-model:page="page"
        v-model:items-per-page="itemsPerPage"
        v-model:sort-by="sortBy"
        v-model="selectedItems"
        :headers="headers"
        :items="filteredItems"
        :loading="loading && !downloading"
        :items-length="totalItems"
        :search="search"
        item-value="id"
        show-select
        class="elevation-0"
        hover
        @click:row="handleRowClick"
      >
        <!-- Title with attachment indicator -->
        <template #item.title="{ item }">
          <div class="d-flex align-center">
            <v-icon
              v-if="item.attachment"
              color="primary"
              size="small"
              class="mr-2"
              @click.stop="viewAttachment(item.attachment)"
            >
              mdi-paperclip
            </v-icon>
            <span class="text-body-2 font-weight-medium">
              {{ item.title || 'Untitled' }}
            </span>
          </div>
        </template>

        <!-- Abstract with truncation -->
        <template #item.abstractNote="{ item }">
          <div class="truncate-text" style="max-width: 500px;" :title="item.abstractNote">
            {{ item.abstractNote }}
          </div>
        </template>

        <!-- Study Sites Count -->
        <template #item.study_sites_count="{ item }">
          <v-chip
            v-if="item.study_sites && item.study_sites.length > 0"
            :color="getStudySitesColor(item.study_sites)"
            size="small"
            @click.stop="viewOnMap(item)"
          >
            <v-icon start size="small">mdi-map-marker</v-icon>
            {{ item.study_sites.length }}
          </v-chip>
          <span v-else class="text-medium-emphasis">—</span>
        </template>

        <!-- Date formatting -->
        <template #item.date="{ item }">
          <span class="text-body-2">
            {{ formatDate(item.date) }}
          </span>
        </template>

        <!-- DOI with link -->
        <template #item.doi="{ item }">
          <v-btn
            v-if="item.doi"
            icon
            size="small"
            variant="text"
            @click.stop="openDoiLink(item.doi)"
          >
            <v-icon size="small">mdi-open-in-new</v-icon>
          </v-btn>
        </template>

        <!-- URL with link -->
        <template #item.url="{ item }">
          <v-btn
            v-if="item.url"
            icon
            size="small"
            variant="text"
            @click.stop="openInNewTab(item.url)"
          >
            <v-icon size="small">mdi-link</v-icon>
          </v-btn>
        </template>

        <!-- Actions -->
        <template #item.actions="{ item }">
          <v-menu>
            <template #activator="{ props }">
              <v-btn
                icon
                size="small"
                variant="text"
                v-bind="props"
                @click.stop
              >
                <v-icon>mdi-dots-vertical</v-icon>
              </v-btn>
            </template>
            <v-list density="compact">
              <v-list-item @click="viewDetails(item)">
                <template #prepend>
                  <v-icon size="small">mdi-eye</v-icon>
                </template>
                <v-list-item-title>View Details</v-list-item-title>
              </v-list-item>
              <v-list-item @click="viewOnMap(item)" :disabled="!hasStudySites(item)">
                <template #prepend>
                  <v-icon size="small">mdi-map</v-icon>
                </template>
                <v-list-item-title>View on Map</v-list-item-title>
              </v-list-item>
              <v-list-item @click="viewExtractionResults(item)">
                <template #prepend>
                  <v-icon size="small">mdi-format-list-bulleted</v-icon>
                </template>
                <v-list-item-title>View Extraction Results</v-list-item-title>
              </v-list-item>
              <v-divider />
              <v-list-item @click="handleImportFile(item)">
                <template #prepend>
                  <v-icon size="small">mdi-download</v-icon>
                </template>
                <v-list-item-title>Download File from Zotero</v-list-item-title>
              </v-list-item>
              <v-list-item @click="handleExtractStudySites(item)">
                <template #prepend>
                  <v-icon size="small">mdi-map-marker-plus</v-icon>
                </template>
                <v-list-item-title>Extract Study Sites</v-list-item-title>
              </v-list-item>
              <v-divider />
              <v-list-item @click="handleEdit(item)">
                <template #prepend>
                  <v-icon size="small">mdi-pencil</v-icon>
                </template>
                <v-list-item-title>Edit</v-list-item-title>
              </v-list-item>
              <v-list-item @click="handleDelete(item)" class="text-error">
                <template #prepend>
                  <v-icon size="small" color="error">mdi-delete</v-icon>
                </template>
                <v-list-item-title>Delete</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
        </template>

        <!-- Bottom info -->
        <template #bottom>
          <div class="text-center pa-4">
            <v-pagination
              v-model="page"
              :length="pageCount"
              :total-visible="7"
            />
          </div>
        </template>
      </v-data-table>
    </v-card>

    <!-- Item Details Dialog -->
    <v-dialog v-model="detailsDialog" max-width="800">
      <v-card v-if="selectedItem">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>{{ selectedItem.title }}</span>
          <v-btn icon="mdi-close" variant="text" @click="detailsDialog = false" />
        </v-card-title>

        <v-divider />

        <v-card-text class="pt-4">
          <v-row>
            <v-col cols="12">
              <h3 class="text-h6 mb-2">Abstract</h3>
              <p class="text-body-2">{{ selectedItem.abstractNote || 'No abstract available' }}</p>
            </v-col>

            <v-col cols="12" md="6">
              <h3 class="text-h6 mb-2">Publication Details</h3>
              <v-list density="compact">
                <v-list-item v-if="selectedItem.publicationTitle">
                  <v-list-item-title>Journal</v-list-item-title>
                  <v-list-item-subtitle>{{ selectedItem.publicationTitle }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="selectedItem.date">
                  <v-list-item-title>Date</v-list-item-title>
                  <v-list-item-subtitle>{{ selectedItem.date }}</v-list-item-subtitle>
                </v-list-item>
                <v-list-item v-if="selectedItem.doi">
                  <v-list-item-title>DOI</v-list-item-title>
                  <v-list-item-subtitle>
                    <a :href="getDoiUrl(selectedItem.doi)" target="_blank" rel="noopener">
                      {{ selectedItem.doi }}
                    </a>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
            </v-col>

            <v-col cols="12" md="6">
              <h3 class="text-h6 mb-2">Study Sites</h3>
              <v-list v-if="selectedItem.study_sites && selectedItem.study_sites.length > 0" density="compact">
                <v-list-item v-for="site in selectedItem.study_sites" :key="site.id">
                  <template #prepend>
                    <v-icon :color="site.is_manual ? 'success' : 'info'">mdi-map-marker</v-icon>
                  </template>
                  <v-list-item-title>{{ site.name || 'Unnamed' }}</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ site.location.latitude?.toFixed(4) }}, {{ site.location.longitude?.toFixed(4) }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>
              <p v-else class="text-body-2 text-medium-emphasis">No study sites extracted yet</p>
            </v-col>
          </v-row>
        </v-card-text>

        <v-divider />

        <v-card-actions>
          <v-spacer />
          <v-btn @click="detailsDialog = false">Close</v-btn>
          <v-btn color="primary" @click="viewOnMap(selectedItem)" :disabled="!hasStudySites(selectedItem)">
            View on Map
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Extraction Results Dialog -->
    <v-dialog v-model="extractionResultsDialog" max-width="1200">
      <extraction-results
        v-if="extractionResultsDialog && selectedItem"
        :item-id="selectedItem.id"
        @close="extractionResultsDialog = false"
        @view-on-map="handleViewResultOnMap"
      />
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useZoteroStore } from '@/stores/zotero'
import { useNotificationStore } from '@/stores/notification'
import { useTaskStore } from '@/stores/tasks'
import { debounce } from 'lodash'
import ExtractionResults from '@/components/papers/ExtractionResults.vue'

// Stores
const router = useRouter()
const zoteroStore = useZoteroStore()
const notificationStore = useNotificationStore()
const taskStore = useTaskStore()
const { items, loading, syncing, downloading, downloadProgress, zoteroCollections } = storeToRefs(zoteroStore)

// State
const search = ref('')
const filterType = ref<string | null>(null)
const filterStudySites = ref<string | null>(null)
const page = ref(1)
const itemsPerPage = ref(25)
const selectedCollectionIndex = ref<number>(-1)
const sortBy = ref<any[]>([{ key: 'dateModified', order: 'desc' }])
const detailsDialog = ref(false)
const extractionResultsDialog = ref(false)
const selectedItem = ref<any>(null)
const forceReload = ref(false)
const selectedItems = ref<any[]>([])

// Filter options
const itemTypeOptions = [
  { title: 'All Types', value: null },
  { title: 'Journal Article', value: 'journalArticle' },
  { title: 'Book', value: 'book' },
  { title: 'Conference Paper', value: 'conferencePaper' },
]

const studySiteOptions = [
  { title: 'All Items', value: null },
  { title: 'With Study Sites', value: 'with' },
  { title: 'Without Study Sites', value: 'without' },
]

// Headers configuration
const headers = computed(() => [
  { key: 'title', title: 'Title', sortable: true, width: '25%' },
  { key: 'abstractNote', title: 'Abstract', sortable: false, width: '30%' },
  { key: 'publicationTitle', title: 'Journal', sortable: true },
  { key: 'date', title: 'Date', sortable: true, width: '100px' },
  { key: 'study_sites_count', title: 'Sites', sortable: false, align: 'center', width: '80px' },
  { key: 'doi', title: 'DOI', sortable: false, align: 'center', width: '60px' },
  { key: 'url', title: 'URL', sortable: false, align: 'center', width: '60px' },
  { key: 'actions', title: '', sortable: false, align: 'center', width: '60px' },
])

// Computed
const filteredItems = computed(() => {
  let result = items.value.data || []

  // Filter by item type
  if (filterType.value) {
    result = result.filter(item => item.itemType === filterType.value)
  }

  // Filter by study sites
  if (filterStudySites.value === 'with') {
    result = result.filter(item => item.study_sites && item.study_sites.length > 0)
  } else if (filterStudySites.value === 'without') {
    result = result.filter(item => !item.study_sites || item.study_sites.length === 0)
  }

  return result
})

const totalItems = computed(() => filteredItems.value.length)

const pageCount = computed(() => Math.ceil(totalItems.value / itemsPerPage.value))

const hasActiveFilters = computed(() => {
  return search.value !== '' || filterType.value !== null || filterStudySites.value !== null
})

const hasSelectedItems = computed(() => {
  return selectedItems.value.length > 0
})

// Computed property for when any operation is in progress
const isProcessing = computed(() => {
  return loading.value || downloading.value || syncing.value
})

const selectedCollection = computed(() => {
  if (selectedCollectionIndex.value === -1 || selectedCollectionIndex.value === undefined) {
    return null
  }
  return zoteroCollections.value[selectedCollectionIndex.value]
})

const syncButtonText = computed(() => {
  if (selectedCollection.value) {
    return `Sync Collection: ${selectedCollection.value.name}`
  }
  return 'Sync Library'
})

// Methods
const debouncedSearch = debounce(() => {
  page.value = 1 // Reset to first page on search
}, 300)

const clearFilters = () => {
  search.value = ''
  filterType.value = null
  filterStudySites.value = null
  page.value = 1
}

const clearSelection = () => {
  selectedItems.value = []
}

const handleSync = async () => {
  try {
    const collectionId = selectedCollection.value?.key || null
    const synced = await zoteroStore.syncLibrary(forceReload.value, collectionId)
    if (synced) {
      await zoteroStore.fetchItems()
      const message = collectionId
        ? `Collection "${selectedCollection.value?.name}" synced successfully`
        : 'Library synced successfully'
      notificationStore.showNotification(message, 'success')
    }
  } catch (error) {
    console.error('Sync error:', error)
  }
}

const handleDownloadAttachments = async () => {
  try {
    await zoteroStore.downloadAttachments()
    // Note: The store already handles fetching items and showing notifications
  } catch (error) {
    console.error('Download error:', error)
  }
}

const handleExtractAll = async () => {
  try {
    if (hasSelectedItems.value) {
      // Extract for selected items only - map to IDs
      const itemIds = selectedItems.value.map(item => item.id)
      const totalSelected = itemIds.length

      try {
        const result = await zoteroStore.extractStudySites(itemIds, forceReload.value)
        if (result && result.tasks) {
          // Add tasks to task store for tracking
          taskStore.addTasks(result.tasks)

          notificationStore.showNotification(
            `Queued extraction for ${totalSelected} selected item(s)`,
            'success'
          )
        }
      } catch (error) {
        console.error(`Extraction error for selected items:`, error)
        notificationStore.showNotification(
          `Failed to queue extraction for selected items`,
          'error'
        )
      }

      // Clear selection after extraction
      clearSelection()

      // Refresh items when all tasks complete
      setTimeout(() => {
        zoteroStore.fetchItems()
      }, 5000)
    } else {
      // Extract for all items
      const result = await zoteroStore.extractStudySites(null, forceReload.value)
      if (result && result.tasks) {
        // Add tasks to task store for tracking
        taskStore.addTasks(result.tasks)

        // Refresh items when tasks complete
        setTimeout(() => {
          zoteroStore.fetchItems()
        }, 5000)
      }
    }
  } catch (error) {
    console.error('Extraction error:', error)
  }
}

const handleRefresh = async () => {
  await zoteroStore.fetchItems()
  notificationStore.showNotification('Items refreshed', 'success')
}

const handleRowClick = (event: any, { item }: any) => {
  selectedItem.value = item
  detailsDialog.value = true
}

const viewDetails = (item: any) => {
  selectedItem.value = item
  detailsDialog.value = true
}

const viewOnMap = (item: any) => {
  router.push({
    path: '/map',
    query: { itemTitle: item.title }
  })
}

const viewExtractionResults = (item: any) => {
  selectedItem.value = item
  extractionResultsDialog.value = true
}

const handleViewResultOnMap = (result: any) => {
  // Close the extraction results dialog
  extractionResultsDialog.value = false

  // Navigate to map with the specific coordinates
  router.push({
    path: '/map',
    query: {
      itemTitle: selectedItem.value?.title,
      lat: result.latitude,
      lng: result.longitude
    }
  })
}

const handleImportFile = async (item: any) => {
  try {
    const result = await zoteroStore.importFileFromZotero(item.id)
    if (result) {
      await zoteroStore.fetchItems()
    }
  } catch (error) {
    console.error('Import file error:', error)
  }
}

const handleExtractStudySites = async (item: any) => {
  try {
    const result = await zoteroStore.extractStudySites(item.id, forceReload.value)
    if (result && result.tasks) {
      // Add tasks to task store for tracking
      taskStore.addTasks(result.tasks)

      // Refresh items when tasks complete
      setTimeout(() => {
        zoteroStore.fetchItems()
      }, 5000)
    }
  } catch (error) {
    console.error('Extraction error:', error)
  }
}

const handleEdit = (item: any) => {
  // Navigate to edit page or open edit dialog
  router.push(`/items/${item.id}/edit`)
}

const handleDelete = async (item: any) => {
  const confirmed = confirm(`Are you sure you want to delete "${item.title}"?`)
  if (!confirmed) return

  try {
    // await zoteroStore.deleteItem(item.id)
    notificationStore.showNotification('Item deleted', 'success')
    await zoteroStore.fetchItems()
  } catch (error) {
    console.error('Delete error:', error)
  }
}

const viewAttachment = (filePath: string) => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL + '/api/v1'
  const fileUrl = baseUrl + '/items/files/' + filePath.split('/').pop()
  window.open(fileUrl, '_blank', 'noopener,noreferrer')
}

const openInNewTab = (url: string) => {
  window.open(url, '_blank', 'noopener,noreferrer')
}

const openDoiLink = (doi: string) => {
  const url = getDoiUrl(doi)
  window.open(url, '_blank', 'noopener,noreferrer')
}

const getDoiUrl = (doi: string): string => {
  // Remove 'doi:' prefix if present
  const cleanDoi = doi.replace(/^doi:\s*/i, '')
  return `https://doi.org/${cleanDoi}`
}

const formatDate = (dateString: string | null): string => {
  if (!dateString) return '—'

  // Try to parse the date
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return dateString // Return original if can't parse

  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short'
  })
}

const hasStudySites = (item: any): boolean => {
  return item.study_sites && item.study_sites.length > 0
}

const getStudySitesColor = (studySites: any[]): string => {
  if (!studySites || studySites.length === 0) return 'default'

  const hasManual = studySites.some(site => site.is_manual)
  return hasManual ? 'success' : 'info'
}

// Lifecycle
onMounted(async () => {
  await Promise.all([
    zoteroStore.fetchItems(),
    zoteroStore.fetchZoteroCollections('group')
  ])
})
</script>

<style scoped>
.truncate-text {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  line-clamp: 3;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  white-space: normal;
  max-height: 4.5em;
}

:deep(.v-data-table tbody tr) {
  cursor: pointer;
}

:deep(.v-data-table tbody tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04);
}
</style>
