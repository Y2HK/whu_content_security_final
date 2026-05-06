<template>
  <div class="camera-capture">
    <div class="video-wrap">
      <video ref="videoRef" autoplay playsinline muted class="video"></video>
      <canvas ref="canvasRef" class="hidden-canvas"></canvas>
      <div v-if="statusText" class="status-badge">{{ statusText }}</div>
    </div>
    <div class="camera-actions">
      <el-button @click="startCamera" :disabled="streaming">开启摄像头</el-button>
      <el-button @click="stopCamera" :disabled="!streaming">关闭摄像头</el-button>
      <el-button type="primary" @click="captureFrame" :disabled="!streaming">拍照上传</el-button>
      <el-button @click="emitAutoCaptureHint" :disabled="!streaming">模拟自动抓拍提示</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

const emit = defineEmits(['captured', 'status'])

const videoRef = ref(null)
const canvasRef = ref(null)
const mediaStream = ref(null)
const streaming = ref(false)
const status = ref('idle')

const statusText = computed(() => {
  const map = {
    idle: '等待开启摄像头',
    running: '摄像头已开启',
    captured: '已拍照，可上传',
    auto_hint: '已触发自动抓拍提示',
    stopped: '摄像头已关闭',
    error: '摄像头打开失败',
  }
  return map[status.value] || ''
})

const startCamera = async () => {
  try {
    mediaStream.value = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream.value
    }
    streaming.value = true
    status.value = 'running'
    emit('status', status.value)
  } catch (error) {
    status.value = 'error'
    emit('status', status.value)
    throw error
  }
}

const stopCamera = () => {
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((track) => track.stop())
    mediaStream.value = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  streaming.value = false
  status.value = 'stopped'
  emit('status', status.value)
}

const captureFrame = async () => {
  if (!videoRef.value || !canvasRef.value) return

  const width = videoRef.value.videoWidth || 640
  const height = videoRef.value.videoHeight || 480
  canvasRef.value.width = width
  canvasRef.value.height = height

  const context = canvasRef.value.getContext('2d')
  context.drawImage(videoRef.value, 0, 0, width, height)

  const blob = await new Promise((resolve) => {
    canvasRef.value.toBlob(resolve, 'image/jpeg', 0.92)
  })

  if (blob) {
    const file = new File([blob], `camera_capture_${Date.now()}.jpg`, { type: 'image/jpeg' })
    status.value = 'captured'
    emit('status', status.value)
    emit('captured', file)
  }
}

const emitAutoCaptureHint = () => {
  status.value = 'auto_hint'
  emit('status', status.value)
}

onBeforeUnmount(() => {
  stopCamera()
})
</script>

<style scoped>
.camera-capture {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-wrap {
  position: relative;
  width: 100%;
  max-width: 720px;
  background: #111827;
  border-radius: 12px;
  overflow: hidden;
}

.video {
  width: 100%;
  display: block;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.hidden-canvas {
  display: none;
}

.status-badge {
  position: absolute;
  left: 12px;
  top: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.75);
  color: #fff;
  font-size: 12px;
}

.camera-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
