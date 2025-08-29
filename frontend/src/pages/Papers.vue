<template>
  <div class="max-w-7xl mx-auto p-6">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-2xl font-semibold">Papers</h2>
      <router-link to="/papers/new" class="btn btn-primary">Add Paper</router-link>
    </div>
    <div class="overflow-x-auto bg-white rounded-lg shadow">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Authors</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Journal</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          <tr v-for="paper in papersStore.filteredPapers" :key="paper.id">
            <td class="px-6 py-4 whitespace-nowrap">
              <router-link :to="`/papers/${paper.id}`" class="text-blue-600 hover:underline">
                {{ paper.title }}
              </router-link>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              {{ paper.authors?.join(', ') }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              {{ paper.journal }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
              <button @click="() => handleProcessLocations(paper.id)" class="btn btn-outline">Process</button>
              <button @click="() => handleDelete(paper.id)" class="btn btn-danger">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { usePapersStore } from '@/stores/papers'
import { useNotificationStore } from '@/stores/notification'

const papersStore = usePapersStore()
const notificationStore = useNotificationStore()

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
