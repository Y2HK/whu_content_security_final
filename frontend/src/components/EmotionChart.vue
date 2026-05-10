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
  orientation: {
    type: String,
    default: 'vertical',
    validator: (value) => ['vertical', 'horizontal'].includes(value),
  },
  enableZoom: {
    type: Boolean,
    default: false,
  },
  maxVisibleItems: {
    type: Number,
    default: 18,
  },
  height: {
    type: Number,
    default: 360,
  },
})

const chartRef = ref(null)
let chartInstance = null

const truncateLabel = (value) => {
  const text = String(value ?? '')
  return text
}

const buildTooltip = (params) => {
  const point = Array.isArray(params) ? params[0] : params
  const item = props.items[point?.dataIndex] || {}
  const label = item.fullLabel || item.label || point?.name || ''
  const value = item.value ?? point?.value ?? 0
  const studentNo = item.student_no ? `<br/>学号：${item.student_no}` : ''
  const details =
    item.live_attendance_count !== undefined || item.group_photo_count !== undefined
      ? `<br/>活体签到：${item.live_attendance_count || 0}<br/>合照识别：${item.group_photo_count || 0}`
      : ''
  return `${label}${studentNo}<br/>${props.title}：${value}${details}`
}

const buildZoom = (total, isHorizontal) => {
  const shouldZoom = props.enableZoom || total > props.maxVisibleItems
  if (!shouldZoom || total <= props.maxVisibleItems) return []

  const end = Math.max(8, Math.min(100, (props.maxVisibleItems / total) * 100))
  const axisIndex = isHorizontal ? { yAxisIndex: 0 } : { xAxisIndex: 0 }
  return [
    {
      type: 'slider',
      ...axisIndex,
      start: 0,
      end,
      zoomLock: true,
      brushSelect: false,
      showDetail: false,
      handleSize: 0,
      showDataShadow: false,
      moveHandleSize: 8,
      height: isHorizontal ? undefined : 12,
      width: isHorizontal ? 12 : undefined,
      right: isHorizontal ? 6 : undefined,
      borderColor: 'transparent',
      top: isHorizontal ? 62 : undefined,
      bottom: isHorizontal ? 28 : 10,
      fillerColor: 'rgba(61, 66, 76, 0.34)',
      backgroundColor: 'rgba(61, 66, 76, 0.14)',
      moveHandleStyle: {
        color: 'rgba(61, 66, 76, 0.78)',
        borderColor: 'transparent',
        opacity: 0.9,
      },
      emphasis: {
        moveHandleStyle: {
          color: 'rgba(36, 40, 48, 0.95)',
        },
      },
      filterMode: 'none',
    },
    {
      type: 'inside',
      ...axisIndex,
      start: 0,
      end,
      zoomLock: true,
      zoomOnMouseWheel: false,
      moveOnMouseWheel: true,
      moveOnMouseMove: true,
      filterMode: 'none',
    },
  ]
}

const renderChart = async () => {
  await nextTick()
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  chartRef.value.style.height = `${props.height}px`
  chartInstance.resize()

  const labels = props.items.map((item) => item.label)
  const values = props.items.map((item) => item.value)
  const total = props.items.length
  const isHorizontal = props.orientation === 'horizontal' && props.chartType === 'bar'
  const hasManyItems = total > props.maxVisibleItems

  const categoryAxis = {
    type: 'category',
    data: labels,
    axisLabel: {
      interval: 0,
      formatter: truncateLabel,
      rotate: !isHorizontal && hasManyItems ? 35 : 0,
      hideOverlap: false,
    },
    axisTick: {
      alignWithLabel: true,
      interval: 0,
    },
  }
  const valueAxis = { type: 'value' }

  chartInstance.setOption({
    title: { text: props.title },
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter: buildTooltip,
    },
    grid: {
      top: 54,
      right: isHorizontal && hasManyItems ? 36 : 20,
      bottom: !isHorizontal && hasManyItems ? 70 : 36,
      left: isHorizontal ? 96 : 48,
      containLabel: true,
    },
    dataZoom: buildZoom(total, isHorizontal),
    xAxis: isHorizontal ? valueAxis : categoryAxis,
    yAxis: isHorizontal ? { ...categoryAxis, inverse: true } : valueAxis,
    series: [
      {
        type: props.chartType,
        smooth: props.chartType === 'line',
        showSymbol: props.chartType === 'line' ? total <= 40 : undefined,
        data: values,
        itemStyle: { color: '#409EFF' },
        lineStyle: { color: '#409EFF', width: 3 },
        areaStyle: props.chartType === 'line' ? { opacity: 0.12 } : undefined,
        barMaxWidth: isHorizontal ? 18 : 34,
      },
    ],
    graphic:
      total === 0
        ? {
            type: 'text',
            left: 'center',
            top: 'middle',
            style: { text: '暂无数据', fill: '#909399', fontSize: 14 },
          }
        : [],
  }, true)
}

onMounted(renderChart)
watch(() => props.items, renderChart, { deep: true })
watch(() => props.chartType, renderChart)
watch(() => props.orientation, renderChart)
watch(() => props.enableZoom, renderChart)
watch(() => props.maxVisibleItems, renderChart)
watch(() => props.height, renderChart)

const resizeChart = () => {
  chartInstance?.resize()
}

onMounted(() => {
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
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
