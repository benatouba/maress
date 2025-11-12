<template>
  <v-dialog
    v-model="isOpen"
    max-width="700px"
    persistent>
    <v-card>
      <!-- Header -->
      <v-card-title class="d-flex justify-space-between align-center">
        <span class="text-h5">Create New Tag</span>
        <v-btn
          icon="mdi-close"
          variant="text"
          @click="close" />
      </v-card-title>

      <v-divider />

      <!-- Content -->
      <v-card-text class="pa-4">
        <!-- Tag Name -->
        <v-text-field
          v-model="tagName"
          label="Tag Name *"
          variant="outlined"
          density="comfortable"
          placeholder="e.g., Marine Biology, Climate Change..."
          :error-messages="tagNameError"
          :rules="[rules.required]"
          @keyup.enter="createTag">
          <template #prepend-inner>
            <v-icon icon="mdi-tag-outline" />
          </template>
        </v-text-field>

        <!-- Item Selection -->
        <div class="mt-4">
          <div class="text-subtitle-2 mb-2">
            Associate with Papers (Optional)
            <v-chip
              v-if="selectedItems.length > 0"
              size="small"
              color="primary"
              class="ml-2">
              {{ selectedItems.length }} selected
            </v-chip>
          </div>

          <!-- Search/Filter -->
          <v-text-field
            v-model="searchQuery"
            label="Search papers..."
            variant="outlined"
            density="compact"
            clearable
            class="mb-3">
            <template #prepend-inner>
              <v-icon icon="mdi-magnify" />
            </template>
          </v-text-field>

          <!-- Items List with Checkboxes -->
          <v-card
            variant="outlined"
            class="items-list-container">
            <v-list
              v-if="filteredItems.length > 0"
              density="compact"
              class="pa-0">
              <v-list-item
                v-for="item in filteredItems"
                :key="item.id"
                class="px-3"
                @click="toggleItem(item.id)">
                <template #prepend>
                  <v-checkbox-btn
                    :model-value="selectedItems.includes(item.id)"
                    @click.stop="toggleItem(item.id)" />
                </template>
                <v-list-item-title class="text-body-2">
                  {{ item.title || 'Untitled' }}
                </v-list-item-title>
                <v-list-item-subtitle
                  v-if="item.creators && item.creators.length > 0"
                  class="text-caption">
                  {{ formatAuthors(item.creators) }}
                </v-list-item-subtitle>
                <v-list-item-subtitle
                  v-if="item.publicationTitle"
                  class="text-caption">
                  {{ item.publicationTitle }}
                  <span v-if="item.date"> · {{ item.date }}</span>
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
            <div
              v-else
              class="pa-4 text-center text-grey">
              <v-icon
                icon="mdi-file-search-outline"
                size="48"
                class="mb-2" />
              <div class="text-body-2">
                {{ searchQuery ? 'No papers match your search' : 'No papers available' }}
              </div>
            </div>
          </v-card>

          <!-- Quick Selection Actions -->
          <div class="d-flex gap-2 mt-2">
            <v-btn
              size="small"
              variant="text"
              @click="selectAll">
              Select All ({{ filteredItems.length }})
            </v-btn>
            <v-btn
              size="small"
              variant="text"
              @click="clearSelection">
              Clear Selection
            </v-btn>
          </div>
        </div>
      </v-card-text>

      <v-divider />

      <!-- Actions -->
      <v-card-actions>
        <v-spacer />
        <v-btn
          variant="text"
          @click="close">
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          :disabled="!tagName.trim()"
          :loading="loading"
          @click="createTag">
          <v-icon
            icon="mdi-tag-plus"
            start />
          Create Tag
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useTagStore } from '@/stores/tags'

interface Props {
  modelValue: boolean
  items: any[]
}

const props = withDefaults(defineProps<Props>(), {
  items: () => []
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'created', tag: any): void
}>()

const tagStore = useTagStore()

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const tagName = ref('')
const tagNameError = ref('')
const selectedItems = ref<string[]>([])
const searchQuery = ref('')
const loading = ref(false)

const rules = {
  required: (value: string) => !!value || 'Tag name is required'
}

// Filter items by search query
const filteredItems = computed(() => {
  if (!searchQuery.value) return props.items

  const query = searchQuery.value.toLowerCase()
  return props.items.filter(item => {
    const titleMatch = item.title?.toLowerCase().includes(query)
    const authorsMatch = item.creators?.some((creator: any) =>
      `${creator.firstName} ${creator.lastName}`.toLowerCase().includes(query)
    )
    const pubMatch = item.publicationTitle?.toLowerCase().includes(query)
    return titleMatch || authorsMatch || pubMatch
  })
})

watch(() => tagName.value, () => {
  // Clear error when user types
  if (tagNameError.value) {
    tagNameError.value = ''
  }
})

watch(() => isOpen.value, (newValue) => {
  if (newValue) {
    // Reset form when dialog opens
    tagName.value = ''
    tagNameError.value = ''
    selectedItems.value = []
    searchQuery.value = ''
  }
})

const toggleItem = (itemId: string) => {
  const index = selectedItems.value.indexOf(itemId)
  if (index > -1) {
    selectedItems.value.splice(index, 1)
  } else {
    selectedItems.value.push(itemId)
  }
}

const selectAll = () => {
  selectedItems.value = filteredItems.value.map(item => item.id)
}

const clearSelection = () => {
  selectedItems.value = []
}

const formatAuthors = (creators: any[]) => {
  if (!creators || creators.length === 0) return ''
  const firstAuthor = `${creators[0].lastName}`
  if (creators.length === 1) return firstAuthor
  if (creators.length === 2) return `${firstAuthor} & ${creators[1].lastName}`
  return `${firstAuthor} et al.`
}

const createTag = async () => {
  if (!tagName.value.trim()) {
    tagNameError.value = 'Tag name is required'
    return
  }

  // Check if tag already exists
  const existingTag = tagStore.tags.find(
    tag => tag.name.toLowerCase() === tagName.value.trim().toLowerCase()
  )

  if (existingTag) {
    tagNameError.value = 'A tag with this name already exists'
    return
  }

  loading.value = true

  const newTag = await tagStore.createTag({
    name: tagName.value.trim(),
    item_ids: selectedItems.value
  })

  loading.value = false

  if (newTag) {
    emit('created', newTag)
    close()
  }
}

const close = () => {
  if (!loading.value) {
    isOpen.value = false
  }
}
</script>

<style scoped>
.items-list-container {
  max-height: 400px;
  overflow-y: auto;
}

.text-grey {
  color: rgb(var(--v-theme-on-surface-variant));
}

.gap-2 {
  gap: 8px;
}
</style>
