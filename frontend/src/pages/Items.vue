<template>
  <div>
    <h2 class="text-2xl font-semibold mb-4">Library</h2>
    <v-btn @click="handleSync">Sync Library</v-btn>
    <h3 class="font-semibold mb-2">Items</h3>
    <v-data-table
      :headers="headers"
      :items="items.data"
      expand-on-click
      :items-per-page="25"
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
          <v-icon color="primary" @click="viewAttachment(item.attachment)">mdi-file</v-icon>
        </div>
      </template>
      <template #item.url="{ item }">
        <div v-if="item.url">
          <v-icon color="primary" @click="openInNewTab(item.url)" class="cursor-pointer">mdi-open-in-new</v-icon>
        </div>
      </template>
      <template #item.doi="{ item }">
        <div v-if="item.doi">
          <v-icon color="primary" @click="openInNewTab(item.doi)" class="cursor-pointer">mdi-open-in-new</v-icon>
        </div>
      </template>
      <template #item.study_site.latitude="{ item }">
        <div v-if="item.study_site?.latitude">
          {{ item.study_site.latitude.toFixed(4) }}
        </div>
      </template>
      <template #item.study_site.longitude="{ item }">
        <div v-if="item.study_site?.longitude">
          {{ item.study_site.latitude.toFixed(4) }}
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

const viewAttachment = (filePath: string) => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL + "/api/v1"
  const fileUrl = baseUrl + "/items/files/" + filePath.split('/').pop()
  window.open(fileUrl, '_blank', 'noopener')
}

const openInNewTab = (url: string) => {
  window.open(url, '_blank', 'noopener')
}

onMounted(async () => {
  await zoteroStore.fetchItems()
  console.log(items.data)
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
  { key: 'study_site.latitude', title: 'Latitude', sortable: true },
  { key: 'study_site.longitude', title: 'Logitude', sortable: true },
  { key: 'abstractNote', title: 'Abstract', sortable: false },
  { key: 'authors', title: 'Authors', sortable: false },
  { key: 'publicationTitle', title: 'Journal', sortable: true },
  // { key: 'journalAbbreviation', title: 'Abbrev.', sortable: true },
  // { key: 'volume', title: 'Volume', sortable: true },
  // { key: 'issue', title: 'Issue', sortable: true },
  // { key: 'pages', title: 'Pages', sortable: false },
  { key: 'date', title: 'Date', sortable: true },
  // { key: 'language', title: 'Language', sortable: true },
  { key: 'issn', title: 'ISSN', sortable: false },
  // { key: 'rights', title: 'Rights', sortable: false },
  // { key: 'itemType', title: 'Type', sortable: true },
  { key: 'libraryCatalog', title: 'Catalog', sortable: false },
  { key: 'archive', title: 'Archive', sortable: false },
  { key: 'seriesTitle', title: 'Series', sortable: false },
  { key: 'doi', title: 'DOI', sortable: false },
  { key: 'url', title: 'URL', sortable: false },
  { key: 'actions', title: '', sortable: false }, // for buttons/menus
])
</script>
<style scoped>
.truncate-text {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box; /* truncate after 3 lines */
  line-clamp: 5; /* Number of lines to show */
  -webkit-line-clamp: 5; /* Number of lines to show */
  -webkit-box-orient: vertical;
  white-space: normal;
  max-width: 400px; /* Adjust width as needed */
  max-height: 6em; /* Limit height for multi-line truncation */
}
</style>
