<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-6">
      <h2 class="text-h5">Papers</h2>
      <v-btn color="primary" to="/papers/new" prepend-icon="mdi-plus">Add Paper</v-btn>
    </div>
    <v-card>
      <v-data-table
        :headers="headers"
        :items="papersStore.filteredPapers"
        :items-per-page="15"
      >
        <template #item.title="{ item }">
          <router-link :to="`/papers/${item.id}`" class="text-primary text-decoration-none">
            {{ item.title }}
          </router-link>
        </template>
        <template #item.authors="{ item }">
          {{ item.authors?.join(', ') }}
        </template>
        <template #item.actions="{ item }">
          <v-btn variant="outlined" size="small" class="mr-2" @click="handleProcessLocations(item.id)">
            Process
          </v-btn>
          <v-btn variant="outlined" color="error" size="small" @click="handleDelete(item.id)">
            Delete
          </v-btn>
        </template>
      </v-data-table>
    </v-card>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { usePapersStore } from '@/stores/papers'
import { useNotificationStore } from '@/stores/notification'

const papersStore = usePapersStore()
const notificationStore = useNotificationStore()

const headers = [
  { title: 'Title', key: 'title' },
  { title: 'Authors', key: 'authors' },
  { title: 'Journal', key: 'journal' },
  { title: 'Actions', key: 'actions', sortable: false },
]

const handleDelete = async (id) => {
  const success = await papersStore.deletePaper(id)
  if (success) {
    notificationStore.showNotification('Paper deleted', 'success')
  }
}

const handleProcessLocations = async (id) => {
  await papersStore.processLocations(id)
}

onMounted(async () => {
  await papersStore.fetchPapers()
})
</script>
