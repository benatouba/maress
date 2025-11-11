<template>
  <v-dialog
    v-model="isOpen"
    max-width="800px"
    persistent>
    <v-card>
      <!-- Header -->
      <v-card-title class="d-flex justify-space-between align-center">
        <span>{{ isTag ? 'Tag Details' : 'Item Details' }}</span>
        <v-btn
          icon="mdi-close"
          variant="text"
          @click="close" />
      </v-card-title>

      <v-divider />

      <!-- Content -->
      <v-card-text
        v-if="nodeData"
        class="pa-4">
        <!-- Tag Content -->
        <div v-if="isTag">
          <v-text-field
            v-if="isEditing"
            v-model="editedName"
            label="Tag Name"
            variant="outlined"
            density="comfortable"
            :rules="[rules.required]" />
          <div v-else>
            <h3 class="text-h6 mb-2">{{ nodeData.name }}</h3>
            <v-chip
              color="success"
              size="small"
              class="mb-3">
              Tag
            </v-chip>
          </div>

          <!-- Connected Items -->
          <div class="mt-4">
            <h4 class="text-subtitle-1 mb-2">Connected Items ({{ connectedItems.length }})</h4>
            <v-list
              v-if="connectedItems.length > 0"
              density="compact">
              <v-list-item
                v-for="item in connectedItems"
                :key="item.id"
                class="px-0">
                <template #prepend>
                  <v-icon
                    icon="mdi-file-document"
                    size="small" />
                </template>
                <v-list-item-title>{{ item.title || 'Untitled' }}</v-list-item-title>
                <v-list-item-subtitle v-if="item.publicationTitle">
                  {{ item.publicationTitle }}
                </v-list-item-subtitle>
                <template
                  v-if="isEditing"
                  #append>
                  <v-btn
                    icon="mdi-close"
                    size="x-small"
                    variant="text"
                    @click="removeItemFromTag(item.id)" />
                </template>
              </v-list-item>
            </v-list>
            <p
              v-else
              class="text-body-2 text-grey">
              No items connected to this tag
            </p>

            <!-- Add Item to Tag (when editing) -->
            <v-autocomplete
              v-if="isEditing"
              v-model="selectedItemToAdd"
              :items="availableItems"
              item-title="title"
              item-value="id"
              label="Add Item to Tag"
              variant="outlined"
              density="comfortable"
              class="mt-3"
              @update:model-value="addItemToTag">
              <template #item="{ props, item }">
                <v-list-item
                  v-bind="props"
                  :title="item.raw.title || 'Untitled'"
                  :subtitle="item.raw.publicationTitle || ''" />
              </template>
            </v-autocomplete>
          </div>
        </div>

        <!-- Item Content -->
        <div v-else>
          <div class="mb-3">
            <h3 class="text-h6 mb-2">{{ nodeData.title || 'Untitled' }}</h3>
            <v-chip
              color="primary"
              size="small">
              Item
            </v-chip>
          </div>

          <!-- Authors -->
          <div
            v-if="nodeData.creators && nodeData.creators.length > 0"
            class="mb-3">
            <v-chip-group>
              <v-chip
                v-for="(creator, index) in nodeData.creators"
                :key="index"
                size="small"
                variant="outlined">
                {{ `${creator.firstName} ${creator.lastName}` }}
              </v-chip>
            </v-chip-group>
          </div>

          <!-- Publication Info -->
          <div class="mb-3">
            <v-row dense>
              <v-col
                v-if="nodeData.publicationTitle"
                cols="12">
                <div class="text-caption text-grey">Publication</div>
                <div class="text-body-2">{{ nodeData.publicationTitle }}</div>
              </v-col>
              <v-col
                v-if="nodeData.date"
                cols="6">
                <div class="text-caption text-grey">Date</div>
                <div class="text-body-2">{{ formatDate(nodeData.date) }}</div>
              </v-col>
              <v-col
                v-if="nodeData.doi"
                cols="6">
                <div class="text-caption text-grey">DOI</div>
                <a
                  :href="`https://doi.org/${nodeData.doi.replace('doi:', '')}`"
                  target="_blank"
                  class="text-body-2 text-primary">
                  {{ nodeData.doi }}
                </a>
              </v-col>
            </v-row>
          </div>

          <!-- Abstract -->
          <div
            v-if="nodeData.abstractNote"
            class="mb-3">
            <div class="text-caption text-grey mb-1">Abstract</div>
            <div class="text-body-2">{{ nodeData.abstractNote }}</div>
          </div>

          <!-- Tags -->
          <div class="mb-3">
            <div class="text-caption text-grey mb-1">Tags</div>
            <v-chip-group>
              <v-chip
                v-for="tag in nodeData.tags"
                :key="tag"
                size="small"
                color="success"
                variant="outlined">
                {{ getTagName(tag) }}
              </v-chip>
              <v-chip
                v-if="!nodeData.tags || nodeData.tags.length === 0"
                size="small"
                variant="outlined"
                disabled>
                No tags
              </v-chip>
            </v-chip-group>
          </div>

          <!-- Study Sites -->
          <div
            v-if="nodeData.study_sites && nodeData.study_sites.length > 0"
            class="mb-3">
            <div class="text-caption text-grey mb-1">Study Sites</div>
            <v-chip-group>
              <v-chip
                v-for="site in nodeData.study_sites"
                :key="site.id"
                size="small"
                :color="site.is_manual ? 'success' : 'info'"
                variant="outlined">
                {{ site.name || `${site.location.latitude}, ${site.location.longitude}` }}
              </v-chip>
            </v-chip-group>
          </div>
        </div>
      </v-card-text>

      <v-divider />

      <!-- Actions -->
      <v-card-actions>
        <v-spacer />

        <!-- View on Map (for items with study sites) -->
        <v-btn
          v-if="!isTag && hasStudySites"
          color="primary"
          variant="text"
          prepend-icon="mdi-map"
          @click="viewOnMap">
          View on Map
        </v-btn>

        <!-- Edit/Save/Cancel -->
        <v-btn
          v-if="!isEditing"
          color="primary"
          variant="text"
          @click="startEditing">
          Edit
        </v-btn>
        <v-btn
          v-if="isEditing"
          color="primary"
          variant="text"
          @click="saveChanges">
          Save
        </v-btn>
        <v-btn
          v-if="isEditing"
          variant="text"
          @click="cancelEditing">
          Cancel
        </v-btn>
        <v-btn
          v-if="!isEditing"
          variant="text"
          @click="close">
          Close
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTagStore } from '@/stores/tags'
import { useNotificationStore } from '@/stores/notification'

interface Props {
  modelValue: boolean
  nodeData: any
  nodeType: 'tag' | 'item'
  allItems?: any[]
  allTags?: any[]
}

const props = withDefaults(defineProps<Props>(), {
  allItems: () => [],
  allTags: () => []
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'updated'): void
}>()

const router = useRouter()
const tagStore = useTagStore()
const notificationStore = useNotificationStore()

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const isTag = computed(() => props.nodeType === 'tag')
const isEditing = ref(false)
const editedName = ref('')
const selectedItemToAdd = ref<string | null>(null)

const connectedItems = computed(() => {
  if (!isTag.value || !props.nodeData) return []
  return props.nodeData.items || []
})

const availableItems = computed(() => {
  if (!isTag.value) return []
  const connectedIds = new Set(connectedItems.value.map((item: any) => item.id))
  return props.allItems.filter(item => !connectedIds.has(item.id))
})

const hasStudySites = computed(() => {
  if (isTag.value || !props.nodeData) return false
  return props.nodeData.study_sites && props.nodeData.study_sites.length > 0
})

const rules = {
  required: (value: string) => !!value || 'Required'
}

watch(() => props.nodeData, (newData) => {
  if (newData && isTag.value) {
    editedName.value = newData.name
  }
}, { immediate: true })

const startEditing = () => {
  if (isTag.value && props.nodeData) {
    editedName.value = props.nodeData.name
  }
  isEditing.value = true
}

const cancelEditing = () => {
  isEditing.value = false
  if (isTag.value && props.nodeData) {
    editedName.value = props.nodeData.name
  }
}

const saveChanges = async () => {
  if (isTag.value && props.nodeData) {
    const success = await tagStore.updateTag(props.nodeData.id, {
      name: editedName.value
    })
    if (success) {
      isEditing.value = false
      emit('updated')
    }
  }
}

const addItemToTag = async (itemId: string | null) => {
  if (!itemId || !props.nodeData) return

  const success = await tagStore.addItemToTag(props.nodeData.id, itemId)
  if (success) {
    selectedItemToAdd.value = null
    emit('updated')
  }
}

const removeItemFromTag = async (itemId: string) => {
  if (!props.nodeData) return

  const success = await tagStore.removeItemFromTag(props.nodeData.id, itemId)
  if (success) {
    emit('updated')
  }
}

const viewOnMap = () => {
  if (!props.nodeData) return
  router.push({
    path: '/map',
    query: { itemId: props.nodeData.id }
  })
}

const close = () => {
  isEditing.value = false
  emit('update:modelValue', false)
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short' })
}

const getTagName = (tagIdOrObj: any) => {
  if (typeof tagIdOrObj === 'string' || typeof tagIdOrObj === 'number') {
    const tag = props.allTags.find(t => t.id === tagIdOrObj)
    return tag?.name || tagIdOrObj
  }
  return tagIdOrObj.name || tagIdOrObj.tag || tagIdOrObj
}
</script>

<style scoped>
.text-grey {
  color: rgb(var(--v-theme-on-surface-variant));
}

.text-primary {
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
}

.text-primary:hover {
  text-decoration: underline;
}
</style>
