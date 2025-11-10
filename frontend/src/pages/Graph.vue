<template>
  <div>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-4">Research Network Graph</h1>
        <div class="mb-4">
          <v-chip
            v-for="tag in tags"
            :key="tag.id"
            closable
            variant="elevated"
            color="success"
            class="mr-2 mb-2"
            @click:close="tagStore.removeTag(tag.id)"
            @click="selectedTag = tag.name">
            {{ tag.name }}
          </v-chip>
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12">
        <GraphView
          :items="items.data || []"
          :tags="tags"
          @graph-updated="handleGraphUpdated" />
      </v-col>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTagStore } from '@/stores/tags'
import { useZoteroStore } from '@/stores/zotero'
import GraphView from '@/components/GraphView.vue'

const tagStore = useTagStore()
const { tags } = storeToRefs(tagStore)
const selectedTag = ref('')

const itemsStore = useZoteroStore()
const { items } = storeToRefs(itemsStore)

const handleGraphUpdated = async () => {
  // Refetch both tags and items when the graph is updated
  await tagStore.fetchTags()
  await itemsStore.fetchItems()
}

onMounted(async () => {
  await tagStore.fetchTags()
  await itemsStore.fetchItems()
})
</script>

<style scoped>
.text-h4 {
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}
</style>
