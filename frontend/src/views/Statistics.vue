<template>
  <div class="page-wrap">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header>情绪分布统计</template>
          <EmotionChart title="情绪分布" :items="emotionChartData" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>活动参与次数统计</template>
          <EmotionChart title="活动参与次数" :items="activityChartData" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>活动参与趋势折线图</template>
      <EmotionChart title="活动参与趋势" :items="activityChartData" chart-type="line" />
    </el-card>

    <el-card>
      <template #header>情绪时间线</template>
      <el-table :data="timeline" v-loading="loading" border>
        <el-table-column prop="student_name" label="姓名" />
        <el-table-column prop="scene" label="场景" />
        <el-table-column prop="emotion" label="情绪" />
        <el-table-column prop="timestamp" label="时间" min-width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import request from '../api/request'
import EmotionChart from '../components/EmotionChart.vue'

const loading = ref(false)
const emotionStatistics = ref([])
const activityStatistics = ref([])
const timeline = ref([])

const emotionChartData = computed(() =>
  emotionStatistics.value.map((item) => ({ label: item.emotion, value: item.count })),
)

const activityChartData = computed(() =>
  activityStatistics.value.map((item) => ({ label: item.name, value: item.activity_count })),
)

const fetchData = async () => {
  loading.value = true
  try {
    const [emotionRes, activityRes, timelineRes] = await Promise.all([
      request.get('/emotion/statistics'),
      request.get('/group/statistics'),
      request.get('/emotion/timeline'),
    ])
    emotionStatistics.value = emotionRes.data.data
    activityStatistics.value = activityRes.data.data
    timeline.value = timelineRes.data.data
  } finally {
    loading.value = false
  }
}

fetchData()
</script>

<style scoped>
.page-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
