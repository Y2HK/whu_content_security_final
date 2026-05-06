<template>
  <div class="page-wrap">
    <el-card>
      <template #header>合照识别</template>
      <el-form :model="form" inline>
        <el-form-item label="活动名称">
          <el-input v-model="form.activity_name" placeholder="请输入活动名称" />
        </el-form-item>
        <el-form-item label="活动日期">
          <el-date-picker v-model="form.event_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
        </el-form-item>
        <el-form-item>
          <input ref="fileInputRef" type="file" accept="image/*" class="hidden-input" @change="handleUpload" />
          <el-button type="primary" @click="triggerFileSelect">上传合照并识别</el-button>
        </el-form-item>
      </el-form>

      <el-descriptions v-if="latestActivity" title="最近一次识别结果" :column="2" border>
        <el-descriptions-item label="活动名称">{{ latestActivity.activity_name }}</el-descriptions-item>
        <el-descriptions-item label="日期">{{ latestActivity.event_date }}</el-descriptions-item>
        <el-descriptions-item label="参与人数">{{ latestActivity.participant_count }}</el-descriptions-item>
        <el-descriptions-item label="活动ID">{{ latestActivity.activity_id }}</el-descriptions-item>
      </el-descriptions>

      <el-table v-if="latestActivity" :data="latestActivity.participants" border class="mt16">
        <el-table-column prop="student_no" label="学号" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="confidence" label="置信度" />
        <el-table-column prop="emotion" label="情绪" />
      </el-table>
    </el-card>

    <el-card>
      <template #header>活动列表</template>
      <el-table :data="activities" v-loading="loading" border>
        <el-table-column prop="activity_name" label="活动名称" />
        <el-table-column prop="event_date" label="日期" />
        <el-table-column prop="participant_count" label="参与人数" />
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button size="small" @click="fetchActivityDetail(scope.row.activity_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'

const loading = ref(false)
const activities = ref([])
const latestActivity = ref(null)
const fileInputRef = ref(null)
const form = reactive({
  activity_name: '班级活动',
  event_date: new Date().toISOString().slice(0, 10),
})

const triggerFileSelect = () => {
  if (!form.activity_name || !form.event_date) {
    ElMessage.warning('请先填写活动名称和日期')
    return
  }
  fileInputRef.value?.click()
}

const handleUpload = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('activity_name', form.activity_name)
  formData.append('event_date', form.event_date)
  formData.append('file', file)

  try {
    const { data } = await request.post('/group/upload', formData)
    latestActivity.value = data.data
    ElMessage.success('识别完成')
    await fetchActivities()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '识别失败')
  } finally {
    event.target.value = ''
  }
}

const fetchActivities = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/group/activities')
    activities.value = data.data
  } finally {
    loading.value = false
  }
}

const fetchActivityDetail = async (activityId) => {
  const { data } = await request.get(`/group/activities/${activityId}`)
  latestActivity.value = data.data
}

fetchActivities()
</script>

<style scoped>
.page-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hidden-input {
  display: none;
}

.mt16 {
  margin-top: 16px;
}
</style>
