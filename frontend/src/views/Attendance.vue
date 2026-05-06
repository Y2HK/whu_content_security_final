<template>
  <div class="page-wrap">
    <el-card>
      <template #header>
        <div class="header-row">
          <span>基础考勤</span>
          <div class="actions">
            <el-button @click="triggerFileSelect">选择图片考勤</el-button>
            <el-button type="success" @click="exportRecords">导出 Excel</el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :span="16">
          <CameraCapture @captured="submitCapturedFile" @status="handleCameraStatus" />
        </el-col>
        <el-col :span="8">
          <FaceMeshDetector />
          <el-alert
            class="mt16"
            :title="cameraStatusMessage"
            type="info"
            :closable="false"
          />
          <el-alert
            class="mt16"
            title="当前版本已接入浏览器摄像头拍照流程；自动抓拍、人脸框与活体判断仅完成交互占位。"
            type="warning"
            :closable="false"
          />
        </el-col>
      </el-row>

      <input ref="fileInputRef" type="file" accept="image/*" class="hidden-input" @change="handleFileChange" />

      <el-descriptions v-if="latestResult" title="最近一次考勤结果" :column="2" border class="result-box">
        <el-descriptions-item label="姓名">{{ latestResult.name }}</el-descriptions-item>
        <el-descriptions-item label="学号">{{ latestResult.student_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ latestResult.status }}</el-descriptions-item>
        <el-descriptions-item label="情绪">{{ latestResult.emotion }}</el-descriptions-item>
        <el-descriptions-item label="置信度">{{ latestResult.confidence }}</el-descriptions-item>
        <el-descriptions-item label="时间">{{ latestResult.check_time }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <template #header>考勤记录</template>
      <el-form inline>
        <el-form-item label="学号">
          <el-input v-model="filters.student_no" placeholder="按学号筛选" clearable />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="filters.name" placeholder="按姓名筛选" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchRecords">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="records" v-loading="loading" border>
        <el-table-column prop="student_no" label="学号" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="class_name" label="班级" />
        <el-table-column prop="status" label="状态" />
        <el-table-column prop="emotion" label="情绪" />
        <el-table-column prop="confidence" label="置信度" />
        <el-table-column prop="check_time" label="考勤时间" min-width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import CameraCapture from '../components/CameraCapture.vue'
import FaceMeshDetector from '../components/FaceMeshDetector.vue'

const loading = ref(false)
const records = ref([])
const latestResult = ref(null)
const fileInputRef = ref(null)
const cameraStatus = ref('idle')
const filters = reactive({
  student_no: '',
  name: '',
})

const cameraStatusMessage = computed(() => {
  const map = {
    idle: '等待开启摄像头',
    running: '摄像头已开启，可拍照考勤',
    captured: '拍照完成，正在上传或可再次拍照',
    auto_hint: '已触发自动抓拍交互提示',
    stopped: '摄像头已关闭',
    error: '摄像头打开失败，请检查浏览器权限',
  }
  return map[cameraStatus.value] || '等待操作'
})

const handleCameraStatus = (status) => {
  cameraStatus.value = status
}

const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

const submitAttendanceFile = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await request.post('/attendance/check', formData)
  latestResult.value = data.data
  await fetchRecords()
}

const submitCapturedFile = async (file) => {
  try {
    await submitAttendanceFile(file)
    ElMessage.success('摄像头考勤成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '摄像头考勤失败')
  }
}

const handleFileChange = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  try {
    await submitAttendanceFile(file)
    ElMessage.success('图片考勤成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '考勤失败')
  } finally {
    event.target.value = ''
  }
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/attendance/records', { params: filters })
    records.value = data.data
  } finally {
    loading.value = false
  }
}

const exportRecords = async () => {
  try {
    const response = await request.get('/attendance/export', { responseType: 'blob' })
    const blob = new Blob([response.data], { type: response.headers['content-type'] })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'attendance.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('导出失败')
  }
}

fetchRecords()
</script>

<style scoped>
.page-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-row,
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hidden-input {
  display: none;
}

.result-box {
  margin-top: 16px;
}

.mt16 {
  margin-top: 16px;
}
</style>
