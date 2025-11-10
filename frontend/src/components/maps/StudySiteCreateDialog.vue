<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="600">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start color="success">mdi-map-marker-plus</v-icon>
        <span>Create New Study Site</span>
      </v-card-title>

      <v-card-text>
        <v-form ref="formRef" v-model="formValid" @submit.prevent="handleCreate">
          <!-- Item Selection -->
          <v-autocomplete
            v-model="form.itemId"
            :items="items"
            :loading="loadingItems"
            item-title="title"
            item-value="id"
            label="Select Paper/Item"
            :rules="[rules.required]"
            prepend-icon="mdi-file-document"
            variant="outlined"
            density="comfortable"
            class="mb-2"
            clearable
            :hint="selectedItemInfo"
            persistent-hint
          >
            <template #item="{ props: itemProps, item }">
              <v-list-item
                v-bind="itemProps"
                :title="item.raw.title"
                :subtitle="getItemSubtitle(item.raw)"
              />
            </template>
          </v-autocomplete>

          <v-text-field
            v-model="form.name"
            label="Site Name"
            :rules="[rules.required]"
            prepend-icon="mdi-map-marker"
            variant="outlined"
            density="comfortable"
            class="mb-2"
            placeholder="e.g., Study Area A, Site 1, etc."
          />

          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model.number="form.latitude"
                label="Latitude"
                type="number"
                :rules="[rules.required, rules.latitude]"
                prepend-icon="mdi-latitude"
                variant="outlined"
                density="comfortable"
                step="0.0001"
                hint="Between -90 and 90"
                persistent-hint
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="form.longitude"
                label="Longitude"
                type="number"
                :rules="[rules.required, rules.longitude]"
                prepend-icon="mdi-longitude"
                variant="outlined"
                density="comfortable"
                step="0.0001"
                hint="Between -180 and 180"
                persistent-hint
              />
            </v-col>
          </v-row>

          <v-textarea
            v-model="form.context"
            label="Context / Description"
            rows="3"
            prepend-icon="mdi-text"
            variant="outlined"
            density="comfortable"
            class="mb-2"
            placeholder="Additional information about this study site..."
          />

          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model.number="form.confidence_score"
                label="Confidence Score"
                type="number"
                :rules="[rules.score]"
                prepend-icon="mdi-percent"
                variant="outlined"
                density="comfortable"
                step="0.01"
                min="0"
                max="1"
                hint="Default: 1.0"
                persistent-hint
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="form.validation_score"
                label="Validation Score"
                type="number"
                :rules="[rules.score]"
                prepend-icon="mdi-check-circle"
                variant="outlined"
                density="comfortable"
                step="0.01"
                min="0"
                max="1"
                hint="Default: 1.0"
                persistent-hint
              />
            </v-col>
          </v-row>

          <!-- Info alert -->
          <v-alert
            type="info"
            variant="tonal"
            density="compact"
            class="mt-4"
          >
            <div class="text-caption">
              This study site will be marked as <strong>manually created</strong>.
              You can edit or delete it later from the map.
            </div>
          </v-alert>
        </v-form>
      </v-card-text>

      <v-card-actions class="justify-end">
        <v-btn
          variant="text"
          @click="handleCancel"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          variant="elevated"
          prepend-icon="mdi-plus"
          @click="handleCreate"
          :loading="creating"
          :disabled="!formValid"
        >
          Create
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useStudySitesStore, type StudySiteCreate } from '@/stores/studySites'
import api from '@/services/api'

interface Props {
  modelValue: boolean
  itemId?: string | null
  coordinates?: [number, number] | null
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue', 'created'])

// Store
const studySitesStore = useStudySitesStore()

// Form state
const formRef = ref()
const formValid = ref(false)
const creating = ref(false)
const loadingItems = ref(false)
const items = ref<any[]>([])

interface CreateForm extends StudySiteCreate {
  itemId: string
}

const form = ref<CreateForm>({
  itemId: '',
  name: '',
  latitude: 0,
  longitude: 0,
  context: 'Manually added by user',
  confidence_score: 1.0,
  validation_score: 1.0
})

// Validation rules
const rules = {
  required: (v: any) => !!v || 'Required',
  latitude: (v: number) => (v >= -90 && v <= 90) || 'Must be between -90 and 90',
  longitude: (v: number) => (v >= -180 && v <= 180) || 'Must be between -180 and 180',
  score: (v: number) => (v >= 0 && v <= 1) || 'Must be between 0 and 1'
}

// Computed
const selectedItemInfo = computed(() => {
  if (!form.value.itemId) return 'Select a paper to associate this study site with'
  const item = items.value.find(i => i.id === form.value.itemId)
  if (!item) return ''
  return `${item.publicationTitle || 'Unknown journal'} (${item.date || 'No date'})`
})

/**
 * Get subtitle for item in autocomplete
 */
const getItemSubtitle = (item: any) => {
  const parts = []
  if (item.publicationTitle) parts.push(item.publicationTitle)
  if (item.date) parts.push(item.date)
  return parts.join(' • ')
}

/**
 * Fetch items for selection
 */
const fetchItems = async () => {
  loadingItems.value = true
  try {
    const response = await api.get('/items/', {
      params: { limit: 1000 }
    })
    items.value = response.data.data || []
  } catch (error) {
    console.error('Error fetching items:', error)
  } finally {
    loadingItems.value = false
  }
}

/**
 * Initialize form with provided coordinates
 */
const initializeForm = () => {
  // Set item ID if provided
  if (props.itemId) {
    form.value.itemId = props.itemId
  }

  // Set coordinates if provided
  if (props.coordinates) {
    form.value.longitude = props.coordinates[0]
    form.value.latitude = props.coordinates[1]
  }
}

/**
 * Handle create
 */
const handleCreate = async () => {
  if (!formValid.value) return

  // Validate form
  const { valid } = await formRef.value.validate()
  if (!valid) return

  creating.value = true
  try {
    const { itemId, ...siteData } = form.value
    const success = await studySitesStore.createStudySite(itemId, siteData)

    if (success) {
      emit('created', success)
      emit('update:modelValue', false)
      resetForm()
    }
  } finally {
    creating.value = false
  }
}

/**
 * Handle cancel
 */
const handleCancel = () => {
  emit('update:modelValue', false)
  resetForm()
}

/**
 * Reset form
 */
const resetForm = () => {
  form.value = {
    itemId: '',
    name: '',
    latitude: 0,
    longitude: 0,
    context: 'Manually added by user',
    confidence_score: 1.0,
    validation_score: 1.0
  }
}

// Watch for dialog open
watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    initializeForm()
  }
})

// Lifecycle
onMounted(async () => {
  await fetchItems()
})
</script>

<style scoped>
/* Add any custom styles here */
</style>
