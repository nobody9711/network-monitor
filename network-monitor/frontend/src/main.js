import { createApp } from 'vue'
import App from './App.vue'
import Chart from 'chart.js/auto'

const app = createApp(App)
app.config.globalProperties.$Chart = Chart
app.mount('#app')
