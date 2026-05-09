<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import * as echarts from 'echarts'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: '统计图',
  },
  items: {
    type: Array,
    default: () => [],
  },
  chartType: {
    type: String,
    default: 'bar',
    validator: (value) => ['bar', 'line'].includes(value),
  },
})

const chartRef = ref(null)
let chartInstance = null

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  chartInstance.setOption({
    title: { text: props.title },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: props.items.map((item) => item.label),
    },
    yAxis: { type: 'value' },
    series: [
      {
        type: props.chartType,
        smooth: props.chartType === 'line',
        data: props.items.map((item) => item.value),
        itemStyle: { color: '#409EFF' },
        lineStyle: { color: '#409EFF', width: 3 },
        areaStyle: props.chartType === 'line' ? { opacity: 0.12 } : undefined,
      },
    ],
  })
}

onMounted(renderChart)
watch(() => props.items, renderChart, { deep: true })
watch(() => props.chartType, renderChart)

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: 360px;
}
</style>
