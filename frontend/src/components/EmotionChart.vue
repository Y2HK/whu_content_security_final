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
        type: 'bar',
        data: props.items.map((item) => item.value),
        itemStyle: { color: '#409EFF' },
      },
    ],
  })
}

onMounted(renderChart)
watch(() => props.items, renderChart, { deep: true })

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
