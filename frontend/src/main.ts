import { createApp } from 'vue'
import App from './App.vue'
import { registerPlugins } from '@/plugins'
import 'unfonts.css'
import 'ol/ol.css'

// Create Vue app
const app = createApp(App)

registerPlugins(app)

// Mount the app
app.mount('#app')
