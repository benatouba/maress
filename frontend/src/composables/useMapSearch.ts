import { ref } from 'vue'
import { searchLocations, type GeocodeResult } from '@/services/mapService'
import logger from '@/utils/logger'

export function useMapSearch() {
  const locationQuery = ref('')
  const searchResults = ref<GeocodeResult[]>([])
  const searching = ref(false)
  const searchError = ref('')
  const highlightedSearchResultIndex = ref(-1)
  const locationSearchDebounce = ref<ReturnType<typeof setTimeout> | null>(null)
  const locationSearchAbortController = ref<AbortController | null>(null)

  const clearLocationSearch = (clearQuery = false) => {
    if (locationSearchDebounce.value) {
      clearTimeout(locationSearchDebounce.value)
      locationSearchDebounce.value = null
    }

    if (locationSearchAbortController.value) {
      locationSearchAbortController.value.abort()
      locationSearchAbortController.value = null
    }

    searchResults.value = []
    searching.value = false
    highlightedSearchResultIndex.value = -1

    if (clearQuery) {
      locationQuery.value = ''
    }
  }

  const runLocationSearch = async (query: string) => {
    const normalizedQuery = query.trim()
    if (normalizedQuery.length < 3) {
      searchResults.value = []
      searchError.value = ''
      return
    }

    if (locationSearchAbortController.value) {
      locationSearchAbortController.value.abort()
    }

    locationSearchAbortController.value = new AbortController()
    searching.value = true
    searchError.value = ''

    try {
      const results = await searchLocations(normalizedQuery, locationSearchAbortController.value.signal)
      searchResults.value = results
      highlightedSearchResultIndex.value = results.length > 0 ? 0 : -1
      if (results.length === 0) {
        searchError.value = 'No locations found'
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') return
      logger.error('Location search failed', error)
      searchError.value = 'Location search unavailable'
      searchResults.value = []
      highlightedSearchResultIndex.value = -1
    } finally {
      searching.value = false
    }
  }

  const handleLocationSearchInput = () => {
    const query = locationQuery.value.trim()
    if (query.length < 3) {
      clearLocationSearch(false)
      return
    }

    if (locationSearchDebounce.value) {
      clearTimeout(locationSearchDebounce.value)
    }

    locationSearchDebounce.value = setTimeout(() => {
      runLocationSearch(query)
      locationSearchDebounce.value = null
    }, 350)
  }

  const handleLocationSearchEnter = async () => {
    if (searchResults.value.length > 0) {
      const selectedIndex = highlightedSearchResultIndex.value >= 0
        ? highlightedSearchResultIndex.value
        : 0
      return searchResults.value[selectedIndex]
    }

    await runLocationSearch(locationQuery.value)
    if (searchResults.value.length > 0) {
      return searchResults.value[0]
    }
    return null
  }

  const handleLocationSearchKeydown = async (event: KeyboardEvent): Promise<GeocodeResult | null> => {
    if (event.key === 'ArrowDown' && searchResults.value.length > 0) {
      event.preventDefault()
      highlightedSearchResultIndex.value =
        (highlightedSearchResultIndex.value + 1 + searchResults.value.length) % searchResults.value.length
      return null
    }

    if (event.key === 'ArrowUp' && searchResults.value.length > 0) {
      event.preventDefault()
      highlightedSearchResultIndex.value =
        (highlightedSearchResultIndex.value - 1 + searchResults.value.length) % searchResults.value.length
      return null
    }

    if (event.key === 'Escape') {
      clearLocationSearch(false)
      return null
    }

    if (event.key === 'Enter') {
      event.preventDefault()
      return await handleLocationSearchEnter()
    }

    return null
  }

  return {
    locationQuery,
    searchResults,
    searching,
    searchError,
    highlightedSearchResultIndex,
    clearLocationSearch,
    handleLocationSearchInput,
    handleLocationSearchKeydown,
    handleLocationSearchEnter,
  }
}
