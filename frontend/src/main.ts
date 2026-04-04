import { createApp } from 'vue'
import App from './App.vue'
import { registerPlugins } from '@/plugins'
import logger from '@/utils/logger'
import 'unfonts.css'
import 'ol/ol.css'

// Create Vue app
const app = createApp(App)

registerPlugins(app)

// Global error handler — catches uncaught errors in components
app.config.errorHandler = (err, instance, info) => {
  const component = instance?.$options?.name || 'unknown'
  logger.error(`Uncaught error in <${component}> (${info}):`, err)
}

// Mount the app
app.mount('#app')
