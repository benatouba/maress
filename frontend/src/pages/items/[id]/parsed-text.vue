<template>
  <v-container class="py-6" fluid>
    <v-row justify="center">
      <v-col cols="12" lg="10" xl="8">
        <v-btn
          variant="text"
          prepend-icon="mdi-arrow-left"
          class="mb-3 px-0"
          @click="goBack"
        >
          Back to Items
        </v-btn>

        <v-card elevation="1">
          <v-card-title class="text-h5 py-4 px-6">
            {{ titleText }}
          </v-card-title>
          <v-divider />

          <v-card-text class="pa-6">
            <v-progress-linear
              v-if="loading"
              indeterminate
              color="primary"
              class="mb-4"
            />

            <v-alert
              v-else-if="errorMessage"
              type="error"
              variant="tonal"
            >
              {{ errorMessage }}
            </v-alert>

            <div
              v-else
              class="parsed-text-content"
              v-html="renderedParsedText"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useZoteroStore } from '@/stores/zotero'

const route = useRoute()
const router = useRouter()
const zoteroStore = useZoteroStore()

const loading = ref(false)
const errorMessage = ref('')
const itemTitle = ref('')
const parsedText = ref('')

const itemId = computed(() => String(route.params.id || ''))

const titleText = computed(() => {
  return itemTitle.value || 'Parsed Text'
})

const escapeHtml = (value: string): string => {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

const parsedTextToHtml = (value: string): string => {
  const normalized = value.replaceAll('\r\n', '\n').trim()
  if (!normalized) {
    return ''
  }

  return normalized
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replaceAll('\n', '<br>')}</p>`)
    .join('')
}

const renderedParsedText = computed(() => parsedTextToHtml(parsedText.value))

const fetchParsedText = async () => {
  if (!itemId.value) {
    errorMessage.value = 'Item ID is missing'
    return
  }

  loading.value = true
  errorMessage.value = ''

  try {
    const response = await zoteroStore.fetchItemParsedText(itemId.value)
    if (!response) {
      errorMessage.value = 'Unable to load parsed text'
      return
    }

    itemTitle.value = response.title || 'Parsed Text'
    parsedText.value = response.parsed_text || ''
  } catch {
    errorMessage.value = 'Unable to load parsed text'
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/Items')
}

onMounted(async () => {
  await fetchParsedText()
})
</script>

<style scoped>
.parsed-text-content {
  font-size: 0.95rem;
  line-height: 1.7;
  color: rgb(var(--v-theme-on-surface));
  word-break: break-word;
}

.parsed-text-content :deep(p) {
  margin-bottom: 1rem;
}

.parsed-text-content :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
