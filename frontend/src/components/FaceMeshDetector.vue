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
      <div v-if="encouragementText" class="encouragement-badge">
        {{ encouragementText }}
      </div>
      <div v-if="isDetecting && actions.length > 1" class="step-badge">
        动作 {{ currentActionIndex + 1 }} / {{ actions.length }}
      </div>
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
        :percentage="overallProgress"
        :status="progressStatus"
        :stroke-width="16"
      />
      <div class="countdown-text">
        剩余时间: {{ remainingSeconds.toFixed(1) }}s / 每个动作 {{ timeoutSeconds }}s
      </div>
    </div>

    <div class="metrics">
      <el-tag v-if="earValue !== null" type="info">EAR: {{ earValue.toFixed(3) }}</el-tag>
      <el-tag v-if="marValue !== null" type="info">MAR: {{ marValue.toFixed(3) }}</el-tag>
      <el-tag v-if="marBaseline !== null" type="success">Baseline: {{ marBaseline.toFixed(3) }}</el-tag>
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
  actions: {
    type: Array,
    required: true,
    validator: (v) => Array.isArray(v) && v.length > 0 && v.every(a => ['blink', 'open_mouth'].includes(a)),
  },
  descriptions: {
    type: Array,
    required: true,
    validator: (v) => Array.isArray(v) && v.length > 0 && v.every(d => typeof d === 'string'),
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
const currentActionIndex = ref(0)
const errorMessage = ref('')
const encouragementText = ref('')
const earValue = ref(null)
const marValue = ref(null)
const earHistory = ref([])
const marHistory = ref([])
const startTime = ref(0)
const elapsedMs = ref(0)
let animationFrameId = null
let timerIntervalId = null
let lastTimestamp = 0
let marBaseline = null
let baselineSamples = []
let prepDeadline = 0
let actionCompleted = false

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// MediaPipe CDN URLs
const MEDIAPIPE_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh'

// Landmark indices
const LEFT_EYE = [362, 385, 387, 263, 373, 380]
const RIGHT_EYE = [33, 160, 158, 133, 153, 144]
const MOUTH = [61, 291, 13, 14, 78, 308, 402, 178]

// Thresholds
const EAR_CLOSED_THRESHOLD = 0.18
const EAR_OPEN_THRESHOLD = 0.22
const MAR_OPEN_DELTA = 0.15
const MAR_CLOSED_DELTA = 0.05

// TTS
function stopSpeech() {
  if ('speechSynthesis' in window) {
    speechSynthesis.cancel()
  }
}

function speak(text, onEnd) {
  const hasTTS = 'speechSynthesis' in window
  if (hasTTS) {
    stopSpeech()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.35
    u.pitch = 1.0
    if (onEnd) u.onend = onEnd
    speechSynthesis.speak(u)
  }
}

function speakComplete(text) {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) {
      resolve()
      return
    }
    stopSpeech()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.35
    u.pitch = 1.0
    u.onend = resolve
    u.onerror = resolve
    speechSynthesis.speak(u)
  })
}

// State labels
const stateLabel = computed(() => {
  if (state.value === 'IDLE') return '等待检测'
  if (state.value === 'PREPARING') return '准备中，请保持自然表情~'
  if (state.value === 'DETECTED') {
    const desc = props.descriptions[currentActionIndex.value] || ''
    return `第${currentActionIndex.value + 1}步：${desc}`
  }
  if (state.value === 'IN_PROGRESS') return '动作进行中，继续保持~'
  if (state.value === 'TRANSITIONING') return '动作完成，准备下一步~'
  if (state.value === 'VERIFIED') return '🎉 验证成功！'
  if (state.value === 'FAILED') return '验证失败'
  return state.value
})

// Overall progress (0-100)
const overallProgress = computed(() => {
  if (!isDetecting.value) return 0
  if (state.value === 'VERIFIED') return 100
  if (state.value === 'FAILED') return 100

  const stepWeight = 100 / props.actions.length
  if (state.value === 'TRANSITIONING') {
    return Math.round((currentActionIndex.value + 1) * stepWeight)
  }

  const actionProgress = Math.min(100, (elapsedMs.value / (props.timeoutSeconds * 1000)) * 100)
  return Math.round(currentActionIndex.value * stepWeight + (actionProgress / 100) * stepWeight)
})

const remainingSeconds = computed(() => {
  if (!isDetecting.value || state.value === 'VERIFIED' || state.value === 'FAILED') {
    return props.timeoutSeconds
  }
  const remaining = props.timeoutSeconds - elapsedMs.value / 1000
  return Math.max(0, remaining)
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

// Calculate EAR
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

// Calculate MAR
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

// Draw face landmarks
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

  if (actionCompleted) return

  if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
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

  // PREPARING: collect baseline
  if (state.value === 'PREPARING') {
    if (avgEAR > 0 && mar > 0) {
      baselineSamples.push({ mar, ear: avgEAR })
    }

    const prepDone = Date.now() >= prepDeadline || baselineSamples.length >= 10

    if (prepDone) {
      if (baselineSamples.length >= 3) {
        // 异常值剔除：去掉最高 10% 的样本，取剩余最小值作为闭合 baseline
        const marValues = baselineSamples.map(s => s.mar).sort((a, b) => a - b)
        const discardCount = Math.max(0, Math.floor(marValues.length * 0.1))
        const filtered = marValues.slice(0, marValues.length - discardCount)
        marBaseline = Math.min(...filtered)
      } else if (baselineSamples.length > 0) {
        marBaseline = baselineSamples[0].mar
      } else {
        marBaseline = 0.3
      }
      startCurrentAction()
    }
    return
  }

  // DETECTED / IN_PROGRESS
  const action = props.actions[currentActionIndex.value]

  if (state.value === 'DETECTED') {
    if (action === 'blink' && avgEAR < EAR_CLOSED_THRESHOLD) {
      state.value = 'IN_PROGRESS'
    } else if (action === 'open_mouth' && mar > marBaseline * 1.5) {
      state.value = 'IN_PROGRESS'
    }
    emit('progress', { state: state.value, ear: avgEAR, mar, actionIndex: currentActionIndex.value })
    return
  }

  if (state.value === 'IN_PROGRESS') {
    let completed = false
    if (action === 'blink' && avgEAR > EAR_OPEN_THRESHOLD) {
      completed = true
    } else if (action === 'open_mouth' && mar < marBaseline * 1.20) {
      completed = true
    }

    if (completed) {
      actionCompleted = true
      stopTimer()
      state.value = 'TRANSITIONING'
      emit('progress', { state: 'TRANSITIONING', actionIndex: currentActionIndex.value })
      if (currentActionIndex.value < props.actions.length - 1) {
        // More actions remaining
        const nextDesc = props.descriptions[currentActionIndex.value + 1]
        encouragementText.value = `✨ 很好！下一步：${nextDesc}`
        setTimeout(() => {
          currentActionIndex.value++
          encouragementText.value = ''
          startCurrentAction()
        }, 200)
      } else {
        // All done
        encouragementText.value = '🎉 太棒了，验证成功！'
        completeVerification()
      }
      return
    }

    emit('progress', { state: state.value, ear: avgEAR, mar, actionIndex: currentActionIndex.value })
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

  encouragementText.value = '验证通过，正在提交'
  await speakComplete('验证通过，正在提交')
  const imageBlob = await captureFrameBlob()
  const durationMs = Date.now() - startTime.value

  emit('verified', {
    success: true,
    imageBlob,
    meta: {
      actions: [...props.actions],
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
  encouragementText.value = ''
  speakComplete('验证失败，请重试')

  emit('verified', {
    success: false,
    imageBlob: null,
    meta: {
      actions: [...props.actions],
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
      // Ignore processing errors
    }
  }

  animationFrameId = requestAnimationFrame(processVideo)
}

// Start detection
async function startDetection() {
  if (isDetecting.value) return

  errorMessage.value = ''
  encouragementText.value = ''
  state.value = 'IDLE'
  currentActionIndex.value = 0
  earValue.value = null
  marValue.value = null
  earHistory.value = []
  marHistory.value = []
  elapsedMs.value = 0
  marBaseline = null
  baselineSamples = []
  prepDeadline = Date.now() + 2500
  actionCompleted = false

  try {
    await initFaceMesh()

    mediaStream.value = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    })

    if (videoRef.value) {
      videoRef.value.srcObject = mediaStream.value
      await new Promise((resolve, reject) => {
        videoRef.value.onloadedmetadata = resolve
        videoRef.value.onerror = reject
        setTimeout(resolve, 3000)
      })
    }

    isDetecting.value = true
    state.value = 'PREPARING'

    const prepText = props.actions.length > 1
      ? `请准备，完成${props.actions.length}个动作`
      : '请准备，完成一个动作'
    speak(prepText)

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

function startCurrentAction() {
  actionCompleted = false
  const desc = props.descriptions[currentActionIndex.value]
  state.value = 'DETECTED'

  stopTimer()
  elapsedMs.value = 0
  startTime.value = Date.now()
  startTimer()

  const stepText = props.actions.length > 1
    ? `第${currentActionIndex.value + 1}步，${desc}`
    : desc
  speak(stepText)
}

// Stop detection
function stopDetection() {
  isDetecting.value = false
  stopTimer()
  stopSpeech()
  stopCamera()
  encouragementText.value = ''

  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }

  if (state.value === 'IN_PROGRESS' || state.value === 'DETECTED' || state.value === 'PREPARING') {
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
watch(() => props.actions, () => {
  if (isDetecting.value) {
    stopDetection()
  }
}, { deep: true })

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

.encouragement-badge {
  position: absolute;
  left: 50%;
  bottom: 48px;
  transform: translateX(-50%);
  padding: 8px 16px;
  border-radius: 999px;
  background: rgba(103, 194, 58, 0.9);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.step-badge {
  position: absolute;
  right: 12px;
  top: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.85);
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
