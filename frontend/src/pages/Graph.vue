<template>
  <div>
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h4">Research Network Graph</h1>
          <v-btn
            v-if="authStore.isAuthenticated"
            color="primary"
            variant="elevated"
            prepend-icon="mdi-tag-plus"
            @click="showCreateDialog = true">
            Create Tag
          </v-btn>
        </div>
        <div class="mb-4">
          <v-chip
            v-for="tag in tags"
            :key="tag.id"
            :closable="authStore.isAuthenticated"
            variant="elevated"
            color="success"
            class="mr-2 mb-2"
            @click:close="handleDeleteTag(tag.id)"
            @click="selectedTag = tag.name">
            {{ tag.name }}
          </v-chip>
          <v-chip
            v-if="!tags || tags.length === 0"
            variant="outlined"
            disabled
            class="mr-2 mb-2">
            No tags yet
          </v-chip>
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12">
        <GraphView
          :items="items || []"
          :tags="tags"
          @graph-updated="handleGraphUpdated" />
      </v-col>
    </v-row>

    <!-- Tag Create Dialog -->
    <TagCreateDialog
      v-model="showCreateDialog"
      :items="items || []"
      @created="handleTagCreated" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useTagStore } from '@/stores/tags'
import { useZoteroStore } from '@/stores/zotero'
import { useAuthStore } from '@/stores/auth'
import GraphView from '@/components/GraphView.vue'
import TagCreateDialog from '@/components/TagCreateDialog.vue'

const authStore = useAuthStore()
const tagStore = useTagStore()
const { tags } = storeToRefs(tagStore)
const selectedTag = ref('')
const showCreateDialog = ref(false)

const itemsStore = useZoteroStore()
const { items } = storeToRefs(itemsStore)

const handleGraphUpdated = async () => {
  // Refetch both tags and items when the graph is updated
  await tagStore.fetchTags()
  await itemsStore.fetchItems()
}

const handleTagCreated = async (newTag: any) => {
  // Refetch data after tag creation
  await handleGraphUpdated()
}

const handleDeleteTag = async (tagId: number) => {
  if (!authStore.isAuthenticated) {
    return
  }

  await tagStore.deleteTag(tagId)
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
