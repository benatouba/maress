<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="600">
    <v-card v-if="studySite">
      <v-card-title class="d-flex align-center justify-space-between">
        <span>Edit Study Site</span>
        <v-chip
          :color="studySite.is_manual ? 'success' : 'info'"
          size="small"
        >
          {{ studySite.is_manual ? 'Manual' : 'Automatic' }}
        </v-chip>
      </v-card-title>

      <v-card-subtitle class="mt-2">
        <div class="text-body-2">
          <strong>Paper:</strong> {{ studySite.item_title || 'Unknown' }}
        </div>
      </v-card-subtitle>

      <v-card-text>
        <v-form ref="formRef" v-model="formValid" @submit.prevent="handleSave">
          <v-text-field
            v-model="form.name"
            label="Site Name"
            :rules="[rules.required]"
            prepend-icon="mdi-map-marker"
            variant="outlined"
            density="comfortable"
            class="mb-2"
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
                hint="0.0 to 1.0"
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
                hint="0.0 to 1.0"
                persistent-hint
              />
            </v-col>
          </v-row>

          <!-- Metadata (read-only) -->
          <v-expansion-panels class="mt-4">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon start>mdi-information</v-icon>
                Additional Information
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <div class="text-caption">
                  <div><strong>Extraction Method:</strong> {{ studySite.extraction_method }}</div>
                  <div><strong>Source Type:</strong> {{ studySite.source_type }}</div>
                  <div><strong>Section:</strong> {{ studySite.section }}</div>
                  <div><strong>Created:</strong> {{ formatDate(studySite.created_at) }}</div>
                  <div><strong>Updated:</strong> {{ formatDate(studySite.updated_at) }}</div>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-form>
      </v-card-text>

      <v-card-actions class="justify-space-between">
        <v-btn
          color="error"
          variant="text"
          prepend-icon="mdi-delete"
          @click="handleDelete"
          :loading="deleting"
        >
          Delete
        </v-btn>

        <div>
          <v-btn
            variant="text"
            @click="handleCancel"
          >
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="elevated"
            prepend-icon="mdi-content-save"
            @click="handleSave"
            :loading="saving"
            :disabled="!formValid"
          >
            Save
          </v-btn>
        </div>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useStudySitesStore, type StudySiteWithItem, type StudySiteUpdate } from '@/stores/studySites'

interface Props {
  modelValue: boolean
  studySite: StudySiteWithItem | null
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue', 'saved', 'deleted'])

// Store
const studySitesStore = useStudySitesStore()

// Form state
const formRef = ref()
const formValid = ref(false)
const saving = ref(false)
const deleting = ref(false)

const form = ref<StudySiteUpdate>({
  name: '',
  latitude: 0,
  longitude: 0,
  context: '',
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

/**
 * Initialize form with study site data
 */
const initializeForm = () => {
  if (!props.studySite) return

  form.value = {
    name: props.studySite.name || '',
    latitude: props.studySite.location.latitude,
    longitude: props.studySite.location.longitude,
    context: props.studySite.context || '',
    confidence_score: props.studySite.confidence_score || 1.0,
    validation_score: props.studySite.validation_score || 1.0
  }
}

/**
 * Handle save
 */
const handleSave = async () => {
  if (!props.studySite || !formValid.value) return

  // Validate form
  const { valid } = await formRef.value.validate()
  if (!valid) return

  saving.value = true
  try {
    const success = await studySitesStore.updateStudySite(
      props.studySite.id,
      form.value
    )

    if (success) {
      emit('saved')
      emit('update:modelValue', false)
    }
  } finally {
    saving.value = false
  }
}

/**
 * Handle delete
 */
const handleDelete = async () => {
  if (!props.studySite) return

  const confirmed = confirm(
    `Are you sure you want to delete the study site "${props.studySite.name || 'Unnamed'}"?`
  )

  if (!confirmed) return

  deleting.value = true
  try {
    const success = await studySitesStore.deleteStudySite(props.studySite.id)

    if (success) {
      emit('deleted')
      emit('update:modelValue', false)
    }
  } finally {
    deleting.value = false
  }
}

/**
 * Handle cancel
 */
const handleCancel = () => {
  emit('update:modelValue', false)
}

/**
 * Format date
 */
const formatDate = (dateString: string) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleString()
}

// Watch for changes in studySite prop
watch(() => props.studySite, (newSite) => {
  if (newSite) {
    initializeForm()
  }
}, { immediate: true })
</script>

<style scoped>
/* Add any custom styles here */
</style>
