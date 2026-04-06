import { createPinia, setActivePinia } from 'pinia';
import { config } from '@vue/test-utils';
import { vi } from 'vitest';
/**
 * Setup function to be called before each test
 */
export function setupTest() {
    // Create a fresh Pinia instance for each test
    const pinia = createPinia();
    setActivePinia(pinia);
    // Mock window.open
    global.window.open = vi.fn();
    // Mock console methods to reduce noise
    global.console.error = vi.fn();
    global.console.warn = vi.fn();
    return { pinia };
}
/**
 * Clean up after tests
 */
export function teardownTest() {
    vi.clearAllMocks();
    vi.restoreAllMocks();
}
/**
 * Create mock API response
 */
export function createMockApiResponse(data, status = 200) {
    return {
        data,
        status,
        statusText: 'OK',
        headers: {},
        config: {}
    };
}
/**
 * Create mock error response
 */
export function createMockErrorResponse(message, status = 400) {
    const error = new Error(message);
    error.response = {
        data: { detail: message },
        status,
        statusText: 'Bad Request',
        headers: {},
        config: {}
    };
    return error;
}
/**
 * Wait for async operations to complete
 */
export async function flushPromises() {
    return new Promise((resolve) => setTimeout(resolve, 0));
}
/**
 * Mock localStorage
 */
export function setupLocalStorage() {
    const localStorageMock = (() => {
        let store = {};
        return {
            getItem: (key) => store[key] || null,
            setItem: (key, value) => {
                store[key] = value.toString();
            },
            removeItem: (key) => {
                delete store[key];
            },
            clear: () => {
                store = {};
            },
            get length() {
                return Object.keys(store).length;
            },
            key: (index) => {
                const keys = Object.keys(store);
                return keys[index] || null;
            }
        };
    })();
    Object.defineProperty(global, 'localStorage', {
        value: localStorageMock,
        writable: true
    });
    return localStorageMock;
}
/**
 * Configure Vue Test Utils globally
 */
export function configureVueTestUtils() {
    // Add global stubs for Vuetify components
    config.global.stubs = {
        VBtn: { template: '<button><slot /></button>' },
        VCard: { template: '<div><slot /></div>' },
        VDialog: { template: '<div v-if="modelValue"><slot /></div>', props: ['modelValue'] },
        VTextField: { template: '<input />', props: ['modelValue'] },
        VTextarea: { template: '<textarea />', props: ['modelValue'] },
        VSelect: { template: '<select />', props: ['modelValue', 'items'] },
        VAutocomplete: { template: '<input />', props: ['modelValue', 'items'] },
        VDataTable: { template: '<table><slot /></table>', props: ['headers', 'items'] },
        VList: { template: '<ul><slot /></ul>' },
        VListItem: { template: '<li><slot /></li>' },
        VIcon: { template: '<i />', props: ['icon'] },
        VChip: { template: '<span><slot /></span>' },
        VRow: { template: '<div><slot /></div>' },
        VCol: { template: '<div><slot /></div>' },
        VContainer: { template: '<div><slot /></div>' },
    };
}
