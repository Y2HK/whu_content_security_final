<template>
  <div class="face-mesh-detector">
    <div class="video-wrap">
      <video
        ref="videoRef"
        autoplay
        playsinline
        muted
        class="video"
      />
      <canvas
        ref="overlayCanvasRef"
        class="overlay-canvas"
      />
      <div class="status-badge">{{ stateLabel }}</div>
    </div>

    <div class="controls">
      <el-button
        type="primary"
        :disabled="isDetecting"
        @click="startDetection"
      >
        开始检测
      </el-button>
      <el-button
        :disabled="!isDetecting"
        @click="stopDetection"
      >
        停止检测
      </el-button>
    </div>

    <div class="progress-area">
      <el-progress
        :percentage="progressPercent"
        :status="progressStatus"
        :stroke-width="16"
      />
      <div class="countdown-text">
        剩余时间: {{ remainingSeconds.toFixed(1) }}s / {{ timeoutSeconds }}s
      </div>
    </div>

    <div class="metrics">
      <el-tag v-if="earValue !== null" type="info">EAR: {{ earValue.toFixed(3) }}</el-tag>
      <el-tag v-if="marValue !== null" type="info">MAR: {{ marValue.toFixed(3) }}</el-tag>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      class="error-alert"
    />

    <canvas
      ref="captureCanvasRef"
      class="hidden-canvas"
    />
  </div>
</template>

<script setup>
import {
  computed,
  onBeforeUnmount,
  ref,
  watch,
} from 'vue'

const props = defineProps({
  actionType: {
    type: String,
    required: true,
    validator: (v) => ['blink', 'open_mouth'].includes(v),
  },
  timeoutSeconds: {
    type: Number,
    default: 10,
  },
})

const emit = defineEmits(['verified', 'progress', 'error'])

// Refs
const videoRef = ref(null)
const overlayCanvasRef = ref(null)
const captureCanvasRef = ref(null)
const mediaStream = ref(null)
// MediaPipe FaceMesh instance (must NOT be reactive ref to avoid Vue Proxy breaking WASM)
let faceMeshInstance = null
const isDetecting = ref(false)
const state = ref('IDLE')
const errorMessage = ref('')
const earValue = ref(null)
const marValue = ref(null)
const earHistory = ref([])
const marHistory = ref([])
const startTime = ref(0)
const elapsedMs = ref(0)
let animationFrameId = null
let timerIntervalId = null
let lastTimestamp = 0
let marBaseline = null  // 闭嘴时的基准 MAR 值

// MediaPipe CDN URLs
const MEDIAPIPE_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh'

// Landmark indices
const LEFT_EYE = [362, 385, 387, 263, 373, 380]
const RIGHT_EYE = [33, 160, 158, 133, 153, 144]
const MOUTH = [61, 291, 13, 14, 78, 308, 402, 178]

// Thresholds
// 眨眼：基于绝对 EAR 值（闭眼时 EAR 显著下降，用户数据有效）
const EAR_CLOSED_THRESHOLD = 0.18
const EAR_OPEN_THRESHOLD = 0.22
// 张嘴：基于相对 MAR 变化（不同人脸闭嘴基准不同，不能用绝对阈值）
const MAR_OPEN_DELTA = 0.15   // 张嘴时 MAR 比 baseline 增加至少 0.15
const MAR_CLOSED_DELTA = 0.05 // 闭嘴时 MAR 回到 baseline + 0.05 以内

// State labels
const stateLabel = computed(() => {
  const map = {
    IDLE: '等待检测',
    DETECTED: '检测到人脸',
    IN_PROGRESS: '动作进行中',
    VERIFIED: '验证通过',
    FAILED: '验证失败',
  }
  return map[state.value] || state.value
})

// Progress
const remainingSeconds = computed(() => {
  if (!isDetecting.value || state.value === 'VERIFIED' || state.value === 'FAILED') {
    return props.timeoutSeconds
  }
  const remaining = props.timeoutSeconds - elapsedMs.value / 1000
  return Math.max(0, remaining)
})

const progressPercent = computed(() => {
  if (!isDetecting.value || state.value === 'VERIFIED' || state.value === 'FAILED') {
    return 0
  }
  const percent = (elapsedMs.value / (props.timeoutSeconds * 1000)) * 100
  return Math.min(100, Math.round(percent))
})

const progressStatus = computed(() => {
  if (state.value === 'VERIFIED') return 'success'
  if (state.value === 'FAILED') return 'exception'
  return ''
})

// Utility: load script dynamically
function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.crossOrigin = 'anonymous'
    script.onload = resolve
    script.onerror = () => reject(new Error(`Failed to load script: ${src}`))
    document.head.appendChild(script)
  })
}

// Utility: Euclidean distance
function distance(p1, p2) {
  return Math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)
}

// Calculate EAR (Eye Aspect Ratio)
function calculateEAR(landmarks, indices) {
  const p1 = landmarks[indices[0]]
  const p2 = landmarks[indices[1]]
  const p3 = landmarks[indices[2]]
  const p4 = landmarks[indices[3]]
  const p5 = landmarks[indices[4]]
  const p6 = landmarks[indices[5]]

  const vertical1 = distance(p2, p6)
  const vertical2 = distance(p3, p5)
  const horizontal = distance(p1, p4)

  if (horizontal === 0) return 0
  return (vertical1 + vertical2) / (2 * horizontal)
}

// Calculate MAR (Mouth Aspect Ratio)
function calculateMAR(landmarks, indices) {
  const p49 = landmarks[indices[0]]
  const p55 = landmarks[indices[1]]
  const p51 = landmarks[indices[2]]
  const p59 = landmarks[indices[3]]
  const p53 = landmarks[indices[4]]
  const p57 = landmarks[indices[5]]
  const p61 = landmarks[indices[6]]
  const p67 = landmarks[indices[7]]

  const vertical1 = distance(p51, p59)
  const vertical2 = distance(p53, p57)
  const horizontal = distance(p49, p55)

  if (horizontal === 0) return 0
  return (vertical1 + vertical2) / (2 * horizontal)
}

// Initialize MediaPipe Face Mesh
async function initFaceMesh() {
  if (faceMeshInstance) return

  try {
    // Load MediaPipe dependencies from CDN
    await loadScript(`${MEDIAPIPE_CDN}/face_mesh.js`)
    await loadScript(`${MEDIAPIPE_CDN}/face_mesh_solution_simd_wasm_bin.js`)

    const { FaceMesh } = window
    if (!FaceMesh) {
      throw new Error('MediaPipe FaceMesh not available after loading scripts')
    }

    const fm = new FaceMesh({
      locateFile: (file) => `${MEDIAPIPE_CDN}/${file}`,
    })

    fm.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    })

    fm.onResults(onFaceMeshResults)
    faceMeshInstance = fm
  } catch (err) {
    emit('error', { message: err.message || 'MediaPipe 加载失败' })
    throw err
  }
}

// Draw face landmarks on overlay canvas
function drawLandmarks(results) {
  const canvas = overlayCanvasRef.value
  const video = videoRef.value
  if (!canvas || !video) return

  const ctx = canvas.getContext('2d')
  canvas.width = video.videoWidth || 640
  canvas.height = video.videoHeight || 480
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) return

  const landmarks = results.multiFaceLandmarks[0]

  // Draw face bounding box approximation
  let minX = 1, minY = 1, maxX = 0, maxY = 0
  for (const lm of landmarks) {
    minX = Math.min(minX, lm.x)
    minY = Math.min(minY, lm.y)
    maxX = Math.max(maxX, lm.x)
    maxY = Math.max(maxY, lm.y)
  }

  const padding = 0.05
  ctx.strokeStyle = '#409eff'
  ctx.lineWidth = 2
  ctx.strokeRect(
    (minX - padding) * canvas.width,
    (minY - padding) * canvas.height,
    (maxX - minX + padding * 2) * canvas.width,
    (maxY - minY + padding * 2) * canvas.height,
  )

  // Draw key landmarks
  const keyIndices = [...LEFT_EYE, ...RIGHT_EYE, ...MOUTH]
  ctx.fillStyle = '#67c23a'
  for (const idx of keyIndices) {
    const lm = landmarks[idx]
    ctx.beginPath()
    ctx.arc(lm.x * canvas.width, lm.y * canvas.height, 2, 0, 2 * Math.PI)
    ctx.fill()
  }
}

// Process Face Mesh results
function onFaceMeshResults(results) {
  if (!isDetecting.value) return

  drawLandmarks(results)

  if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
    if (state.value === 'IDLE') {
      // No face detected yet
    }
    emit('progress', { state: state.value })
    return
  }

  const landmarks = results.multiFaceLandmarks[0]

  const leftEAR = calculateEAR(landmarks, LEFT_EYE)
  const rightEAR = calculateEAR(landmarks, RIGHT_EYE)
  const avgEAR = (leftEAR + rightEAR) / 2
  const mar = calculateMAR(landmarks, MOUTH)

  earValue.value = avgEAR
  marValue.value = mar
  earHistory.value.push(avgEAR)
  marHistory.value.push(mar)

  // DEBUG: print real-time values
  console.log(
    `[FaceMesh] action=${props.actionType} state=${state.value} EAR=${avgEAR.toFixed(3)} MAR=${mar.toFixed(3)} | ` +
    `EAR_th=${EAR_CLOSED_THRESHOLD}/${EAR_OPEN_THRESHOLD} MAR_baseline=${marBaseline?.toFixed(3) ?? 'null'} MAR_delta=${MAR_OPEN_DELTA}/${MAR_CLOSED_DELTA}`
  )

  // State machine
  if (state.value === 'IDLE') {
    state.value = 'DETECTED'
    emit('progress', { state: state.value, ear: avgEAR, mar })
    return
  }

  if (state.value === 'DETECTED') {
    if (props.actionType === 'blink' && avgEAR < EAR_CLOSED_THRESHOLD) {
      state.value = 'IN_PROGRESS'
    } else if (props.actionType === 'open_mouth') {
      // 收集前3帧建立闭嘴 baseline，然后检测张嘴
      if (marBaseline === null) {
        if (marHistory.value.length >= 3) {
          marBaseline = (marHistory.value[0] + marHistory.value[1] + marHistory.value[2]) / 3
        }
      } else if (mar > marBaseline + MAR_OPEN_DELTA) {
        state.value = 'IN_PROGRESS'
      }
    }
    emit('progress', { state: state.value, ear: avgEAR, mar })
    return
  }

  if (state.value === 'IN_PROGRESS') {
    let completed = false
    if (props.actionType === 'blink' && avgEAR > EAR_OPEN_THRESHOLD) {
      completed = true
    } else if (props.actionType === 'open_mouth' && mar < marBaseline + MAR_CLOSED_DELTA) {
      completed = true
    }

    if (completed) {
      completeVerification()
      return
    }

    emit('progress', { state: state.value, ear: avgEAR, mar })
  }
}

// Capture frame as Blob
async function captureFrameBlob() {
  const video = videoRef.value
  const canvas = captureCanvasRef.value
  if (!video || !canvas) return null

  canvas.width = video.videoWidth || 640
  canvas.height = video.videoHeight || 480
  const ctx = canvas.getContext('2d')
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.92)
  })
}

// Complete verification
async function completeVerification() {
  state.value = 'VERIFIED'
  isDetecting.value = false
  stopTimer()

  const imageBlob = await captureFrameBlob()
  const durationMs = Date.now() - startTime.value

  emit('verified', {
    success: true,
    imageBlob,
    meta: {
      action_type: props.actionType,
      duration_ms: durationMs,
      ear_history: [...earHistory.value],
      mar_history: [...marHistory.value],
    },
  })
}

// Fail verification
function failVerification(reason) {
  state.value = 'FAILED'
  isDetecting.value = false
  stopTimer()

  emit('verified', {
    success: false,
    imageBlob: null,
    meta: {
      action_type: props.actionType,
      duration_ms: Date.now() - startTime.value,
      ear_history: [...earHistory.value],
      mar_history: [...marHistory.value],
      reason,
    },
  })
}

// Timer
function startTimer() {
  elapsedMs.value = 0
  startTime.value = Date.now()
  timerIntervalId = setInterval(() => {
    elapsedMs.value = Date.now() - startTime.value
    if (elapsedMs.value >= props.timeoutSeconds * 1000) {
      failVerification('timeout')
    }
  }, 100)
}

function stopTimer() {
  if (timerIntervalId) {
    clearInterval(timerIntervalId)
    timerIntervalId = null
  }
}

// Video processing loop
async function processVideo() {
  if (!isDetecting.value) return

  const video = videoRef.value
  if (video && video.readyState >= 2 && faceMeshInstance) {
    try {
      await faceMeshInstance.send({ image: video })
    } catch (err) {
      // Ignore processing errors, continue loop
    }
  }

  animationFrameId = requestAnimationFrame(processVideo)
}

// Start detection
async function startDetection() {
  if (isDetecting.value) return

  errorMessage.value = ''
  state.value = 'IDLE'
  earValue.value = null
  marValue.value = null
  earHistory.value = []
  marHistory.value = []
  elapsedMs.value = 0
  marBaseline = null

  try {
    // Initialize MediaPipe
    await initFaceMesh()

    // Get camera stream
    mediaStream.value = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    })

    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream.value
      await new Promise((resolve, reject) => {
        videoRef.value.onloadedmetadata = resolve
        videoRef.value.onerror = reject
        // Timeout fallback
        setTimeout(resolve, 3000)
      })
    }

    isDetecting.value = true
    startTimer()
    processVideo()
  } catch (err) {
    const msg = err.name === 'NotAllowedError'
      ? '摄像头权限被拒绝，请在浏览器设置中允许访问摄像头'
      : err.message || '启动检测失败'
    errorMessage.value = msg
    emit('error', { message: msg })
    stopCamera()
  }
}

// Stop detection
function stopDetection() {
  isDetecting.value = false
  stopTimer()
  stopCamera()

  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }

  if (state.value === 'IN_PROGRESS' || state.value === 'DETECTED') {
    failVerification('user_cancelled')
  } else {
    state.value = 'IDLE'
  }
}

// Stop camera stream
function stopCamera() {
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((track) => track.stop())
    mediaStream.value = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
}

// Cleanup on unmount
onBeforeUnmount(() => {
  stopDetection()
  if (faceMeshInstance) {
    try {
      faceMeshInstance.close()
    } catch (e) {
      // ignore WASM cleanup errors
    }
    faceMeshInstance = null
  }
})

// Watch for prop changes
watch(() => props.actionType, () => {
  if (isDetecting.value) {
    stopDetection()
  }
})

// Expose methods
defineExpose({
  startDetection,
  stopDetection,
})
</script>

<style scoped>
.face-mesh-detector {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.video-wrap {
  position: relative;
  width: 100%;
  max-width: 480px;
  background: #111827;
  border-radius: 12px;
  overflow: hidden;
}

.video {
  width: 100%;
  display: block;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
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

.controls {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.progress-area {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.countdown-text {
  font-size: 12px;
  color: #606266;
}

.metrics {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.error-alert {
  margin-top: 4px;
}

.hidden-canvas {
  display: none;
}
</style>
