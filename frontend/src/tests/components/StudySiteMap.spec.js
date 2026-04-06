import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { useStudySitesStore } from '@/stores/studySites';
import StudySiteMap from '@/components/maps/StudySiteMap.vue';
let pinia;
let vectorSourceCreateCount = 0;
const vectorSourceInstance = {
    clear: vi.fn(),
    addFeature: vi.fn(),
    addFeatures: vi.fn(),
    getExtent: vi.fn(() => [0, 0, 10, 10]),
};
const regionSourceInstance = {
    clear: vi.fn(),
    addFeatures: vi.fn(),
    getFeatures: vi.fn(() => []),
};
const analysisSourceInstance = {
    clear: vi.fn(),
    addFeatures: vi.fn(),
};
const clusterSourceInstance = {
    setSource: vi.fn(),
};
const mapViewInstance = {
    fit: vi.fn(),
    setCenter: vi.fn(),
    setZoom: vi.fn(),
    animate: vi.fn(),
    calculateExtent: vi.fn(() => [0, 0, 10, 10]),
};
const mapInstance = {
    on: vi.fn(),
    hasFeatureAtPixel: vi.fn(() => false),
    getTargetElement: vi.fn(() => ({ style: {} })),
    forEachFeatureAtPixel: vi.fn(() => undefined),
    getView: vi.fn(() => mapViewInstance),
    getSize: vi.fn(() => [1000, 600]),
    updateSize: vi.fn(),
    getInteractions: vi.fn(() => ({
        forEach: (_callback) => { },
    })),
    removeInteraction: vi.fn(),
    addInteraction: vi.fn(),
    setTarget: vi.fn(),
};
vi.mock('ol', () => ({
    Map: vi.fn(function MockMap() {
        return mapInstance;
    }),
    View: vi.fn(function MockView() {
        return mapViewInstance;
    }),
    Feature: vi.fn(function MockFeature(data) {
        return {
            get: (key) => data[key],
            set: vi.fn((key, value) => {
                data[key] = value;
            }),
            getGeometry: () => data.geometry || { getCoordinates: () => [0, 0], getExtent: () => [0, 0, 10, 10] },
        };
    }),
}));
vi.mock('ol/layer', () => ({
    Tile: vi.fn(function MockTileLayer() {
        return {};
    }),
    Vector: vi.fn(function MockVectorLayer() {
        return {};
    }),
}));
vi.mock('ol/source', () => ({
    OSM: vi.fn(function MockOSM() {
        return {};
    }),
    Vector: vi.fn(function MockVectorSource() {
        vectorSourceCreateCount += 1;
        if (vectorSourceCreateCount === 1) {
            return vectorSourceInstance;
        }
        if (vectorSourceCreateCount === 2) {
            return regionSourceInstance;
        }
        return analysisSourceInstance;
    }),
    Cluster: vi.fn(function MockCluster() {
        return clusterSourceInstance;
    }),
}));
vi.mock('ol/interaction', () => ({
    DragBox: class DragBox {
        on = vi.fn();
        getGeometry() {
            return {
                getExtent: () => [0, 0, 10, 10],
            };
        }
    },
    DragZoom: class DragZoom {
    },
    DragPan: class DragPan {
        setActive = vi.fn();
    },
}));
vi.mock('ol/events/condition', () => ({
    shiftKeyOnly: vi.fn(() => false),
}));
vi.mock('ol/format/GeoJSON', () => ({
    default: class GeoJSON {
        readFeatures = vi.fn(() => [
            {
                set: vi.fn(),
                getGeometry: vi.fn(() => ({
                    getExtent: () => [0, 0, 10, 10],
                })),
            },
        ]);
    },
}));
vi.mock('ol/geom', () => ({
    Point: vi.fn(function MockPoint(coords) {
        return {
            coords,
            getCoordinates: () => coords,
            getExtent: () => [coords[0], coords[1], coords[0], coords[1]],
        };
    }),
}));
vi.mock('ol/proj', () => ({
    fromLonLat: vi.fn((coords) => coords),
    toLonLat: vi.fn((coords) => coords),
    transformExtent: vi.fn((extent) => extent),
}));
vi.mock('ol/style', () => ({
    Style: vi.fn(function MockStyle() {
        return {};
    }),
    Circle: vi.fn(function MockCircle() {
        return {};
    }),
    Fill: vi.fn(function MockFill() {
        return {};
    }),
    Stroke: vi.fn(function MockStroke() {
        return {};
    }),
    Text: vi.fn(function MockText() {
        return {};
    }),
}));
vi.mock('ol/extent', () => ({
    boundingExtent: vi.fn(() => [0, 0, 10, 10]),
}));
describe('StudySiteMap', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        pinia = createPinia();
        setActivePinia(pinia);
        vi.clearAllMocks();
        vectorSourceCreateCount = 0;
        Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
            configurable: true,
            get: () => 1000,
        });
        Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
            configurable: true,
            get: () => 600,
        });
        vi.stubGlobal('requestAnimationFrame', (callback) => {
            return setTimeout(() => callback(0), 0);
        });
    });
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.useRealTimers();
    });
    const flushMapSetup = async () => {
        await Promise.resolve();
        vi.runAllTimers();
        await Promise.resolve();
    };
    const mountComponent = (sites) => {
        return mount(StudySiteMap, {
            props: sites ? { sites } : {},
            global: {
                plugins: [pinia],
                stubs: {
                    StudySiteEditDialog: { template: '<div />' },
                    StudySiteCreateDialog: { template: '<div />' },
                    VOverlay: { template: '<div><slot /></div>' },
                    VProgressCircular: { template: '<div />' },
                    VCard: { template: '<div><slot /></div>' },
                    VCardText: { template: '<div><slot /></div>' },
                    VBtn: { template: '<button><slot /></button>' },
                },
            },
        });
    };
    it('adds one feature per valid map point from store', async () => {
        const studySitesStore = useStudySitesStore();
        studySitesStore.mapPoints = [
            {
                id: 'site-1',
                name: 'A',
                item_id: 'item-1',
                item_title: 'Paper A',
                latitude: 45.5,
                longitude: -122.3,
                is_manual: true,
                confidence_score: 0.9,
            },
            {
                id: 'site-2',
                name: 'B',
                item_id: 'item-2',
                item_title: 'Paper B',
                latitude: 40.7,
                longitude: -74,
                is_manual: false,
                confidence_score: 0.8,
            },
        ];
        mountComponent();
        await flushMapSetup();
        expect(vectorSourceInstance.clear).toHaveBeenCalled();
        expect(vectorSourceInstance.addFeatures).toHaveBeenCalledTimes(1);
    });
    it('skips points with null coordinates', async () => {
        const studySitesStore = useStudySitesStore();
        studySitesStore.mapPoints = [
            {
                id: 'site-1',
                name: 'A',
                item_id: 'item-1',
                item_title: 'Paper A',
                latitude: null,
                longitude: -122.3,
                is_manual: true,
                confidence_score: 0.9,
            },
            {
                id: 'site-2',
                name: 'B',
                item_id: 'item-2',
                item_title: 'Paper B',
                latitude: 40.7,
                longitude: null,
                is_manual: false,
                confidence_score: 0.8,
            },
        ];
        mountComponent();
        await flushMapSetup();
        expect(vectorSourceInstance.addFeatures).not.toHaveBeenCalled();
    });
    it('keeps valid zero coordinates (0, 0)', async () => {
        const studySitesStore = useStudySitesStore();
        studySitesStore.mapPoints = [
            {
                id: 'site-0',
                name: 'Null Island',
                item_id: 'item-0',
                item_title: 'Paper 0',
                latitude: 0,
                longitude: 0,
                is_manual: false,
                confidence_score: 0.5,
            },
        ];
        mountComponent();
        await flushMapSetup();
        expect(vectorSourceInstance.addFeatures).toHaveBeenCalledTimes(1);
    });
    it('uses props.sites instead of store mapPoints when provided', async () => {
        const studySitesStore = useStudySitesStore();
        studySitesStore.mapPoints = [];
        mountComponent([
            {
                id: 'site-prop',
                name: 'From props',
                item_id: 'item-prop',
                item_title: 'Paper prop',
                latitude: 10,
                longitude: 20,
                is_manual: true,
                confidence_score: 1,
            },
        ]);
        await flushMapSetup();
        expect(vectorSourceInstance.addFeatures).toHaveBeenCalledTimes(1);
    });
    it('renders analysis buffer features when provided', async () => {
        mount(StudySiteMap, {
            props: {
                bufferFeatures: [
                    {
                        source_id: 'site-1',
                        geometry: {
                            type: 'Polygon',
                            coordinates: [],
                        },
                    },
                ],
            },
            global: {
                plugins: [pinia],
                stubs: {
                    StudySiteEditDialog: { template: '<div />' },
                    StudySiteCreateDialog: { template: '<div />' },
                    VOverlay: { template: '<div><slot /></div>' },
                    VProgressCircular: { template: '<div />' },
                    VCard: { template: '<div><slot /></div>' },
                    VCardText: { template: '<div><slot /></div>' },
                    VBtn: { template: '<button><slot /></button>' },
                },
            },
        });
        await flushMapSetup();
        expect(analysisSourceInstance.clear).toHaveBeenCalled();
        expect(analysisSourceInstance.addFeatures).toHaveBeenCalled();
    });
});
