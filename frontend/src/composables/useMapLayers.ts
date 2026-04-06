import { shallowRef } from 'vue'
import { Vector as VectorLayer } from 'ol/layer'
import { Vector as VectorSource, Cluster } from 'ol/source'
import { Feature } from 'ol'
import { Point } from 'ol/geom'
import { fromLonLat } from 'ol/proj'
import { Style, Circle, Fill, Stroke, Text } from 'ol/style'
import GeoJSON from 'ol/format/GeoJSON'
import type { MapPoint } from '@/stores/studySites'
import type { Region } from '@/stores/regions'
import type { GISBufferedFeature } from '@/stores/gis'

export function useMapLayers() {
  // OL objects stored as `any` refs — their internal types are incompatible
  // with Vue's deep-reactive Ref wrapper. The original component did the same.
  const vectorSource = shallowRef<any>(null)
  const clusterSource = shallowRef<any>(null)
  const clusterLayer = shallowRef<any>(null)
  const regionSource = shallowRef<any>(null)
  const regionLayer = shallowRef<any>(null)
  const analysisSource = shallowRef<any>(null)
  const analysisLayer = shallowRef<any>(null)
  const searchPinSource = shallowRef<any>(null)
  const searchPinLayer = shallowRef<any>(null)
  const geojsonFormat = new GeoJSON()

  // Style cache to avoid creating new Style objects on every render
  const styleCache: Record<string, Style> = {}

  const clusterStyleFunction = (feature: Feature): Style => {
    const clusterFeatures = feature.get('features') as Feature[]
    const size = clusterFeatures.length

    if (size === 1) {
      const point = clusterFeatures[0].get('mapPoint') as MapPoint
      const color = point.is_manual ? '#4CAF50' : '#2196F3'
      const key = `single-${color}`
      if (!styleCache[key]) {
        styleCache[key] = new Style({
          image: new Circle({
            radius: 6,
            fill: new Fill({ color }),
            stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
          }),
        })
      }
      return styleCache[key]
    }

    const key = `cluster-${size}`
    if (!styleCache[key]) {
      const radius = Math.min(8 + Math.log2(size) * 4, 24)
      styleCache[key] = new Style({
        image: new Circle({
          radius,
          fill: new Fill({ color: 'rgba(33, 150, 243, 0.7)' }),
          stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
        }),
        text: new Text({
          text: size.toString(),
          fill: new Fill({ color: '#FFFFFF' }),
          font: 'bold 12px sans-serif',
        }),
      })
    }
    return styleCache[key]
  }

  const createLayers = () => {
    vectorSource.value = new VectorSource()

    clusterSource.value = new Cluster({
      distance: 40,
      minDistance: 20,
      source: vectorSource.value,
    })

    clusterLayer.value = new VectorLayer({
      source: clusterSource.value,
      style: clusterStyleFunction as any,
    })

    regionSource.value = new VectorSource()
    regionLayer.value = new VectorLayer({
      source: regionSource.value,
      style: new Style({
        fill: new Fill({ color: 'rgba(255, 152, 0, 0.1)' }),
        stroke: new Stroke({ color: '#FF9800', width: 2 }),
      }),
    })

    analysisSource.value = new VectorSource()
    analysisLayer.value = new VectorLayer({
      source: analysisSource.value,
      style: new Style({
        fill: new Fill({ color: 'rgba(233, 30, 99, 0.15)' }),
        stroke: new Stroke({ color: '#E91E63', width: 2 }),
      }),
    })

    searchPinSource.value = new VectorSource()
    searchPinLayer.value = new VectorLayer({
      source: searchPinSource.value,
      style: new Style({
        image: new Circle({
          radius: 8,
          fill: new Fill({ color: '#EF5350' }),
          stroke: new Stroke({ color: '#FFFFFF', width: 2 }),
        }),
      }),
    })
  }

  const updateMarkers = (mapPoints: MapPoint[]) => {
    if (!vectorSource.value) return

    vectorSource.value.clear()
    Object.keys(styleCache).forEach((key) => delete styleCache[key])

    const features: Feature[] = []
    mapPoints.forEach((point) => {
      if (point.latitude == null || point.longitude == null) return
      features.push(new Feature({
        geometry: new Point(fromLonLat([point.longitude, point.latitude])),
        mapPoint: point,
      }))
    })

    if (features.length > 0) {
      vectorSource.value.addFeatures(features)
    }
  }

  const updateRegions = (regions: Region[]) => {
    if (!regionSource.value) return
    regionSource.value.clear()

    regions.forEach((region) => {
      if (!region.geojson) return

      const featureObj = {
        type: 'Feature' as const,
        geometry: region.geojson,
        properties: { regionId: region.id, name: region.name },
      }

      const features = geojsonFormat.readFeatures(featureObj, {
        dataProjection: 'EPSG:4326',
        featureProjection: 'EPSG:3857',
      })

      features.forEach((f) => {
        f.set('regionId', region.id)
        f.set('regionName', region.name)
      })

      regionSource.value!.addFeatures(features)
    })
  }

  const updateAnalysisFeatures = (bufferFeatures: GISBufferedFeature[]) => {
    if (!analysisSource.value) return
    analysisSource.value.clear()

    bufferFeatures.forEach((bufferFeature) => {
      if (!bufferFeature.geometry) return

      const featureObj = {
        type: 'Feature' as const,
        geometry: bufferFeature.geometry,
        properties: { sourceId: bufferFeature.source_id },
      }

      const features = geojsonFormat.readFeatures(featureObj, {
        dataProjection: 'EPSG:4326',
        featureProjection: 'EPSG:3857',
      })

      analysisSource.value!.addFeatures(features)
    })
  }

  const updateSearchPin = (lon: number, lat: number) => {
    if (!searchPinSource.value) return
    searchPinSource.value.clear()
    searchPinSource.value.addFeature(new Feature({
      geometry: new Point(fromLonLat([lon, lat])),
    }))
  }

  const clearSearchPin = () => {
    searchPinSource.value?.clear()
  }

  const fitToRegionExtent = (regionId: string) => {
    if (!regionSource.value) return null
    const features = regionSource.value.getFeatures().filter(
      (f: any) => f.get('regionId') === regionId,
    )
    if (features.length === 0) return null

    const extent = features[0].getGeometry()!.getExtent()
    for (let i = 1; i < features.length; i++) {
      const e = features[i].getGeometry()!.getExtent()
      extent[0] = Math.min(extent[0], e[0])
      extent[1] = Math.min(extent[1], e[1])
      extent[2] = Math.max(extent[2], e[2])
      extent[3] = Math.max(extent[3], e[3])
    }
    return extent
  }

  return {
    vectorSource,
    clusterSource,
    clusterLayer,
    regionSource,
    regionLayer,
    analysisSource,
    analysisLayer,
    searchPinSource,
    searchPinLayer,
    createLayers,
    updateMarkers,
    updateRegions,
    updateAnalysisFeatures,
    updateSearchPin,
    clearSearchPin,
    fitToRegionExtent,
  }
}
