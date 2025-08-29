<template>
  <div class="max-w-4xl mx-auto p-6" v-if="paper">
    <h2 class="text-2xl font-semibold mb-4">{{ paper.title }}</h2>
    <p class="text-gray-700">{{ paper.abstract }}</p>
    <div class="mt-4"><span class="font-semibold">Authors: </span>{{ paper.authors?.join(', ') }}</div>
    <div class="mt-2"><span class="font-semibold">Journal: </span>{{ paper.journal }}</div>
    <div class="mt-2"><a :href="paper.url" target="_blank" class="text-blue-600 hover:underline">View Original</a></div>
    <div class="mt-4">
      <h3 class="text-xl font-semibold">Locations</h3>
      <ul class="list-disc list-inside">
        <li v-for="loc in locations" :key="loc.location.id">
          {{ loc.location.name }} ({{ loc.location.country }}) - Confidence: {{ loc.confidence_score.toFixed(2) }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { usePapersStore } from '@/stores/papers'

const route = useRoute()
const papersStore = usePapersStore()
const paper = ref(null)
const locations = ref([])

onMounted(async () => {
  const id = route.params.id
  paper.value = await papersStore.fetchPaper(id)
  locations.value = await papersStore.getPaperLocations(id)
})
</script>
