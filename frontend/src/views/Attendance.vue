<template>
  <div class="page-wrap">
    <el-card>
      <template #header>
        <div class="header-row">
          <span>基础考勤</span>
          <div class="actions">
            <el-button @click="triggerFileSelect">选择图片考勤</el-button>
            <el-button v-if="isTeacher" type="success" @click="exportRecords">导出 Excel</el-button>
          </div>
        </div>
      </template>

      <div v-if="isTeacher" class="session-panel">
        <template v-if="activeSession">
          <el-alert
            type="success"
            :closable="false"
            :title="`已发布签到：${activeSession.title}`"
          />
          <el-button type="danger" plain :loading="sessionLoading" @click="closeAttendanceSession">
            结束签到
          </el-button>
        </template>
        <template v-else>
          <el-input v-model="sessionForm.title" class="session-title-input" placeholder="请输入签到标题" />
          <el-button type="primary" :loading="sessionLoading" @click="publishAttendanceSession">
            发布签到
          </el-button>
        </template>
      </div>

      <el-alert
        v-if="!isTeacher && activeSession"
        class="mt16"
        type="success"
        :closable="false"
        title="有新的考勤，请使用活体识别完成签到。"
      />

      <!-- 活体检测挑战卡片 -->
      <el-card v-if="canUseLiveness && challenge && !showFaceMesh && faceMeshState !== 'verified'" class="challenge-card" shadow="hover">
        <template #header>
          <div class="challenge-header">
            <el-icon><Lock /></el-icon>
            <span>活体检测</span>
          </div>
        </template>
        <div class="challenge-body">
          <div class="challenge-actions">
            <el-button type="primary" :loading="isVerifying" @click="startFaceMeshVerify">
              开始验证
            </el-button>
            <el-button @click="skipFaceMeshVerify">跳过动作验证</el-button>
          </div>
          <el-alert
            v-if="actionError"
            :title="actionError"
            type="error"
            :closable="false"
            class="mt12"
          />
        </div>
      </el-card>

      <!-- FaceMeshDetector 动作验证 -->
      <el-row v-if="showFaceMesh && challenge" :gutter="16" class="face-mesh-row">
        <el-col :span="16">
          <FaceMeshDetector
            ref="faceMeshRef"
            :actions="challenge.actions"
            :descriptions="challenge.descriptions"
            :timeout-seconds="challenge.timeout_seconds"
            @verified="onFaceMeshVerified"
            @progress="onFaceMeshProgress"
            @error="onFaceMeshError"
          />
        </el-col>
        <el-col :span="8">
          <el-alert
            class="mt16"
            :title="cameraStatusMessage"
            type="info"
            :closable="false"
          />
          <el-alert
            class="mt16"
            title="正在进行活体动作验证，请按照提示完成动作。验证通过后将自动提交考勤。"
            type="warning"
            :closable="false"
          />
          <el-button class="mt16" @click="cancelFaceMeshVerify">取消验证</el-button>
        </el-col>
      </el-row>

      <!-- 原有 CameraCapture（跳过验证或验证完成后显示） -->
      <el-row v-if="!showFaceMesh" :gutter="16">
        <el-col :span="16">
          <CameraCapture @captured="submitCapturedFile" @status="handleCameraStatus" />
        </el-col>
        <el-col :span="8">
          <el-alert
            class="mt16"
            :title="cameraStatusMessage"
            type="info"
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
        <el-descriptions-item v-if="latestResult.live_result" label="活体方法">
          {{ latestResult.live_result.method }}
        </el-descriptions-item>
        <el-descriptions-item v-if="latestResult.live_result" label="活体置信度">
          {{ latestResult.live_result.confidence }}
        </el-descriptions-item>
        <el-descriptions-item v-if="latestResult.live_result" label="是否活体">
          <el-tag :type="latestResult.live_result.is_live ? 'success' : 'danger'">
            {{ latestResult.live_result.is_live ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card>
      <template #header>考勤记录</template>
      <el-form v-if="isTeacher" inline>
        <el-form-item label="学号">
          <el-input v-model="filters.student_no" placeholder="按学号筛选" clearable />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="filters.name" placeholder="按姓名筛选" clearable />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            class="date-range-picker"
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="选择日期范围"
            end-placeholder=""
            unlink-panels
            clearable
          />
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
        <el-table-column label="是否活体" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_live ? 'success' : 'info'">
              {{ row.is_live ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="emotion" label="情绪" />
        <el-table-column prop="confidence" label="置信度" />
        <el-table-column prop="check_time" label="考勤时间" min-width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'

import request from '../api/request'
import CameraCapture from '../components/CameraCapture.vue'
import FaceMeshDetector from '../components/FaceMeshDetector.vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const isTeacher = computed(() => authStore.user?.role === 'teacher')
const canUseLiveness = computed(() => !isTeacher.value && Boolean(activeSession.value))
const loading = ref(false)
const sessionLoading = ref(false)
const records = ref([])
const latestResult = ref(null)
const fileInputRef = ref(null)
const cameraStatus = ref('idle')
const filters = reactive({
  student_no: '',
  name: '',
})
const dateRange = ref([])
const activeSession = ref(null)
const livenessDismissed = ref(false)
let sessionPollTimer = null
const sessionForm = reactive({
  title: '课堂签到',
})

// 活体检测相关状态
const challenge = ref(null)
const showFaceMesh = ref(false)
const faceMeshState = ref('idle')
const actionError = ref(null)
const isVerifying = ref(false)
const faceMeshRef = ref(null)

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

const fetchActiveSession = async () => {
  let data
  try {
    const response = await request.get('/attendance/session/active')
    data = response.data
  } catch {
    return
  }

  const previousSessionId = activeSession.value?.session_id || null
  activeSession.value = data.data

  const currentSessionId = activeSession.value?.session_id || null
  if (previousSessionId !== currentSessionId) {
    livenessDismissed.value = false
    challenge.value = null
    showFaceMesh.value = false
    faceMeshState.value = 'idle'
  }

  if (!canUseLiveness.value) {
    challenge.value = null
    showFaceMesh.value = false
    return
  }

  if (!challenge.value && !livenessDismissed.value) {
    await fetchChallenge()
  }
}

const publishAttendanceSession = async () => {
  sessionLoading.value = true
  try {
    const { data } = await request.post('/attendance/session/publish', {
      title: sessionForm.title,
    })
    activeSession.value = data.data
    ElMessage.success('签到已发布')
  } finally {
    sessionLoading.value = false
  }
}

const closeAttendanceSession = async () => {
  sessionLoading.value = true
  try {
    await request.post('/attendance/session/close')
    activeSession.value = null
    challenge.value = null
    showFaceMesh.value = false
    livenessDismissed.value = false
    ElMessage.success('签到已结束')
  } finally {
    sessionLoading.value = false
  }
}

// 获取动作挑战
const fetchChallenge = async () => {
  try {
    const { data } = await request.get('/attendance/action-challenge')
    challenge.value = data.data
  } catch (error) {
    console.error('获取动作挑战失败:', error)
    // 获取失败时不阻断，允许用户跳过验证
  }
}

// 开始 FaceMesh 动作验证
const startFaceMeshVerify = () => {
  if (!challenge.value) return
  actionError.value = null
  faceMeshState.value = 'idle'
  showFaceMesh.value = true
  isVerifying.value = true
  // FaceMeshDetector 内部会自己启动检测
}

// 跳过动作验证
const skipFaceMeshVerify = () => {
  challenge.value = null
  actionError.value = null
  faceMeshState.value = 'skipped'
  showFaceMesh.value = false
  livenessDismissed.value = true
  ElMessage.info('已跳过动作验证，请使用摄像头拍照考勤')
}

// 取消验证
const cancelFaceMeshVerify = () => {
  showFaceMesh.value = false
  faceMeshState.value = 'idle'
  isVerifying.value = false
  actionError.value = null
  if (faceMeshRef.value) {
    faceMeshRef.value.stopDetection()
  }
}

// FaceMesh 验证通过
const onFaceMeshVerified = async (result) => {
  isVerifying.value = false
  if (result.success && result.imageBlob) {
    faceMeshState.value = 'verified'
    showFaceMesh.value = false
    const file = new File([result.imageBlob], `facemesh_capture_${Date.now()}.jpg`, { type: 'image/jpeg' })
    try {
      await submitAttendanceFile(file, {
        challenge_id: challenge.value?.challenge_id,
        meta: result.meta,
      })
      ElMessage.success('活体验证通过，考勤提交成功')
    } catch (error) {
      const message = error.response?.data?.detail || '考勤提交失败'
      actionError.value = message
      faceMeshState.value = 'failed'
      showFaceMesh.value = true
      isVerifying.value = false
      ElMessage.error(message)
    }
  } else {
    faceMeshState.value = 'failed'
    actionError.value = result.meta?.reason || '验证未通过，请重试'
    showFaceMesh.value = true
    isVerifying.value = false
  }
}

// FaceMesh 进度更新
const onFaceMeshProgress = (progress) => {
  faceMeshState.value = progress.state?.toLowerCase() || 'detecting'
}

// FaceMesh 错误
const onFaceMeshError = (error) => {
  isVerifying.value = false
  actionError.value = error.message || '检测过程出错'
  showFaceMesh.value = true
  faceMeshState.value = 'error'
}

const submitAttendanceFile = async (file, challengeData = null) => {
  const formData = new FormData()
  formData.append('file', file)
  if (challengeData) {
    formData.append('challenge_id', challengeData.challenge_id)
    formData.append('action_verified', 'true')
    formData.append('action_meta', JSON.stringify(challengeData.meta || {}))
  }
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

const buildAttendanceParams = () => {
  const params = {
    student_no: filters.student_no,
    name: filters.name,
  }
  if (dateRange.value?.[0]) {
    params.date_from = dateRange.value[0]
  }
  if (dateRange.value?.[1]) {
    params.date_to = dateRange.value[1]
  }
  return params
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/attendance/records', { params: buildAttendanceParams() })
    records.value = data.data
  } finally {
    loading.value = false
  }
}

const exportRecords = async () => {
  try {
    const response = await request.get('/attendance/export', {
      params: buildAttendanceParams(),
      responseType: 'blob',
    })
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

onMounted(() => {
  fetchRecords()
  fetchActiveSession()
  sessionPollTimer = window.setInterval(fetchActiveSession, 15000)
})

onBeforeUnmount(() => {
  if (sessionPollTimer) {
    window.clearInterval(sessionPollTimer)
  }
})
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

.session-panel {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.session-panel :deep(.el-alert) {
  flex: 1;
}

.session-title-input {
  max-width: 260px;
}

.result-box {
  margin-top: 16px;
}

.mt16 {
  margin-top: 16px;
}

.mt12 {
  margin-top: 12px;
}

.challenge-card {
  margin-bottom: 16px;
}

.challenge-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.challenge-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.challenge-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

.face-mesh-row {
  margin-bottom: 16px;
}

.date-range-picker {
  width: 260px;
}
</style>
