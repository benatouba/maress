<template>
  <div>
    <h2 class="text-2xl font-semibold mb-4">Zotero Library</h2>
    <v-btn @click="handleSync">Sync Library</v-btn>
    <h3 class="font-semibold mb-2">Items</h3>
    <v-data-table
      :headers="headers"
      :items="items.data"
      expand-on-click
      :items-per-page="10"
      :items-length="items.count"
      :loading="loading || syncing"
    >
      <template #item.abstractNote="{ item }">
        <div class="truncate-text" :title="item.abstractNote">
          {{ item.abstractNote }}
        </div>
      </template>
      <template #item.attachment="{ item }">
        <div v-if="!!item.attachment">
          <v-icon color="primary">mdi-file</v-icon>
        </div>
      </template>
    </v-data-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useZoteroStore } from '@/stores/zotero'

const zoteroStore = useZoteroStore()
const { items, loading, syncing } = storeToRefs(zoteroStore)

const handleSync = async () => {
  const synced = await zoteroStore.syncLibrary()
  if (synced) {
    await zoteroStore.fetchItems(null, undefined)
  }
  const downloaded = await zoteroStore.downloadAttachments()
  if (downloaded) {
    await zoteroStore.fetchItems(null, undefined)
  }
}
const handleImportCollection = async collectionId => {
  await zoteroStore.syncLibrary(collectionId)
}
const handleImportItem = async itemId => {
  await zoteroStore.importItem(itemId)
}

onMounted(async () => {
  await zoteroStore.fetchItems()
})
interface DataTableHeader {
  key: string // maps to the field in your data
  title: string // column label in the UI
  value?: string // optional, also maps to field
  align?: 'start' | 'end' | 'center'
  sortable?: boolean
}

const headers: Ref<Readonly<DataTableHeader[]>> = ref([
  { key: 'attachment', title: '', sortable: false },
  { key: 'title', title: 'Title', sortable: true },
  { key: 'study_site.latitude', title: 'lat', sortable: true },
  { key: 'study_site.longitude', title: 'lon', sortable: true },
  { key: 'abstractNote', title: 'Abstract', sortable: false },
  { key: 'authors', title: 'Authors', sortable: false }, // you’ll need to format people array
  { key: 'publicationTitle', title: 'Journal', sortable: true },
  { key: 'journalAbbreviation', title: 'Abbrev.', sortable: true },
  { key: 'volume', title: 'Volume', sortable: true },
  { key: 'issue', title: 'Issue', sortable: true },
  { key: 'pages', title: 'Pages', sortable: false },
  { key: 'date', title: 'Date', sortable: true },
  { key: 'doi', title: 'DOI', sortable: false },
  { key: 'url', title: 'URL', sortable: false },
  { key: 'language', title: 'Language', sortable: true },
  { key: 'issn', title: 'ISSN', sortable: false },
  { key: 'rights', title: 'Rights', sortable: false },
  { key: 'itemType', title: 'Type', sortable: true },
  { key: 'libraryCatalog', title: 'Catalog', sortable: false },
  { key: 'archive', title: 'Archive', sortable: false },
  { key: 'seriesTitle', title: 'Series', sortable: false },
  { key: 'actions', title: '', sortable: false }, // for buttons/menus
])
</script>
<style scoped>
.truncate-text {
  overflow: hidden;
  text-overflow: ellipsis;
  /* truncate after 3 lines */
  display: -webkit-box;
  line-clamp: 3; /* Number of lines to show */
  -webkit-line-clamp: 3; /* Number of lines to show */
  -webkit-box-orient: vertical;
  white-space: normal;
  max-width: 300px; /* Adjust width as needed */
  max-height: 3em; /* Limit height for multi-line truncation */
}
</style>
