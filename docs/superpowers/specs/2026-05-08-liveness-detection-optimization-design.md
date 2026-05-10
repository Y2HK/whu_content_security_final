# 活体检测前端流程优化设计

> 文档类型：子模块优化规格说明书
> 日期：2026-05-08
> 适用：基于已完成的活体检测基础实现，优化前端交互体验与安全性

---

## 1. 设计目标

解决当前活体检测前端流程的两个核心问题：

1. **启动延迟感**：张嘴动作需等待前3帧建立 MAR baseline，用户需刻意静止等待，体验不自然。
2. **单一指令安全性**：仅眨眼/张嘴两种独立动作，攻击者可用针对性视频/照片分别绕过。

优化后达成：
- **零等待启动**：500ms准备期自动采集baseline，用户无感知等待
- **双动作序列挑战**：连续完成两个不同动作（如眨眼→张嘴），大幅提升防攻击能力
- **语音引导**：浏览器原生TTS提示动作指令，降低用户认知负担

---

## 2. 与现有代码的集成边界

### 2.1 需要修改的文件

| 文件 | 当前状态 | 修改内容 |
|------|----------|----------|
| `frontend/src/components/FaceMeshDetector.vue` | 单动作检测（blink/open_mouth） | 支持动作序列、准备期baseline采集、语音引导 |
| `frontend/src/views/Attendance.vue` | 单动作挑战流程 | 适配双动作序列响应，显示进度指示 |
| `backend/app/routers/attendance.py` | action-challenge返回单动作 | 返回actions数组，支持1~2个动作随机组合 |

### 2.2 不需要修改的文件

- `backend/app/services/liveness_service.py`：纹理检测逻辑不变
- `backend/app/core/config.py`：配置项不变
- 数据库结构：无变更

---

## 3. 前端检测流程优化（A1：零等待Baseline + 语音引导）

### 3.1 准备期（PREPARING状态）

```
用户点击"开始验证"
  │
  ▼
[PREPARING: 0~500ms]
  ├─ 开启摄像头
  ├─ 自动进入PREPARING状态
  ├─ 每帧记录MAR/EAR值（不判定任何动作）
  ├─ 播放语音："请准备，依次完成以下动作"
  ├─ 500ms后或采集到10帧（取先到者）
  │   └─ 计算baseline = 中位数（抗噪，优于平均值）
  │
  ▼
[动作1开始]
```

**关键设计：**
- 准备期内用户处于自然状态，无需刻意静止
- 使用**中位数**而非平均值计算baseline，抵抗偶然噪声帧
- 固定500ms上限，低帧率设备也能在可预期时间内完成采集
- 采集在 `onFaceMeshResults` 回调中异步完成，不阻塞主线程

### 3.2 语音引导（TTS）

使用浏览器原生 `speechSynthesis` API，无需引入第三方库：

```javascript
function speak(text) {
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'zh-CN'
  u.rate = 1.0
  speechSynthesis.speak(u)
}
```

**播放时机：**

| 时机 | 语音内容 | 说明 |
|------|----------|------|
| 准备期开始 | "请准备，依次完成以下动作" | 只播放一次 |
| 动作1开始 | "请眨眼" / "请张嘴" | 根据当前动作 |
| 动作1通过 | "通过" | 简短确认 |
| 动作2开始 | "请张嘴" / "请眨眼" | 第二个动作 |
| 全部通过 | "验证成功" | 终态确认 |

### 3.3 扩展状态机

```
IDLE ──点击开始──> PREPARING(500ms采集baseline)
                      │
                      └──> DETECTED(动作1) ──> IN_PROGRESS(动作1)
                                                    │
                                                    ├── 超时 ──> FAILED
                                                    └── 完成 ──> VERIFIED_STEP1
                                                                    │
                                                                    └──> DETECTED(动作2) ──> IN_PROGRESS(动作2)
                                                                                                  │
                                                                                                  ├── 超时 ──> FAILED
                                                                                                  └── 完成 ──> VERIFIED
```

---

## 4. 双动作序列挑战（B1）

### 4.1 后端 challenge 生成

```python
# backend/app/routers/attendance.py
ACTIONS = ["blink", "open_mouth"]

@router.get("/action-challenge")
def action_challenge(user: User = Depends(get_current_user)):
    _cleanup_expired_challenges()
    challenge_id = str(uuid.uuid4())
    
    # 随机排列两个动作，形成序列挑战
    actions = random.sample(ACTIONS, k=len(ACTIONS))  # ["blink", "open_mouth"] 或 ["open_mouth", "blink"]
    
    descriptions = ["请眨眼" if a == "blink" else "请张嘴" for a in actions]
    
    _challenge_store[challenge_id] = {
        "actions": actions,
        "expires_at": datetime.utcnow() + timedelta(seconds=60),
        "used": False,
    }
    
    return success({
        "challenge_id": challenge_id,
        # 兼容旧前端（单动作）
        "action_type": actions[0],
        "description": descriptions[0],
        # 新前端（动作序列）
        "actions": actions,
        "descriptions": descriptions,
        "timeout_seconds": 10,  # 每个动作的超时时间
    })
```

### 4.2 响应格式变更（向后兼容）

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "challenge_id": "uuid-string",
    "action_type": "blink",
    "description": "请眨眼",
    "actions": ["blink", "open_mouth"],
    "descriptions": ["请眨眼", "请张嘴"],
    "timeout_seconds": 10
  }
}
```

**兼容性说明：**
- 旧前端使用 `action_type` / `description`（单字符串），行为与之前完全一致
- 新前端读取 `actions` / `descriptions` 数组，按顺序执行双动作挑战

### 4.3 安全增益

| 攻击类型 | 单动作防御 | 双动作序列防御 |
|----------|-----------|---------------|
| 静态照片 | 动作活体可防 | 动作活体可防 |
| 视频重放 | 可被针对性视频绕过 | 需同时包含眨眼+张嘴时序，难度大幅提高 |
| 3D面具 | 纹理活体可防 | 纹理活体可防 |

---

## 5. FaceMeshDetector.vue 修改详情

### 5.1 Props 变更

| 属性 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `actions` | `string[]` | 是 | - | 动作序列，如 `["blink", "open_mouth"]` |
| `prepMs` | `number` | 否 | 500 | 准备期时长（毫秒） |
| `timeoutSeconds` | `number` | 否 | 10 | 每个动作的超时时间 |

### 5.2 内部状态扩展

```javascript
// 新增状态
const currentActionIndex = ref(0)     // 当前执行到第几个动作
const marBaseline = ref(null)         // 张嘴动作的baseline（每次序列重新计算）
const earHistory = ref([])            // 眨眼动作的历史（用于可选的平滑）

// 组件顶层非响应式变量（避免Vue Proxy干扰MediaPipe WASM）
let baselineSamples = []              // 准备期采集的样本
let prepDeadline = 0                  // 准备期截止时间戳
```

### 5.3 核心流程伪代码

```javascript
// TTS 播放（带降级）
function speak(text, onEnd) {
  const hasTTS = 'speechSynthesis' in window
  if (hasTTS) {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = 1.0
    if (onEnd) u.onend = onEnd
    speechSynthesis.speak(u)
  }
  // 无论TTS是否可用，都通过事件通知UI显示文字提示
  emit('tts', { text, spoken: hasTTS })
}

async function startDetection() {
  state.value = 'PREPARING'
  currentActionIndex.value = 0
  marBaseline.value = null
  earHistory.value = []
  baselineSamples = []
  prepDeadline = Date.now() + props.prepMs
  
  speak('请准备，依次完成以下动作')
  // 准备期采集在 onFaceMeshResults 回调中异步完成，不阻塞主线程
}

function startCurrentAction() {
  const action = props.actions[currentActionIndex.value]
  state.value = 'DETECTED'
  
  // 重置计时器：每个动作独立计时
  stopTimer()
  elapsedMs.value = 0
  startTime.value = Date.now()
  startTimer()
  
  speak(props.descriptions[currentActionIndex.value])
}

function onFaceMeshResults(results) {
  if (!isDetecting.value) return
  
  // 计算当前帧特征值
  const landmarks = results.multiFaceLandmarks[0]
  const leftEAR = calculateEAR(landmarks, LEFT_EYE)
  const rightEAR = calculateEAR(landmarks, RIGHT_EYE)
  const avgEAR = (leftEAR + rightEAR) / 2
  const mar = calculateMAR(landmarks, MOUTH)
  
  // ===== PREPARING: 准备期采集baseline =====
  if (state.value === 'PREPARING') {
    if (avgEAR > 0 && mar > 0) {
      baselineSamples.push({ mar, ear: avgEAR })
    }
    
    // 退出准备期条件：达到prepMs上限 或 采集到10个有效帧
    const prepDone = Date.now() >= prepDeadline || baselineSamples.length >= 10
    
    if (prepDone) {
      if (baselineSamples.length >= 3) {
        // 计算中位数baseline（抗噪）
        const marValues = baselineSamples.map(s => s.mar).sort((a, b) => a - b)
        marBaseline.value = marValues[Math.floor(marValues.length / 2)]
      } else {
        // 有效帧不足，fallback到第一帧
        marBaseline.value = baselineSamples[0]?.mar || 0.3
      }
      startCurrentAction()
    }
    return
  }
  
  // ===== DETECTED / IN_PROGRESS: 动作判定 =====
  const action = props.actions[currentActionIndex.value]
  
  if (state.value === 'DETECTED') {
    if (action === 'blink' && avgEAR < EAR_CLOSED_THRESHOLD) {
      state.value = 'IN_PROGRESS'
    } else if (action === 'open_mouth' && mar > marBaseline.value + MAR_OPEN_DELTA) {
      state.value = 'IN_PROGRESS'
    }
    emit('progress', { state: state.value, ear: avgEAR, mar })
    return
  }
  
  if (state.value === 'IN_PROGRESS') {
    let completed = false
    if (action === 'blink' && avgEAR > EAR_OPEN_THRESHOLD) {
      completed = true
    } else if (action === 'open_mouth' && mar < marBaseline.value + MAR_CLOSED_DELTA) {
      completed = true
    }
    
    if (completed) {
      if (currentActionIndex.value < props.actions.length - 1) {
        // 还有下一个动作：语音确认后进入缓冲，再启动下一动作
        currentActionIndex.value++
        speak('通过', () => {
          setTimeout(() => startCurrentAction(), 800)  // TTS播放完+800ms缓冲
        })
      } else {
        // 全部完成
        speak('验证成功')
        completeVerification()
      }
      return
    }
    
    emit('progress', { state: state.value, ear: avgEAR, mar })
  }
}
```

---

## 6. Attendance.vue 修改详情

### 6.1 适配双动作响应

```javascript
const challenge = ref(null)

async function fetchChallenge() {
  const { data } = await request.get('/attendance/action-challenge')
  challenge.value = data.data  // { challenge_id, actions, descriptions, timeout_seconds }
}

// 模板中显示当前进度
// "动作 1/2：请眨眼" → 完成后 → "动作 2/2：请张嘴"
```

### 6.2 FaceMeshDetector 调用

```vue
<FaceMeshDetector
  v-if="showFaceMesh"
  ref="faceMeshRef"
  :actions="challenge.actions"
  :descriptions="challenge.descriptions"
  :timeout-seconds="challenge.timeout_seconds"
  @verified="onFaceMeshVerified"
  @progress="onFaceMeshProgress"
  @error="onFaceMeshError"
/>
```

---

## 7. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| TTS在某些浏览器不支持 | 无语音引导 | 降级为文字提示（emit `tts` 事件），不阻断流程；具体检测逻辑见5.3节 `speak()` 实现 |
| 双动作总时间超过用户耐心 | 用户放弃 | 单个动作超时10秒，总体验约20秒内完成；提供"跳过动作验证"按钮回退到CameraCapture |
| 准备期内用户提前张嘴 | baseline偏高 | 准备期仅500ms，中位数抗噪；即使偏高，张嘴delta=0.15仍能检测；有效帧不足3帧时fallback到首帧值 |
| 连续动作切换过快 | 用户反应不及 | TTS `onend` 回调 + 800ms缓冲，确保语音播放完再进入下一动作 |
| 准备期无有效帧（人脸未对准） | baseline无法建立 | 准备期最长3秒（ prepMs=500ms + 人脸检测等待），超时后提示"未检测到人脸，请正对摄像头" |
| 动作序列中某一动作失败 | 用户困惑 | 整体验证失败，提示"验证未通过，请重新开始"，用户可点击"重新验证"从头执行完整序列 |
| 旧前端调用新后端 | 兼容性问题 | 后端同时返回 `action_type`/`description`（单字符串）和 `actions`/`descriptions`（数组），旧前端行为不变 |

---

## 8. 交付标准

### 8.1 必做

- [ ] FaceMeshDetector.vue 支持动作序列和准备期baseline采集
- [ ] 语音引导使用浏览器原生TTS实现
- [ ] 双动作序列（眨眼+张嘴）随机顺序执行
- [ ] 动作间TTS onend + 800ms缓冲
- [ ] 后端 action-challenge 返回 actions + action_type（兼容旧前端）
- [ ] 旧前端调用兼容（单动作行为不变）
- [ ] 准备期无有效帧时超时提示

### 8.2 验证点

- [ ] 单动作挑战（旧模式）仍能正常工作
- [ ] 双动作序列正确执行（两种顺序都测试）
- [ ] 准备期内baseline采集不影响用户体验
- [ ] 超时和跳过按钮工作正常
- [ ] 无语音浏览器降级为纯文字提示
- [ ] 动作1完成后正确进入动作2（计时器重置）
- [ ] 准备期无有效帧时正确超时失败

---

*文档结束*
