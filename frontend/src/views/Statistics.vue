<template>
  <div class="page-wrap">
    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>情绪分布统计</span>
              <el-select
                v-if="isTeacher"
                v-model="selectedEmotionStudentId"
                class="student-select"
                size="small"
                @change="fetchEmotionStatistics"
              >
                <el-option label="全班" value="" />
                <el-option
                  v-for="student in students"
                  :key="student.student_id"
                  :label="`${student.name}（${student.student_no}）`"
                  :value="student.student_id"
                />
              </el-select>
            </div>
          </template>
          <EmotionChart title="情绪分布" :items="emotionChartData" />
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="16">
        <el-card>
          <template #header>有效参与次数统计</template>
          <EmotionChart
            title="有效参与次数"
            :items="activityChartData"
            orientation="horizontal"
            :enable-zoom="true"
            :max-visible-items="20"
            :height="420"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="isTeacher">
      <template #header>有效参与次数折线图</template>
      <EmotionChart
        title="有效参与次数"
        :items="activityChartData"
        chart-type="line"
        :enable-zoom="true"
        :max-visible-items="14"
      />
    </el-card>

    <el-card>
      <template #header>情绪时间线</template>
      <el-table :data="timeline" v-loading="loading" border>
        <el-table-column prop="student_no" label="学号" />
        <el-table-column prop="student_name" label="姓名" />
        <el-table-column prop="scene" label="场景" />
        <el-table-column prop="emotion" label="情绪" />
        <el-table-column label="是否活体" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_live ? 'success' : 'info'">
              {{ row.is_live ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="时间" min-width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import request from '../api/request'
import EmotionChart from '../components/EmotionChart.vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const emotionStatistics = ref([])
const activityStatistics = ref([])
const timeline = ref([])
const students = ref([])
const selectedEmotionStudentId = ref('')
const isTeacher = computed(() => authStore.user?.role === 'teacher')

const emotionChartData = computed(() =>
  emotionStatistics.value.map((item) => ({ label: item.emotion, value: item.count })),
)

const activityChartData = computed(() =>
  activityStatistics.value.map((item) => ({
    label: item.name,
    fullLabel: item.name,
    value: item.activity_count,
    name: item.name || '',
    student_no: item.student_no || '',
    live_attendance_count: item.live_attendance_count || 0,
    group_photo_count: item.group_photo_count || 0,
  })),
)

const fetchEmotionStatistics = async () => {
  const params = {}
  if (selectedEmotionStudentId.value !== '') {
    params.student_id = selectedEmotionStudentId.value
  }
  const response = await request.get('/emotion/statistics', { params })
  emotionStatistics.value = response.data.data
}

const fetchData = async () => {
  loading.value = true
  try {
    const requests = [
      fetchEmotionStatistics(),
      request.get('/group/statistics'),
      request.get('/emotion/timeline'),
    ]
    if (isTeacher.value) {
      requests.push(request.get('/students'))
    }

    const [, activityRes, timelineRes, studentsRes] = await Promise.all(requests)
    activityStatistics.value = activityRes.data.data
    timeline.value = timelineRes.data.data
    if (studentsRes) {
      students.value = studentsRes.data.data
    }
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.student-select {
  width: 180px;
}

@media (max-width: 720px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .student-select {
    width: 100%;
  }
}
</style>
