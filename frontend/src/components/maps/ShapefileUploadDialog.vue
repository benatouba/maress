<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    max-width="500"
    persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-shape-polygon-plus</v-icon>
        Upload Shapefile
      </v-card-title>

      <v-card-text>
        <v-alert
          v-if="!authStore.isAuthenticated"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-4">
          You must be signed in to upload shapefiles.
        </v-alert>

        <v-file-input
          v-model="selectedFile"
          label="Shapefile (.zip)"
          accept=".zip"
          prepend-icon="mdi-file-upload"
          variant="outlined"
          density="compact"
          :rules="[fileRequired, fileSize]"
          :disabled="!authStore.isAuthenticated"
          hint="Upload a .zip archive containing .shp, .shx, .dbf, and .prj files"
          persistent-hint
          show-size
          class="mb-4">
        </v-file-input>

        <v-alert
          v-if="error"
          type="error"
          variant="tonal"
          density="compact"
          closable
          @click:close="error = null"
          class="mb-4">
          {{ error }}
        </v-alert>

        <v-alert
          v-if="uploadResult"
          type="success"
          variant="tonal"
          density="compact"
          class="mb-4">
          Created {{ uploadResult }} region(s) from shapefile.
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn
          variant="text"
          @click="close">
          {{ uploadResult ? 'Close' : 'Cancel' }}
        </v-btn>
        <v-btn
          v-if="!uploadResult"
          color="primary"
          variant="elevated"
          :loading="uploading"
          :disabled="!selectedFile || !authStore.isAuthenticated"
          @click="upload">
          Upload
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRegionsStore } from '../../stores/regions'
import { useAuthStore } from '../../stores/auth'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  uploaded: []
}>()

const regionsStore = useRegionsStore()
const authStore = useAuthStore()

const selectedFile = ref<File | null>(null)
const error = ref<string | null>(null)
const uploadResult = ref<number | null>(null)
const uploading = ref(false)

const fileRequired = (v: File | null) => !!v || 'A file is required'
const fileSize = (v: File | null) =>
  !v || v.size <= 50 * 1024 * 1024 || 'File must be under 50 MB'

const upload = async () => {
  if (!authStore.isAuthenticated) {
    error.value = 'You must be signed in to upload shapefiles'
    return
  }

  if (!selectedFile.value) return

  uploading.value = true
  error.value = null
  uploadResult.value = null

  try {
    const regions = await regionsStore.uploadShapefile(selectedFile.value)
    if (regions.length > 0) {
      uploadResult.value = regions.length
      emit('uploaded')
    } else {
      error.value = 'No regions were created from the shapefile'
    }
  } catch (e: any) {
    error.value = e.message || 'Upload failed'
  } finally {
    uploading.value = false
  }
}

const close = () => {
  selectedFile.value = null
  error.value = null
  uploadResult.value = null
  emit('update:modelValue', false)
}
</script>
