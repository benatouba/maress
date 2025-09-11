<template>
  <div>
    <h1>Graph Page</h1>
    <v-row>
      <v-col cols="12">
        <v-chip
          v-for="tag in tags"
          closable
          variant="elevated"
          @click:close="tagStore.removeTag(tag.id)"
          @click="selectedTag = tag.name">
          {{ tag.name }}
        </v-chip>
      </v-col>
      <v-row>
        <v-col cols="12">
          <GraphView :items="items.data" :tags="tags" />
        </v-col>
      </v-row>
    </v-row>
  </div>
</template>

<script setup lang="ts">
import { useTagStore } from '@/stores/tags'
import { useZoteroStore } from '@/stores/zotero'

const tagStore = useTagStore()
const { tags } = storeToRefs(tagStore)
const selectedTag = ref('')

const itemsStore = useZoteroStore()
const { items } = storeToRefs(itemsStore)
console.log('Items:', items.value)

onMounted(async () => {
  await tagStore.fetchTags()
  await itemsStore.fetchItems()
})

</script>
