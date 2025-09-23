<template>
  <v-container
    fluid
    class="fill-height">
    <v-row
      align="center"
      justify="center"
      class="fill-height">
      <v-col
        cols="12"
        md="8"
        lg="6">
        <!-- Welcome Card -->
        <v-card
          class="mx-auto mb-8"
          elevation="2">
          <v-card-text class="text-center pa-8">
            <!-- Welcome Message -->
            <div class="mb-4">
              <h1 class="display-1 font-weight-light mb-4">Welcome to MaRESS</h1>

              <h2 class="headline font-weight-regular mb-6 text--secondary">
                The geospatial reference platform for Earth System Science
              </h2>

              <p class="body-1 text--secondary mb-6">
                {{
                  authStore.isAuthenticated ?
                    'Access your research papers, manage study sites, and analyze geospatial patterns.'
                  : 'Please log in to access your research data, study sites, and climate modeling tools.'
                }}
              </p>
            </div>

            <!-- Action Buttons -->
            <div
              v-if="authStore.isAuthenticated"
              class="mb-4">
              <v-row
                justify="center"
                class="ma-0">
                <v-col cols="auto">
                  <v-btn
                    color="primary"
                    large
                    @click="$router.push('/map')"
                    class="mr-4">
                    <v-icon left>mdi-map</v-icon>
                    Study Sites Map
                  </v-btn>
                </v-col>
                <v-col cols="auto">
                  <v-btn
                    color="secondary"
                    large
                    outlined
                    @click="$router.push('/items')">
                    <v-icon left>mdi-file-document-multiple</v-icon>
                    Research Papers
                  </v-btn>
                </v-col>
              </v-row>
            </div>

            <div v-else>
              <v-btn
                color="primary"
                large
                @click="$router.push('/login')">
                <v-icon left>mdi-login</v-icon>
                Get Started
              </v-btn>
            </div>

            <!-- Center Image -->
            <div class="mb-6">
              <v-img
                src="/project-overview.jpg"
                alt="Climate Research"
                max-width="1000"
                class="mx-auto"
                contain />
            </div>
          </v-card-text>
        </v-card>

        <!-- Feature Cards for Authenticated Users -->
        <v-row
          v-if="authStore.isAuthenticated"
          justify="center">
          <v-col
            cols="12"
            sm="6"
            md="4">
            <v-card
              hover
              @click="$router.push('/zotero')"
              height="230px"
              class="cursor-pointer">
              <v-card-text class="text-center">
                <v-icon
                  size="48"
                  color="primary"
                  class="mb-4"
                  >mdi-library</v-icon
                >
                <h3 class="subtitle-1 font-weight-medium">Zotero Integration</h3>
                <p class="caption text--secondary">Sync and manage your research library</p>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col
            cols="12"
            sm="6"
            md="4">
            <v-card
              hover
              @click="$router.push('/map')"
              height="230px"
              class="cursor-pointer">
              <v-card-text class="text-center">
                <v-icon
                  size="48"
                  color="primary"
                  class="mb-4"
                  >mdi-text-box-outline</v-icon
                >
                <h3 class="subtitle-1 font-weight-medium">Natural Language Processing</h3>
                <p class="caption text--secondary">
                  Find geographical information in your documents
                </p>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col
            cols="12"
            sm="6"
            md="4">
            <v-card
              hover
              @click="$router.push('/graph')"
              height="230px"
              class="cursor-pointer">
              <v-card-text class="text-center">
                <v-icon
                  size="48"
                  color="accent"
                  class="mb-4"
                  >mdi-spider-web</v-icon
                >
                <h3 class="subtitle-1 font-weight-medium">Connection Graph</h3>
                <p class="caption text--secondary">
                  Find and organize your knowledge via keyword graph
                </p>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <!-- Quick Stats Card for Authenticated Users -->
        <v-card
          v-if="authStore.isAuthenticated"
          class="mt-8"
          elevation="2">
          <v-card-title>
            <v-icon
              left
              color="primary"
              >mdi-chart-box-outline</v-icon
            >
            Quick Overview
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col
                cols="6"
                sm="3"
                class="text-center">
                <div class="display-1 font-weight-bold text--primary">{{ itemsStore.itemsCount }}</div>
                <div class="caption">Research Papers</div>
              </v-col>
              <v-col
                cols="6"
                sm="3"
                class="text-center">
                <div class="display-1 font-weight-bold text--secondary">{{ stats.studySites }}</div>
                <div class="caption">Study Sites</div>
              </v-col>
              <v-col
                cols="6"
                sm="3"
                class="text-center">
                <div class="display-1 font-weight-bold text--accent">{{ stats.keywords }}</div>
                <div class="caption">Keywords</div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useZoteroStore } from '@/stores/zotero'

const router = useRouter()
const authStore = useAuthStore()
const itemsStore = useZoteroStore()

// Mock data - replace with actual API calls
const stats = ref({ studySites: 0, keywords: 0 })

const recentActivities = ref([
  {
    id: 1,
    title: 'New research paper imported',
    subtitle: 'Climate impact study from Zotero',
    time: '2 hours ago',
    icon: 'mdi-file-document-plus',
    color: 'primary',
  },
  {
    id: 2,
    title: 'Study site coordinates updated',
    subtitle: 'Location validation completed',
    time: '1 day ago',
    icon: 'mdi-map-marker',
    color: 'secondary',
  },
  {
    id: 3,
    title: 'Data analysis completed',
    subtitle: 'Regional temperature trends',
    time: '3 days ago',
    icon: 'mdi-chart-line',
    color: 'success',
  },
])

// Load user statistics
const loadUserStats = async () => {
  if (authStore.isAuthenticated) {
    try {
      // Replace these with actual API calls to your backend
      // const response = await axios.get('/users/stats')
      // stats.value = response.data

      // Mock data for demonstration
      stats.value = { studySites: 15, keywords: 8 }
    } catch (error) {
      console.error('Error loading user stats:', error)
    }
  }
}

onMounted(async () => {
  // Initialize auth and load stats
  await authStore.initializeAuth()
  await loadUserStats()
})
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}

.fill-height {
  min-height: calc(100vh - 100px); /* Account for top navigation */
}
</style>
