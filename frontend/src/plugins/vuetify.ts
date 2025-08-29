/**
 * plugins/vuetify.ts
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

// Composables
import { createVuetify } from 'vuetify'

// import { de, en } from 'vuetify/locale'
const light = {
  dark: false,
  colors: {
    maintext: '#00495e',
    antitext: '#ffffff',
    weaktext: '#8bb3bf',
    primary: '#0a6c85',
    secondary: '#ffffff',
    surface: '#ffffff',
    background: '#e3e9eb',
    warning: '#FCCE25',
    error: '#E16462',
    'on-surface': '#00495e',
  },
  variables: {
    'high-emphasis-opacity': 1,
    'medium-emphasis-opacity': 1,
  },
}
const dark = {
  dark: true,
  colors: {
    maintext: '#e1e1e1',
    antitext: '#002c2d',
    weaktext: '#aaaaaa',
    primary: '#6ca6b9',
    secondary: '#ffffff',
    surface: '#053c49',
    background: '#000000',
    warning: '#FCCE25',
    error: '#E16462',
    'on-surface': '#e1e1e1',
  },
  variables: {
    'high-emphasis-opacity': 1,
    'medium-emphasis-opacity': 1,
    'navigation-drawer-background': '#053c49',
    'body-font-family': 'Lato',
  },
}

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
export default createVuetify({
  theme: {
    // defaultTheme: 'system',
    defaultTheme: 'light',
    themes: {
      light,
      dark,
    },
  },
  icons: {
    defaultSet: 'mdi',
  },
  defaults: {
    VCol: {
      style: 'margin: 0; padding: 6px',
    },
    VRow: {
      style: 'margin: 0; padding: 0',
    },
    VCard: {
      style: 'margin: 0; padding: 24px',
      class: 'text-maintext',
    },
    VCardTitle: {
      class: 'text-wrap',
      style: 'hyphens: auto; overflow-wrap: break-word; word-break: break-word',
    },
    VCardText: {
      class: 'text-wrap',
      style: 'hyphens: auto; overflow-wrap: break-word; word-break: break-word',
    },
    VListItem: {
      class: 'text-maintext',
    },
  },
})
