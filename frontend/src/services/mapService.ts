import api from '@/services/api'

export interface GeocodeResult {
  id: string
  label: string
  lat: number
  lon: number
}

interface GeocodeSearchApiResult {
  id: string
  label: string
  latitude: number
  longitude: number
}

interface GeocodeSearchApiResponse {
  data: GeocodeSearchApiResult[]
}

const DEFAULT_PROVIDER = 'nominatim'
const DEFAULT_LIMIT = 8

const getSearchLimit = (): number => {
  const raw = Number(import.meta.env.VITE_GEOCODER_LIMIT)
  if (!Number.isFinite(raw) || raw <= 0) {
    return DEFAULT_LIMIT
  }

  return Math.min(Math.round(raw), 20)
}

const getProvider = (): string => {
  return (import.meta.env.VITE_GEOCODER_PROVIDER || DEFAULT_PROVIDER).toLowerCase()
}

export const searchLocations = async (query: string, signal?: AbortSignal): Promise<GeocodeResult[]> => {
  const normalizedQuery = query.trim()
  if (normalizedQuery.length < 3) {
    return []
  }

  const response = await api.get<GeocodeSearchApiResponse>('/study-sites/geocode-search', {
    params: {
      q: normalizedQuery,
      limit: getSearchLimit(),
      provider: getProvider(),
      countrycodes: import.meta.env.VITE_GEOCODER_COUNTRYCODES || undefined,
      language: navigator?.language || undefined,
    },
    signal,
  })

  return (response.data.data || []).map((item) => ({
    id: item.id,
    label: item.label,
    lat: item.latitude,
    lon: item.longitude,
  }))
}
