<template>
  <v-container
    fluid
    class="pa-0"
    style="height: calc(100vh - 64px)"
    @keydown.esc="selectedSite = null; selectedPaper = null">
    <v-row
      no-gutters
      class="fill-height">
      <!-- Papers Sidebar (Left) -->
      <v-col
        cols="12"
        md="3"
        class="fill-height sidebar sidebar-left">
        <v-card
          class="fill-height d-flex flex-column"
          elevation="1">
          <v-card-title class="d-flex align-center justify-space-between">
            <span>Papers</span>
            <div class="d-flex align-center gap-2">
              <v-btn
                v-if="authStore.isAuthenticated"
                icon
                size="small"
                variant="text"
                :loading="mapPapersLoading"
                @click="refreshPapers"
                >
                <v-icon>mdi-refresh</v-icon>
                <v-tooltip
                  activator="parent"
                  location="bottom">
                  Refresh papers
                </v-tooltip>
              </v-btn>
              <v-chip
                :color="selectedPaper ? 'primary' : 'default'"
                size="small">
                {{ totalPapers }} papers
              </v-chip>
            </div>
          </v-card-title>

          <v-card-text
            v-if="authStore.isAuthenticated"
            class="pt-2 pb-0"
          >
            <v-btn-toggle
              v-model="papersScope"
              mandatory
              density="compact"
              class="w-100"
            >
              <v-btn value="all" prepend-icon="mdi-earth" class="flex-grow-1">All Papers</v-btn>
              <v-btn value="mine" prepend-icon="mdi-account" class="flex-grow-1">Just Mine</v-btn>
            </v-btn-toggle>
          </v-card-text>

          <v-divider />

          <!-- Filters -->
          <v-card-text class="flex-grow-0">
            <v-text-field
              v-model="paperSearchQuery"
              label="Search papers"
              prepend-inner-icon="mdi-magnify"
              clearable
              density="compact"
              variant="outlined"
              hide-details
              class="mb-3" />

            <v-select
              v-model="paperFilterType"
              :items="paperFilterOptions"
              label="Filter papers"
              prepend-inner-icon="mdi-filter"
              density="compact"
              variant="outlined"
              hide-details />
          </v-card-text>

          <v-divider />

          <!-- Papers List -->
          <v-card-text class="flex-grow-1 overflow-y-auto pa-0">
            <v-virtual-scroll
              v-if="filteredPapers.length > 0"
              :items="filteredPapers"
              :item-height="72"
              item-key="id"
              class="fill-height">
              <template #default="{ item: paper }">
                <v-list-item
                  :active="selectedPaper?.id === paper.id"
                  @click="handlePaperClick(paper)"
                  class="cursor-pointer"
                  density="compact">
                  <template #prepend>
                    <v-avatar
                      color="primary"
                      size="32">
                      <v-icon
                        size="16"
                        color="white">
                        mdi-file-document
                      </v-icon>
                    </v-avatar>
                  </template>

                  <v-list-item-title class="text-wrap">
                    {{ paper.title || 'Untitled Paper' }}
                  </v-list-item-title>

                  <v-list-item-subtitle class="text-wrap">
                    {{ formatPaperSubtitle(paper) }}
                  </v-list-item-subtitle>

                  <template #append>
                    <div class="d-flex flex-column align-end gap-1">
                      <v-chip
                        v-if="paper.study_site_count > 0"
                        color="primary"
                        size="x-small"
                        @click.stop="showPaperStudySites(paper)">
                        <v-icon start size="x-small">mdi-map-marker</v-icon>
                        {{ paper.study_site_count }}
                      </v-chip>
                      <v-chip
                        v-else
                        size="x-small"
                        color="default"
                        variant="outlined">
                        <v-icon size="x-small">mdi-minus</v-icon>
                      </v-chip>
                    </div>
                  </template>
                </v-list-item>
              </template>
            </v-virtual-scroll>

            <v-empty-state
              v-else
              icon="mdi-file-document-off"
              title="No papers found"
              :text="authStore.isAuthenticated ? 'Try adjusting your filters or sync your library' : 'Try adjusting your filters'" />
          </v-card-text>

          <v-divider />

          <!-- Actions -->
          <v-card-actions class="flex-grow-0">
            <v-btn
              v-if="selectedPaper"
              block
              variant="outlined"
              prepend-icon="mdi-close"
              @click="clearPaperSelection">
              Clear Selection
            </v-btn>
            <v-btn
              v-else
              v-if="authStore.isAuthenticated"
              block
              color="primary"
              prepend-icon="mdi-refresh"
              @click="refreshPapers"
              :loading="mapPapersLoading">
              Refresh
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Map Section -->
      <v-col
        cols="12"
        md="6"
        class="fill-height">
        <StudySiteMap
          ref="mapComponent"
          :initial-center="[0, 20]"
          :initial-zoom="2"
          :sites="filteredSites"
          :regions="regionsStore.regions"
          :buffer-features="bufferFeatures"
          @site-selected="handleSiteSelected"
          @viewport-changed="handleViewportChanged"
          @map-ready="handleMapReady"
          @region-selected="handleRegionSelected" />
      </v-col>

      <!-- Right Sidebar (Study Sites / Regions) -->
      <v-col
        cols="12"
        md="3"
        class="fill-height sidebar sidebar-right">
        <v-card
          class="fill-height d-flex flex-column"
          elevation="1">

          <!-- Tabs -->
          <div class="right-sidebar-header">
            <v-tabs
              v-model="rightTab"
              density="compact"
              grow>
              <v-tab value="sites">
                <v-icon start size="small">mdi-map-marker</v-icon>
                Sites
                <v-chip size="x-small" class="ml-1">{{ totalSites }}</v-chip>
              </v-tab>
              <v-tab value="regions">
                <v-icon start size="small">mdi-shape-polygon-plus</v-icon>
                Regions
                <v-chip v-if="regionsStore.regionCount > 0" size="x-small" class="ml-1">{{ regionsStore.regionCount }}</v-chip>
              </v-tab>
            </v-tabs>

            <v-divider />
          </div>

          <!-- Study Sites Tab -->
          <template v-if="rightTab === 'sites'">
            <!-- Filters -->
            <v-card-text class="flex-grow-0">
              <v-text-field
                v-model="searchQuery"
                label="Search sites or papers"
                prepend-inner-icon="mdi-magnify"
                clearable
                density="compact"
                variant="outlined"
                hide-details
                class="mb-3" />

              <v-select
                v-model="filterType"
                :items="filterOptions"
                label="Filter by type"
                prepend-inner-icon="mdi-filter"
                density="compact"
                variant="outlined"
                hide-details />
            </v-card-text>

            <v-divider />

            <!-- Info Banner -->
            <v-alert
              v-if="showExtractionInfoBanner"
              type="info"
              variant="tonal"
              density="compact"
              class="ma-3 mb-2">
              <div class="text-caption">
                <v-icon size="small" class="mr-1">mdi-information</v-icon>
                {{ authStore.isAuthenticated
                  ? 'Study sites appear after extraction tasks complete. Click refresh to see new sites.'
                  : 'Browse extracted study sites and map output. Sign in to run extraction tasks.' }}
              </div>
            </v-alert>

            <!-- Sites List (virtualized) -->
            <v-card-text class="flex-grow-1 overflow-y-auto pa-0">
              <v-virtual-scroll
                v-if="filteredSites.length > 0"
                :items="filteredSites"
                :item-height="64"
                item-key="id"
                class="fill-height">
                <template #default="{ item: site }">
                  <v-list-item
                    :active="selectedSite?.id === site.id"
                    @click="handleSiteClick(site)"
                    density="compact"
                    class="cursor-pointer">
                    <template #prepend>
                      <v-avatar
                        :color="site.is_manual ? 'success' : 'info'"
                        size="32">
                        <v-icon
                          size="16"
                          color="white">
                          {{ site.is_manual ? 'mdi-account' : 'mdi-robot' }}
                        </v-icon>
                      </v-avatar>
                    </template>

                    <v-list-item-title class="text-wrap">
                      {{ site.name || 'Unnamed Site' }}
                    </v-list-item-title>

                    <v-list-item-subtitle class="text-wrap">
                      {{ site.item_title || 'Unknown Paper' }}
                    </v-list-item-subtitle>

                    <template #append>
                      <v-chip
                        size="x-small"
                        :color="site.is_manual ? 'success' : 'info'">
                        {{ site.is_manual ? 'Manual' : 'Auto' }}
                      </v-chip>
                    </template>
                  </v-list-item>
                </template>
              </v-virtual-scroll>

              <v-empty-state
                v-else
                icon="mdi-map-marker-off"
                title="No study sites found"
                text="Try adjusting your filters" />
            </v-card-text>

            <v-divider />

            <!-- Actions -->
            <v-card-actions class="flex-grow-0">
              <v-btn
                v-if="authStore.isAuthenticated"
                block
                color="primary"
                prepend-icon="mdi-refresh"
                @click="refreshData"
                :loading="loading">
                Refresh
              </v-btn>
            </v-card-actions>

            <!-- Legend -->
            <v-card-text class="flex-grow-0 pt-2 pb-3">
              <div class="text-caption text-medium-emphasis mb-2">Legend:</div>
              <div class="d-flex align-center mb-1">
                <v-icon
                  color="success"
                  size="small"
                  class="mr-2"
                  >mdi-circle</v-icon
                >
                <span class="text-caption">Manual (Human-created)</span>
              </div>
              <div class="d-flex align-center mb-1">
                <v-icon
                  color="info"
                  size="small"
                  class="mr-2"
                  >mdi-circle</v-icon
                >
                <span class="text-caption">Automatic (Algorithm-extracted)</span>
              </div>
              <div class="d-flex align-center">
                <v-icon
                  color="orange"
                  size="small"
                  class="mr-2"
                  >mdi-square-rounded-outline</v-icon
                >
                <span class="text-caption">Uploaded Region</span>
              </div>
            </v-card-text>
          </template>

          <!-- Regions Tab -->
          <template v-if="rightTab === 'regions'">
            <!-- Upload Button -->
            <v-card-text
              v-if="authStore.isAuthenticated"
              class="flex-grow-0">
              <v-btn
                block
                color="primary"
                variant="outlined"
                prepend-icon="mdi-upload"
                @click="uploadDialogOpen = true">
                Upload Shapefile
              </v-btn>
            </v-card-text>

            <!-- GIS Tools -->
            <v-card-text
              v-if="authStore.isAuthenticated"
              class="flex-grow-0 pt-0">
              <div class="text-caption text-medium-emphasis mb-2">GIS Tools</div>

              <v-select
                v-model="gisOperation"
                :items="gisOperationOptions"
                label="Operation"
                density="compact"
                variant="outlined"
                hide-details
                class="mb-2" />

              <v-alert
                v-if="gisOperationOptions.length === 0"
                type="info"
                variant="tonal"
                density="compact">
                No GIS operations are available for your account.
              </v-alert>

              <template v-else>
                <v-select
                  v-model="selectedRegionIdForClip"
                  :items="regionSelectOptions"
                  label="Region filter / target (optional)"
                  density="compact"
                  variant="outlined"
                  hide-details
                  class="mb-2" />

                <template v-if="gisOperation === 'buffer'">
                  <v-text-field
                    v-model.number="bufferDistance"
                    type="number"
                    min="1"
                    label="Distance"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-2" />

                  <v-select
                    v-model="bufferUnit"
                    :items="bufferUnitOptions"
                    label="Unit"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-2" />

                  <v-btn
                    block
                    variant="text"
                    size="small"
                    class="mb-2"
                    @click="bufferDissolve = !bufferDissolve">
                    Dissolve Regions: {{ bufferDissolve ? 'On' : 'Off' }}
                  </v-btn>

                  <v-btn
                    block
                    color="primary"
                    prepend-icon="mdi-layers-plus"
                    :loading="runningOperation"
                    :disabled="!canRunBuffer || bufferDistance <= 0"
                    @click="runBufferOperation">
                    Run Buffer
                  </v-btn>
                </template>

                <template v-else-if="gisOperation === 'clip'">
                  <v-btn
                    block
                    color="primary"
                    prepend-icon="mdi-content-cut"
                    :loading="runningOperation"
                    :disabled="!canRunClip || !selectedRegionIdForClip"
                    @click="runClipOperation">
                    Run Clip
                  </v-btn>
                </template>

                <template v-else-if="gisOperation === 'within-distance'">
                  <v-text-field
                    v-model.number="withinDistanceDistance"
                    type="number"
                    min="1"
                    label="Distance"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-2" />

                  <v-select
                    v-model="withinDistanceUnit"
                    :items="bufferUnitOptions"
                    label="Unit"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-2" />

                  <v-select
                    v-model="withinDistanceReturnLayer"
                    :items="withinDistanceReturnOptions"
                    label="Return Layer"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-2" />

                  <v-btn
                    block
                    color="primary"
                    prepend-icon="mdi-map-search"
                    :loading="runningOperation"
                    :disabled="!canRunWithinDistance || withinDistanceDistance <= 0"
                    @click="runWithinDistanceOperation">
                    Run Within Distance
                  </v-btn>
                </template>

                <template v-else>
                  <v-select
                    v-model="summaryGroupBy"
                    :items="summaryGroupByOptions"
                    label="Group By"
                    density="compact"
                    variant="outlined"
                    hide-details
                    class="mb-2" />

                  <v-btn
                    block
                    variant="text"
                    size="small"
                    class="mb-1"
                    @click="summaryIncludeCount = !summaryIncludeCount">
                    Include Site Count: {{ summaryIncludeCount ? 'On' : 'Off' }}
                  </v-btn>

                  <v-btn
                    block
                    variant="text"
                    size="small"
                    class="mb-2"
                    @click="summaryIncludeAvgConfidence = !summaryIncludeAvgConfidence">
                    Include Avg Confidence: {{ summaryIncludeAvgConfidence ? 'On' : 'Off' }}
                  </v-btn>

                  <v-btn
                    block
                    color="primary"
                    prepend-icon="mdi-chart-box-outline"
                    :loading="runningOperation"
                    :disabled="!canRunSummaryStats || selectedSummaryMetrics.length === 0"
                    @click="runSummaryStatsOperation">
                    Run Summary Stats
                  </v-btn>
                </template>

                <v-btn
                  block
                  variant="outlined"
                  color="secondary"
                  size="small"
                  class="mt-2"
                  @click="clearGisResults">
                  Clear GIS Results
                </v-btn>

                <div
                  v-if="withinDistanceRegions.length > 0"
                  class="mt-3">
                  <div class="text-caption text-medium-emphasis mb-1">Within-distance Regions:</div>
                  <v-chip
                    v-for="region in withinDistanceRegions"
                    :key="region.id"
                    size="x-small"
                    class="mr-1 mb-1"
                    @click="handleRegionSelected(region.id)">
                    {{ region.name }}
                  </v-chip>
                </div>

                <div
                  v-if="summaryStatsRows.length > 0"
                  class="mt-3">
                  <div class="text-caption text-medium-emphasis mb-1">
                    Summary rows: {{ summaryStatsCount }}
                  </div>
                  <v-list density="compact" class="bg-transparent pa-0">
                    <v-list-item
                      v-for="(row, idx) in summaryStatsRows"
                      :key="`summary-row-${idx}`"
                      class="px-0">
                      <v-list-item-title class="text-caption text-wrap">
                        {{ formatSummaryRow(row) }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </div>
              </template>

              <!-- Export -->
              <div class="text-caption text-medium-emphasis mt-3 mb-2">Export</div>
              <v-btn
                block
                variant="outlined"
                size="small"
                prepend-icon="mdi-map-marker-path"
                class="mb-1"
                @click="exportStudySites('geojson')">
                Export Sites (GeoJSON)
              </v-btn>
              <v-btn
                block
                variant="outlined"
                size="small"
                prepend-icon="mdi-file-delimited"
                class="mb-1"
                @click="exportStudySites('csv')">
                Export Sites (CSV)
              </v-btn>
              <v-btn
                block
                variant="outlined"
                size="small"
                prepend-icon="mdi-book-open-variant"
                @click="exportItems('bibtex')">
                Export Papers (BibTeX)
              </v-btn>
            </v-card-text>

            <v-divider />

            <!-- Region Stats Panel (shown when region selected) -->
            <template v-if="regionsStore.selectedRegion && regionsStore.regionStats">
              <v-card-text class="flex-grow-0">
                <div class="d-flex align-center justify-space-between mb-2">
                  <div class="text-subtitle-2 font-weight-bold">
                    {{ regionsStore.selectedRegion.name }}
                  </div>
                  <v-btn
                    icon
                    size="x-small"
                    variant="text"
                    @click="regionsStore.selectRegion(null)">
                    <v-icon size="small">mdi-close</v-icon>
                  </v-btn>
                </div>

                <div class="d-flex gap-4 mb-3">
                  <div class="stat-item">
                    <div class="stat-value">{{ regionsStore.regionStats.study_site_count }}</div>
                    <div class="stat-label">Sites</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-value">{{ regionsStore.regionStats.paper_count }}</div>
                    <div class="stat-label">Papers</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-value text-success">{{ regionsStore.regionStats.manual_count }}</div>
                    <div class="stat-label">Manual</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-value text-info">{{ regionsStore.regionStats.automatic_count }}</div>
                    <div class="stat-label">Auto</div>
                  </div>
                </div>

                <!-- Extraction Methods -->
                <div v-if="Object.keys(regionsStore.regionStats.extraction_methods).length > 0" class="mb-3">
                  <div class="text-caption text-medium-emphasis mb-1">Extraction Methods:</div>
                  <v-chip
                    v-for="(count, method) in regionsStore.regionStats.extraction_methods"
                    :key="method"
                    size="x-small"
                    class="mr-1 mb-1">
                    {{ formatExtractionMethod(String(method)) }}: {{ count }}
                  </v-chip>
                </div>

                <!-- Papers in Region -->
                <div v-if="regionsStore.regionStats.papers.length > 0">
                  <div class="text-caption text-medium-emphasis mb-1">Papers in region:</div>
                  <v-list density="compact" class="bg-transparent pa-0">
                    <v-list-item
                      v-for="paper in regionsStore.regionStats.papers"
                      :key="paper.id"
                      density="compact"
                      class="px-0"
                      @click="filterPaperById(paper.id)">
                      <v-list-item-title class="text-caption text-wrap">
                        {{ paper.title || 'Untitled' }}
                      </v-list-item-title>
                    </v-list-item>
                  </v-list>
                </div>
              </v-card-text>

              <v-divider />
            </template>

            <!-- Regions List -->
            <v-card-text class="flex-grow-1 overflow-y-auto pa-0">
              <v-list
                v-if="regionsStore.regions.length > 0"
                density="compact">
                <v-list-item
                  v-for="region in regionsStore.regions"
                  :key="region.id"
                  :active="regionsStore.selectedRegion?.id === region.id"
                  @click="handleRegionClick(region)"
                  class="cursor-pointer">
                  <template #prepend>
                    <v-avatar
                      color="orange"
                      size="32">
                      <v-icon
                        size="16"
                        color="white">
                        mdi-shape-polygon-plus
                      </v-icon>
                    </v-avatar>
                  </template>

                  <v-list-item-title class="text-wrap">
                    {{ region.name }}
                  </v-list-item-title>

                  <v-list-item-subtitle v-if="region.source_filename" class="text-wrap">
                    {{ region.source_filename }}
                  </v-list-item-subtitle>

                  <template #append>
                    <v-btn
                      icon
                      size="x-small"
                      variant="text"
                      color="error"
                      @click.stop="confirmDeleteRegion(region)">
                      <v-icon size="small">mdi-delete</v-icon>
                      <v-tooltip activator="parent" location="top">Delete</v-tooltip>
                    </v-btn>
                  </template>
                </v-list-item>
              </v-list>

              <v-empty-state
                v-else
                icon="mdi-shape-polygon-plus"
                title="No regions uploaded"
                text="Upload a shapefile to view spatial statistics" />
            </v-card-text>
          </template>
        </v-card>
      </v-col>
    </v-row>

    <!-- Paper Study Sites Dialog -->
    <v-dialog
      v-model="studySitesDialog"
      max-width="900"
      scrollable>
      <v-card v-if="dialogPaper">
        <v-card-title class="d-flex align-center justify-space-between">
          <div>
            <div class="text-h6">Study Sites</div>
            <div class="text-subtitle-2 text-medium-emphasis">{{ dialogPaper.title }}</div>
          </div>
          <v-btn
            icon="mdi-close"
            variant="text"
            @click="studySitesDialog = false" />
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-alert
            v-if="paperStudySitesLoading"
            type="info"
            variant="tonal"
            class="mb-4">
            Loading study sites...
          </v-alert>

          <v-alert
            v-else-if="!dialogPaper.study_sites || dialogPaper.study_sites.length === 0"
            type="info"
            variant="tonal"
            class="mb-4">
            No study sites have been extracted for this paper yet.
          </v-alert>

          <v-list
            v-else
            lines="three"
            class="bg-transparent">
            <v-list-item
              v-for="(site, index) in dialogPaper.study_sites"
              :key="site.id"
              class="mb-3 pa-3"
              border
              rounded>
              <template #prepend>
                <v-avatar
                  :color="site.is_manual ? 'success' : 'info'"
                  size="48">
                  <v-icon
                    size="24"
                    color="white">
                    {{ site.is_manual ? 'mdi-account' : 'mdi-robot' }}
                  </v-icon>
                </v-avatar>
              </template>

              <v-list-item-title class="text-h6 mb-2">
                {{ site.name || `Study Site ${Number(index) + 1}` }}
              </v-list-item-title>

              <v-list-item-subtitle class="text-body-2">
                <div class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-map-marker</v-icon>
                  <strong>Location:</strong>
                  {{ site.location?.latitude?.toFixed(4) }}, {{ site.location?.longitude?.toFixed(4) }}
                </div>

                <div v-if="site.context" class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-text</v-icon>
                  <strong>Context:</strong>
                  <div class="mt-1 text-medium-emphasis context-text">
                    {{ site.context }}
                  </div>
                </div>

                <div class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-chart-line</v-icon>
                  <strong>Confidence:</strong>
                  {{ (site.confidence_score * 100).toFixed(1) }}%
                  <v-progress-linear
                    :model-value="site.confidence_score * 100"
                    :color="getConfidenceColor(site.confidence_score)"
                    height="6"
                    rounded
                    class="mt-1" />
                </div>

                <div class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-information</v-icon>
                  <strong>Method:</strong> {{ formatExtractionMethod(site.extraction_method) }}
                  <v-chip
                    :color="site.is_manual ? 'success' : 'info'"
                    size="x-small"
                    class="ml-2">
                    {{ site.is_manual ? 'Manual' : 'Automatic' }}
                  </v-chip>
                </div>

                <div v-if="site.section" class="mb-2">
                  <v-icon size="small" class="mr-1">mdi-book-open-page-variant</v-icon>
                  <strong>Section:</strong> {{ site.section }}
                </div>
              </v-list-item-subtitle>

              <template #append>
                <v-btn
                  icon
                  variant="text"
                  size="small"
                  @click="panToStudySite(site)">
                  <v-icon>mdi-crosshairs-gps</v-icon>
                  <v-tooltip activator="parent" location="top">
                    View on Map
                  </v-tooltip>
                </v-btn>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>

        <v-divider />

        <v-card-actions>
          <v-spacer />
          <v-btn @click="studySitesDialog = false">Close</v-btn>
          <v-btn
            v-if="dialogPaper.study_sites && dialogPaper.study_sites.length > 0"
            color="primary"
            @click="filterByDialogPaper">
            Show on Map
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <!-- Shapefile Upload Dialog -->
    <ShapefileUploadDialog
      v-if="authStore.isAuthenticated"
      v-model="uploadDialogOpen"
      @uploaded="handleShapefileUploaded" />

    <!-- Delete Region Confirmation -->
    <v-dialog v-model="deleteRegionDialog" max-width="400">
      <v-card>
        <v-card-title>Delete Region</v-card-title>
        <v-card-text>
          Are you sure you want to delete "{{ regionToDelete?.name }}"?
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteRegionDialog = false">Cancel</v-btn>
          <v-btn color="error" variant="elevated" @click="executeDeleteRegion">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import api from '@/services/api'
import { useAuthStore } from '../stores/auth'
import { useNotificationStore } from '../stores/notification'
import { useStudySitesStore, type MapPoint } from '../stores/studySites'
import { useRegionsStore, type Region } from '../stores/regions'
import { useGisStore, type GISMetric } from '../stores/gis'
import { useZoteroStore } from '../stores/zotero'
import StudySiteMap from '../components/maps/StudySiteMap.vue'
import ShapefileUploadDialog from '../components/maps/ShapefileUploadDialog.vue'
import logger from '@/utils/logger'

interface MapPaperSummary {
  id: string
  title: string | null
  publicationTitle?: string | null
  date?: string | null
  study_site_count: number
}

interface ViewportBounds {
  minLon: number
  minLat: number
  maxLon: number
  maxLat: number
}

// Route
const route = useRoute()

// Stores
const authStore = useAuthStore()
const notificationStore = useNotificationStore()
const studySitesStore = useStudySitesStore()
const regionsStore = useRegionsStore()
const gisStore = useGisStore()
const zoteroStore = useZoteroStore()
const { mapPoints, loading } = storeToRefs(studySitesStore)
const {
  capabilities,
  bufferFeatures,
  clippedStudySites,
  withinDistanceStudySites,
  withinDistanceRegions,
  summaryStatsRows,
  summaryStatsCount,
  runningOperation,
  asyncTaskStatus,
  presets,
} = storeToRefs(gisStore)

// State - Study Sites
const selectedSite = ref<MapPoint | null>(null)
const searchQuery = ref('')
const filterType = ref('all')
const mapReady = ref(false)
const mapComponent = ref<InstanceType<typeof StudySiteMap> | null>(null)

// State - Papers
const selectedPaper = ref<any | null>(null)
const paperSearchQuery = ref('')
const paperFilterType = ref('all')
const studySitesDialog = ref(false)
const dialogPaper = ref<any | null>(null)
const mapPapers = ref<MapPaperSummary[]>([])
const mapPapersLoading = ref(false)
const paperStudySitesLoading = ref(false)
const activeViewport = ref<ViewportBounds | null>(null)
const useClippedResult = ref(false)
const useWithinDistanceResult = ref(false)
const papersScope = ref<'all' | 'mine'>('all')

// State - GIS operations
const gisOperation = ref<'buffer' | 'clip' | 'within-distance' | 'summary-stats'>('buffer')
const bufferDistance = ref(1000)
const bufferUnit = ref<'meter' | 'kilometer'>('meter')
const bufferDissolve = ref(false)
const selectedRegionIdForClip = ref<string | null>(null)
const withinDistanceDistance = ref(1000)
const withinDistanceUnit = ref<'meter' | 'kilometer'>('meter')
const withinDistanceReturnLayer = ref<'source' | 'against'>('source')
const summaryGroupBy = ref<string>('is_manual')
const summaryIncludeCount = ref(true)
const summaryIncludeAvgConfidence = ref(true)

// State - Right sidebar
const rightTab = ref('sites')
const uploadDialogOpen = ref(false)
const deleteRegionDialog = ref(false)
const regionToDelete = ref<Region | null>(null)

// Filter options - Study Sites
const filterOptions = [
  { title: 'All Sites', value: 'all' },
  { title: 'Manual Only', value: 'manual' },
  { title: 'Automatic Only', value: 'automatic' },
]

// Filter options - Papers
const paperFilterOptions = [
  { title: 'All Papers', value: 'all' },
  { title: 'With Study Sites', value: 'with_sites' },
  { title: 'Without Study Sites', value: 'without_sites' },
]

const gisOperationOptions = computed(() => {
  const options = [
    { title: 'Buffer', value: 'buffer' as const },
    { title: 'Clip', value: 'clip' as const },
    { title: 'Within Distance', value: 'within-distance' as const },
    { title: 'Summary Stats', value: 'summary-stats' as const },
  ]
  const enabledIds = new Set(capabilities.value.filter((op) => op.enabled).map((op) => op.id))
  return options.filter((option) => enabledIds.has(option.value))
})

const bufferUnitOptions = [
  { title: 'Meters', value: 'meter' },
  { title: 'Kilometers', value: 'kilometer' },
]

const withinDistanceReturnOptions = [
  { title: 'Study Sites', value: 'source' },
  { title: 'Regions', value: 'against' },
]

const summaryGroupByOptions = [
  { title: 'Manual vs Auto', value: 'is_manual' },
  { title: 'Extraction Method', value: 'extraction_method' },
  { title: 'Paper Title', value: 'item_title' },
]

const regionSelectOptions = computed(() => regionsStore.regions.map((region) => ({
  title: region.name,
  value: region.id,
})))

// Computed - Papers
const papers = computed(() => mapPapers.value)

const totalPapers = computed(() => papers.value.length)

const filteredPapers = computed(() => {
  let result = papers.value

  // Filter by type
  if (paperFilterType.value === 'with_sites') {
    result = result.filter((p: any) => (p.study_site_count || 0) > 0)
  } else if (paperFilterType.value === 'without_sites') {
    result = result.filter((p: any) => (p.study_site_count || 0) === 0)
  }

  // Filter by search query
  if (paperSearchQuery.value) {
    const query = paperSearchQuery.value.toLowerCase()
    result = result.filter(
      (p: any) =>
        p.title?.toLowerCase().includes(query) ||
        p.abstractNote?.toLowerCase().includes(query) ||
        p.publicationTitle?.toLowerCase().includes(query),
    )
  }

  return result
})

const activeSites = computed(() =>
  useClippedResult.value
    ? clippedStudySites.value
    : (useWithinDistanceResult.value && withinDistanceReturnLayer.value === 'source')
      ? withinDistanceStudySites.value
      : mapPoints.value,
)

// Computed - Study Sites (uses lightweight MapPoint[])
const totalSites = computed(() => activeSites.value.length)

const filteredSites = computed(() => {
  let sites = activeSites.value

  // Filter by selected paper
  if (selectedPaper.value) {
    sites = sites.filter((s) => s.item_id === selectedPaper.value.id)
  }

  // Filter by type
  if (filterType.value === 'manual') {
    sites = sites.filter((s) => s.is_manual)
  } else if (filterType.value === 'automatic') {
    sites = sites.filter((s) => !s.is_manual)
  }

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    sites = sites.filter(
      (s) =>
        s.name?.toLowerCase().includes(query) ||
        s.item_title?.toLowerCase().includes(query),
    )
  }

  return sites
})

const showExtractionInfoBanner = computed(() => {
  if (!authStore.isAuthenticated) {
    return false
  }

  return totalSites.value === 0
})

const availableOperationIds = computed(() =>
  capabilities.value.filter((op) => op.enabled).map((op) => op.id),
)

const canRunBuffer = computed(() => availableOperationIds.value.includes('buffer'))
const canRunClip = computed(() => availableOperationIds.value.includes('clip'))
const canRunWithinDistance = computed(() => availableOperationIds.value.includes('within-distance'))
const canRunSummaryStats = computed(() => availableOperationIds.value.includes('summary-stats'))

const selectedSummaryMetrics = computed<GISMetric[]>(() => {
  const metrics: GISMetric[] = []
  if (summaryIncludeCount.value) {
    metrics.push({ type: 'count', field: 'id', alias: 'site_count' })
  }
  if (summaryIncludeAvgConfidence.value) {
    metrics.push({ type: 'avg', field: 'confidence_score', alias: 'avg_confidence' })
  }
  return metrics
})

const fetchMapPapers = async () => {
  mapPapersLoading.value = true
  try {
    const response = await zoteroStore.fetchMapItems(500, papersScope.value)
    mapPapers.value = response?.data || []
  } finally {
    mapPapersLoading.value = false
  }
}

const fetchMapPointsForViewport = async (bounds: ViewportBounds) => {
  activeViewport.value = bounds
  await studySitesStore.fetchMapPointsForBounds(bounds, 25000, true)
}

const handleViewportChanged = async (bounds: ViewportBounds) => {
  await fetchMapPointsForViewport(bounds)
}

const runBufferOperation = async () => {
  if (!canRunBuffer.value) return
  useWithinDistanceResult.value = false

  const target = selectedRegionIdForClip.value
    ? {
        layer_id: 'regions' as const,
        selection: {
          type: 'ids' as const,
          ids: [selectedRegionIdForClip.value],
        },
      }
    : {
        layer_id: 'study-sites' as const,
        selection: { type: 'all' as const },
      }

  await gisStore.runBuffer(target, {
    distance: bufferDistance.value,
    unit: bufferUnit.value,
    dissolve: bufferDissolve.value,
  })
}

const runClipOperation = async () => {
  if (!canRunClip.value || !selectedRegionIdForClip.value) return
  useWithinDistanceResult.value = false

  const result = await gisStore.runClip(
    {
      layer_id: 'study-sites',
      selection: { type: 'all' },
    },
    {
      layer_id: 'regions',
      selection: { type: 'ids', ids: [selectedRegionIdForClip.value] },
    },
  )

  if (result) {
    useClippedResult.value = true
    rightTab.value = 'sites'
  }
}

const runWithinDistanceOperation = async () => {
  if (!canRunWithinDistance.value || withinDistanceDistance.value <= 0) return

  const regionRef = selectedRegionIdForClip.value
    ? {
        layer_id: 'regions' as const,
        selection: {
          type: 'ids' as const,
          ids: [selectedRegionIdForClip.value],
        },
      }
    : {
        layer_id: 'regions' as const,
        selection: { type: 'all' as const },
      }

  const result = await gisStore.runWithinDistance(
    {
      layer_id: 'study-sites',
      selection: { type: 'all' },
    },
    regionRef,
    {
      distance: withinDistanceDistance.value,
      unit: withinDistanceUnit.value,
      return: withinDistanceReturnLayer.value,
    },
  )

  if (!result) return

  useClippedResult.value = false
  useWithinDistanceResult.value = result.return_layer_id === 'study-sites'
  rightTab.value = result.return_layer_id === 'study-sites' ? 'sites' : 'regions'
}

const runSummaryStatsOperation = async () => {
  if (!canRunSummaryStats.value || selectedSummaryMetrics.value.length === 0) return

  const spatialFilter = selectedRegionIdForClip.value
    ? {
        layer_id: 'regions' as const,
        selection: {
          type: 'ids' as const,
          ids: [selectedRegionIdForClip.value],
        },
        predicate: 'within' as const,
      }
    : undefined

  await gisStore.runSummaryStats({
    target: {
      layer_id: 'study-sites',
      selection: { type: 'all' },
    },
    group_by: summaryGroupBy.value ? [summaryGroupBy.value] : [],
    metrics: selectedSummaryMetrics.value,
    spatial_filter: spatialFilter,
  })
}

const clearGisResults = () => {
  useClippedResult.value = false
  useWithinDistanceResult.value = false
  gisStore.clearResults()
}

// --- Export ---

const triggerDownload = (data: string, filename: string, mimeType: string) => {
  const blob = new Blob([data], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const exportStudySites = async (format: 'geojson' | 'csv') => {
  try {
    const params: Record<string, string> = { format }
    if (selectedPaper.value?.id) {
      params.item_id = selectedPaper.value.id
    }
    const response = await api.get('/export/study-sites', { params })
    const ext = format === 'geojson' ? 'geojson' : 'csv'
    const mime = format === 'geojson' ? 'application/geo+json' : 'text/csv'
    const content = typeof response.data === 'string' ? response.data : JSON.stringify(response.data, null, 2)
    triggerDownload(content, `study_sites.${ext}`, mime)
  } catch {
    notificationStore.showNotification('Export failed', 'error')
  }
}

const exportItems = async (format: 'bibtex') => {
  try {
    const response = await api.get('/export/items', { params: { format } })
    triggerDownload(response.data, 'references.bib', 'application/x-bibtex')
  } catch {
    notificationStore.showNotification('Export failed', 'error')
  }
}

/**
 * Handle site selection from map
 */
const handleSiteSelected = (site: MapPoint) => {
  if (selectedSite.value?.id === site.id) {
    selectedSite.value = null
    return
  }
  selectedSite.value = site
}

/**
 * Handle site click from list - Pan map to location
 */
const handleSiteClick = (site: MapPoint) => {
  if (!site) {
    logger.warn('Invalid site clicked')
    return
  }

  // Toggle selection
  if (selectedSite.value?.id === site.id) {
    selectedSite.value = null
  } else {
    selectedSite.value = site
  }

  if (!mapComponent.value) {
    logger.warn('Map component not initialized yet')
    return
  }

  if (site.latitude == null || site.longitude == null) {
    logger.warn(`Site "${site.name}" has no valid location data`)
    return
  }

  // Pan to site location with zoom level 12
  mapComponent.value.panTo(site.latitude, site.longitude, 12, 1500)
}

/**
 * Handle map ready
 */
const handleMapReady = (map: any) => {
  mapReady.value = true
}

/**
 * Refresh data
 */
const refreshData = async () => {
  if (activeViewport.value) {
    await studySitesStore.fetchMapPointsForBounds(activeViewport.value, 25000, false)
  }
}

/**
 * Refresh sites (alias for refreshData)
 */
const refreshSites = refreshData

/**
 * Refresh papers
 */
const refreshPapers = async () => {
  await fetchMapPapers()
}

/**
 * Handle paper click - Filter study sites by paper
 */
const handlePaperClick = (paper: any) => {
  if (selectedPaper.value?.id === paper.id) {
    // Toggle off if already selected
    selectedPaper.value = null
  } else {
    selectedPaper.value = paper
  }
}

/**
 * Clear paper selection
 */
const clearPaperSelection = () => {
  selectedPaper.value = null
}

/**
 * Show paper study sites dialog
 */
const showPaperStudySites = (paper: any) => {
  dialogPaper.value = {
    ...paper,
    study_sites: [],
  }
  studySitesDialog.value = true

  paperStudySitesLoading.value = true
  studySitesStore.fetchItemStudySites(paper.id)
    .then((sites) => {
      if (!dialogPaper.value || dialogPaper.value.id !== paper.id) return
      dialogPaper.value = {
        ...dialogPaper.value,
        study_sites: sites,
      }
    })
    .finally(() => {
      if (dialogPaper.value?.id === paper.id) {
        paperStudySitesLoading.value = false
      }
    })
}

/**
 * Filter by dialog paper and close dialog
 */
const filterByDialogPaper = () => {
  selectedPaper.value = dialogPaper.value
  studySitesDialog.value = false
}

/**
 * Pan to study site from dialog
 */
const panToStudySite = (site: any) => {
  studySitesDialog.value = false

  if (!mapComponent.value) {
    logger.warn('Map component not initialized yet')
    return
  }

  const lat = site.location?.latitude ?? site.latitude
  const lon = site.location?.longitude ?? site.longitude

  if (lat == null || lon == null) {
    logger.warn(`Site "${site.name}" has no valid location data`)
    return
  }

  mapComponent.value.panTo(lat, lon, 12, 1500)
}

/**
 * Format paper subtitle (author and year)
 */
const formatPaperSubtitle = (paper: any): string => {
  const parts: string[] = []

  if (paper.publicationTitle) {
    parts.push(paper.publicationTitle)
  }

  if (paper.date) {
    const year = new Date(paper.date).getFullYear()
    if (!isNaN(year)) {
      parts.push(year.toString())
    }
  }

  return parts.length > 0 ? parts.join(' • ') : 'No publication info'
}

/**
 * Get confidence color
 */
const getConfidenceColor = (score: number): string => {
  if (score >= 0.8) return 'success'
  if (score >= 0.5) return 'warning'
  return 'error'
}

/**
 * Format extraction method
 */
const formatExtractionMethod = (method: string): string => {
  if (!method) return 'Unknown'

  // Convert snake_case to Title Case
  return method
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const formatSummaryRow = (row: Record<string, any>): string => {
  const groupParts: string[] = []
  const metricParts: string[] = []

  Object.entries(row).forEach(([key, value]) => {
    if (key === 'site_count' || key === 'avg_confidence') {
      metricParts.push(`${key}: ${value}`)
      return
    }
    groupParts.push(`${key}: ${value}`)
  })

  if (metricParts.length === 0) {
    return groupParts.join(' | ')
  }
  if (groupParts.length === 0) {
    return metricParts.join(' | ')
  }
  return `${groupParts.join(' | ')} -> ${metricParts.join(' | ')}`
}

/**
 * Handle region selected from map click
 */
const handleRegionSelected = (regionId: string) => {
  const region = regionsStore.regions.find((r) => r.id === regionId)
  if (region) {
    regionsStore.selectRegion(region)
    rightTab.value = 'regions'
  }
}

/**
 * Handle region click from list
 */
const handleRegionClick = (region: Region) => {
  if (regionsStore.selectedRegion?.id === region.id) {
    regionsStore.selectRegion(null)
  } else {
    regionsStore.selectRegion(region)
    mapComponent.value?.fitToRegion(region.id)
  }
}

/**
 * Filter papers by ID (from region stats panel)
 */
const filterPaperById = (paperId: string) => {
  const paper = mapPapers.value.find((p) => p.id === paperId)
  if (paper) {
    selectedPaper.value = paper
    rightTab.value = 'sites'
  }
}

/**
 * Confirm region deletion
 */
const confirmDeleteRegion = (region: Region) => {
  regionToDelete.value = region
  deleteRegionDialog.value = true
}

/**
 * Execute region deletion
 */
const executeDeleteRegion = async () => {
  if (regionToDelete.value) {
    await regionsStore.deleteRegion(regionToDelete.value.id)
  }
  deleteRegionDialog.value = false
  regionToDelete.value = null
}

/**
 * Handle shapefile uploaded
 */
const handleShapefileUploaded = () => {
  uploadDialogOpen.value = false
}

// Lifecycle
onMounted(async () => {
  await gisStore.fetchCapabilities()
  await fetchMapPapers()
  if (authStore.isAuthenticated) {
    await regionsStore.fetchRegions()
  }

  // Read query params for initial item selection
  if (route.query.itemTitle) {
    searchQuery.value = route.query.itemTitle as string
  }
})

watch(gisOperation, (operation) => {
  useClippedResult.value = false
  useWithinDistanceResult.value = false
  if (!gisOperationOptions.value.some((option) => option.value === operation)) {
    gisOperation.value = gisOperationOptions.value[0]?.value ?? 'buffer'
    return
  }
  if (operation !== 'buffer') {
    bufferDissolve.value = false
  }
})

watch(
  () => gisOperationOptions.value,
  (options) => {
    if (!options.some((option) => option.value === gisOperation.value)) {
      gisOperation.value = options[0]?.value ?? 'buffer'
    }
  },
)

watch(
  () => route.query.itemTitle,
  (newVal) => {
    if (newVal) {
      searchQuery.value = newVal as string
    }
  },
)

// Watch for paper selection changes and fit map to filtered sites
watch(
  () => selectedPaper.value,
  () => {
    // Wait for the map to update markers, then fit to them
    setTimeout(() => {
      if (mapComponent.value && filteredSites.value.length > 0) {
        mapComponent.value.fitToMarkers()
      }
    }, 300)
  },
)

watch(studySitesDialog, (open) => {
  if (!open) {
    paperStudySitesLoading.value = false
  }
})

watch(
  () => selectedRegionIdForClip.value,
  () => {
    useClippedResult.value = false
    useWithinDistanceResult.value = false
  },
)

watch(withinDistanceReturnLayer, () => {
  useWithinDistanceResult.value = false
})

watch(papersScope, async () => {
  selectedPaper.value = null
  await fetchMapPapers()
})
</script>

<style scoped>
.fill-height {
  height: 100%;
  min-height: 0;
}

.cursor-pointer {
  cursor: pointer;
}

.sidebar-left {
  border-right: 1px solid rgba(0, 0, 0, 0.12);
}

.sidebar-right {
  border-left: 1px solid rgba(0, 0, 0, 0.12);
}

.overflow-y-auto {
  overflow-y: auto;
}

/* Custom scrollbar for the list */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Context text styling */
.context-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  padding: 8px;
  background-color: rgba(0, 0, 0, 0.03);
  border-radius: 4px;
  font-style: italic;
}

/* Gap utility for flex items */
.gap-1 {
  gap: 4px;
}

.gap-2 {
  gap: 8px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: bold;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.6);
  letter-spacing: 0.5px;
}
</style>
