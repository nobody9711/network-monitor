<template>
  <div class="monitoring-dashboard">
    <div class="controls">
      <select v-model="selectedRange" @change="updateChart">
        <option v-for="opt in rangeOptions" :value="opt.value" :key="opt.value">
          {{ opt.label }}
        </option>
      </select>
      <div v-if="selectedRange === 'custom'" class="custom-range">
        <input type="datetime-local" v-model="customStart" @change="setCustomRange">
        <input type="datetime-local" v-model="customEnd" @change="setCustomRange">
      </div>
      <button @click="triggerTest" class="test-button">Run Manual Test</button>
    </div>
    
    <div class="chart-container">
      <line-chart :data="processedData" :options="chartOptions"/>
    </div>
  </div>
</template>

<script>
import { Line } from 'vue-chartjs'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const RANGE_OPTIONS = [
  { label: '1 Day', value: '1d' },
  { label: '2 Days', value: '2d' },
  { label: '7 Days', value: '7d' },
  { label: '1 Month', value: '1m' },
  { label: '3 Months', value: '3m' },
  { label: '6 Months', value: '6m' },
  { label: '1 Year', value: '1y' },
  { label: 'Custom', value: 'custom' }
]

export default {
  components: { LineChart: Line },
  data() {
    return {
      selectedRange: '1d',
      customStart: null,
      customEnd: null,
      rawData: [],
      rangeOptions: RANGE_OPTIONS,
      chartOptions: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            type: 'time',
            time: {
              tooltipFormat: 'YYYY-MM-DD HH:mm',
              displayFormats: {
                hour: 'MMM D HH:mm',
                day: 'MMM D',
                month: 'MMM YYYY'
              }
            }
          }
        }
      }
    }
  },
  computed: {
    processedData() {
      return {
        labels: this.rawData.map(d => d.timestamp),
        datasets: [
          {
            label: 'Download (Mbps)',
            data: this.rawData.map(d => d.download),
            borderColor: '#4dc9f6',
            tension: 0.1
          },
          {
            label: 'Upload (Mbps)',
            data: this.rawData.map(d => d.upload),
            borderColor: '#f67019',
            tension: 0.1
          }
        ]
      }
    }
  },
  async mounted() {
    await this.updateChart()
  },
  methods: {
    async fetchData(params = {}) {
      const query = new URLSearchParams(params).toString()
      const res = await fetch(`/speedtest/results?${query}`)
      this.rawData = await res.json()
    },
    
    calcDateRange() {
      const now = new Date()
      switch(this.selectedRange) {
        case '1d': return { start: new Date(now - 86400000) }
        case '2d': return { start: new Date(now - 172800000) }
        case '7d': return { start: new Date(now - 604800000) }
        case '1m': return { start: new Date(now.setMonth(now.getMonth() - 1)) }
        case '3m': return { start: new Date(now.setMonth(now.getMonth() - 3)) }
        case '6m': return { start: new Date(now.setMonth(now.getMonth() - 6)) }
        case '1y': return { start: new Date(now.setFullYear(now.getFullYear() - 1)) }
        default: return {}
      }
    },
    
    async updateChart() {
      if(this.selectedRange !== 'custom') {
        const range = this.calcDateRange()
        await this.fetchData({
          start: range.start.toISOString(),
          end: new Date().toISOString()
        })
      }
    },
    
    async setCustomRange() {
      if(this.customStart && this.customEnd) {
        await this.fetchData({
          start: new Date(this.customStart).toISOString(),
          end: new Date(this.customEnd).toISOString()
        })
      }
    },
    
    async triggerTest() {
      await fetch('/speedtest/trigger', { method: 'POST' })
      await this.updateChart()
    }
  }
}
</script>

<style scoped>
.monitoring-dashboard {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.custom-range {
  display: flex;
  gap: 1rem;
}

.chart-container {
  height: 500px;
  position: relative;
}

.test-button {
  background: #4CAF50;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}
</style>
