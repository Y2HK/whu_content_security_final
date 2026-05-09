# 活体检测模块详细设计

> 文档类型：子模块实现规格说明书  
> 日期：2026-05-08  
> 适用：基于《基于人脸识别的班级考勤系统》原有设计，对接现有基础版代码  

---

## 1. 设计目标

将当前基础版中所有**活体检测占位逻辑**替换为真实实现，达成：

1. **前端动作活体**：基于 MediaPipe Face Mesh 实时检测面部 468 个关键点，验证眨眼/张嘴动作的时序连贯性。
2. **后端纹理活体**：基于 CNN 分析面部纹理伪影，区分真实人脸与照片/屏幕翻拍/视频重放攻击。
3. **两级独立防线**：前端动作检测为第一层（防照片），后端纹理检测为第二层（防视频），互不依赖。
4. **模型自动降级**：运行时按"自研 CNN → CDCN → Silent-Face"顺序自动选择可用模型。
5. **零侵入集成**：仅修改 `liveness_service.py`、`attendance.py`、`FaceMeshDetector.vue`，不改动数据库结构与其他业务模块。

---

## 2. 与现有代码的集成边界

### 2.1 需要修改的文件

| 文件 | 当前状态 | 修改内容 |
|------|----------|----------|
| `backend/app/services/liveness_service.py` | 仅返回占位字典 | 替换为完整的活体检测引擎（含三级模型加载） |
| `backend/app/routers/attendance.py` | 调用 `get_liveness_placeholder()` | 改为真实活体检测调用，将结果写入 `is_live` 和 `live_method` |
| `frontend/src/components/FaceMeshDetector.vue` | 仅文件占位 | 实现 MediaPipe Face Mesh 动作检测完整逻辑 |
| `frontend/src/views/Attendance.vue` | 直接拍照上传 | 增加动作挑战流程：获取指令 → MediaPipe 检测 → 通过后拍照 → 提交 |

### 2.2 不需要修改的文件

- `backend/app/db/models.py`：`is_live`、`live_method` 字段已存在
- `backend/app/core/security.py`：AES 加密用于人脸特征，与活体检测无关
- `backend/app/services/face_service.py`：人脸比对逻辑独立，不受影响
- `backend/app/services/emotion_service.py`：情绪分析独立，不受影响
- 所有合照识别、统计、学生管理模块：不受影响

---

## 3. 前端动作活体设计

### 3.1 组件：FaceMeshDetector.vue

**职责：** 封装 MediaPipe Face Mesh 的加载、实时关键点检测、动作验证逻辑。

**输入（Props）：**

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `actionType` | String | 是 | 动作类型：`"blink"` 或 `"open_mouth"` |
| `timeoutSeconds` | Number | 否 | 动作超时时间，默认 10 秒 |

**说明：** 组件内部自行创建 `<video>` 元素并通过 WebRTC 获取摄像头流，不依赖外部传入 video 元素。通过 `ref` 暴露 `startDetection()` 和 `stopDetection()` 方法供父组件调用。

**输出（Events）：**

| 事件 | 参数 | 说明 |
|------|------|------|
| `verified` | `{ success: boolean, imageBlob: Blob, meta: object }` | 动作验证结果（含采集图像） |
| `progress` | `{ state: string, ear?: number, mar?: number }` | 实时状态更新 |

**核心算法：**

```
EAR（眼睛纵横比）= (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
MAR（嘴巴纵横比）= (||p51-p59|| + ||p53-p57||) / (2 * ||p49-p55||)

MediaPipe Face Mesh 关键点索引：
- 左眼：362, 385, 387, 263, 373, 380
- 右眼：33, 160, 158, 133, 153, 144
- 嘴巴：61, 291, 13, 14, 78, 308, 402, 178
```

**动作验证时序：**

| 动作 | 验证条件 | 阈值 |
|------|----------|------|
| 眨眼 | EAR 先下降至阈值以下，再恢复至正常范围 | EAR < 0.2 为闭眼，EAR > 0.25 为睁眼 |
| 张嘴 | MAR 上升至阈值以上，再恢复至正常范围 | MAR > 0.5 为张嘴，MAR < 0.3 为闭嘴 |

**状态机：**

```
IDLE ──> 检测到人脸 ──> DETECTED ──> 动作开始（EAR下降/MAR上升）──> IN_PROGRESS
                              │
                              └──> 超时 ──> FAILED

IN_PROGRESS ──> 动作完成（EAR恢复/MAR恢复）──> VERIFIED
           │
           └──> 超时 ──> FAILED
```

### 3.2 页面流程：Attendance.vue

**修改后的考勤流程：**

```
1. 用户进入考勤页
2. 前端调用 GET /attendance/action-challenge 获取随机动作指令
   └─ 后端生成 challenge_id，存入内存缓存（TTL 60秒）
3. 前端显示动作提示（"请眨眼"或"请张嘴"）
4. 用户点击"开始验证"，FaceMeshDetector 组件内部开启 WebRTC 摄像头
5. MediaPipe 实时检测面部关键点，验证动作时序
6. 动作验证通过后，组件通过 @verified 事件通知父组件，同时返回采集的图像 Blob
7. 前端将 image + challenge_id + action_meta 提交到 POST /attendance/check
8. 后端校验 challenge_id 有效性（未过期、未使用）
9. 后端对整张图片进行纹理活体检测（不依赖人脸检测，直接对输入图像分析）
10. 纹理检测通过 → 继续人脸识别、情绪分析 → 写入考勤记录
11. 返回考勤结果
```

> **关于 TTL 60秒 vs 前端超时 10秒：** challenge 在后端保留 60 秒，但前端仅给用户 10 秒完成动作。这样设计的目的是：如果用户在前端超时前刚好完成动作但网络延迟导致提交稍晚， challenge 仍然有效。10-60 秒之间的重试是允许的。

> **关于 CameraCapture.vue 与 FaceMeshDetector.vue 的摄像头冲突：** 动作活体检测阶段使用 `FaceMeshDetector`（内部管理摄像头），动作通过后关闭并采集图像；旧的 `CameraCapture` 拍照流程作为降级保留。两者不会同时运行。

> **关于 `action_verified` 和 `action_meta`：** 这两个参数由前端传入，后端仅记录到日志中用于审计追溯，**不作为安全判定依据**（前端数据可被伪造）。安全判定仅依赖后端 texture 检测和 challenge_id 校验。

### 3.3 action-challenge 接口设计

**接口：** `GET /api/v1/attendance/action-challenge`

**响应格式：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "challenge_id": "uuid-string",
    "action_type": "blink",
    "description": "请眨眼",
    "timeout_seconds": 10
  }
}
```

**后端 challenge 存储与校验机制：**

由于课程设计场景无需持久化 challenge 数据，使用内存字典 + TTL 实现。注意：此方案仅适用于 FastAPI 单进程开发服务器（`uvicorn` 单 worker），多 worker 部署需改用 Redis 等共享存储。

```python
# backend/app/routers/attendance.py
import random
import uuid
from datetime import datetime, timedelta

# 内存缓存：{challenge_id: {"action_type": str, "expires_at": datetime, "used": bool}}
# ⚠️ 注意：此方案仅适用于 FastAPI 单进程开发服务器（uvicorn 单 worker）。
#    多 worker 部署需改用 Redis 等共享存储。
_challenge_store = {}

def _cleanup_expired_challenges():
    """清理已过期的 challenge，防止内存泄漏。"""
    now = datetime.utcnow()
    expired = [k for k, v in _challenge_store.items() if now > v["expires_at"]]
    for k in expired:
        del _challenge_store[k]

@router.get("/action-challenge")
def action_challenge(user = Depends(get_current_user)):
    _cleanup_expired_challenges()
    challenge_id = str(uuid.uuid4())
    action_type = random.choice(["blink", "open_mouth"])
    _challenge_store[challenge_id] = {
        "action_type": action_type,
        "expires_at": datetime.utcnow() + timedelta(seconds=60),
        "used": False,
    }
    return success({
        "challenge_id": challenge_id,
        "action_type": action_type,
        "description": "请眨眼" if action_type == "blink" else "请张嘴",
        "timeout_seconds": 10,
    })

# 在 attendance_check 中校验
def _validate_challenge(challenge_id: str) -> bool:
    if not challenge_id:
        return False
    _cleanup_expired_challenges()
    challenge = _challenge_store.get(challenge_id)
    if not challenge:
        return False
    if challenge["used"]:
        return False
    if datetime.utcnow() > challenge["expires_at"]:
        return False
    challenge["used"] = True
    return True
```

**校验失败响应：** `400 Bad Request`，`detail: "动作验证凭证无效或已过期"`

---

## 4. 后端纹理活体设计

### 4.1 模块：liveness_service.py

**职责：** 统一管理活体检测模型，提供统一的 `predict()` 接口，内部处理模型加载和自动降级。

**命名说明：** 直接修改现有 `backend/app/services/liveness_service.py` 文件，将占位函数替换为 `LivenessEngine` 类。对外暴露单例实例 `liveness_engine`。

**模型加载优先级：**

```
运行时启动:
  ├─ 尝试加载 models/custom_live.pth （自研CNN，输入256x256）
  │    └─ 成功 ──> model_type = "custom"
  │
  ├─ 尝试加载 models/minifasnet_v2.onnx （MiniFASNet ONNX，输入128x128 RGB）
  │    └─ 成功 ──> model_type = "minifasnet"
  │
  ├─ 尝试加载 models/cdcn_live.pth （CDCN预训练，输入256x256）
  │    └─ 成功 ──> model_type = "cdcn"
  │
  └─ 尝试加载 Silent-Face-Anti-Spoofing （输入80x80）
       └─ 成功 ──> model_type = "silent_face"
       └─ 失败 ──> model_type = "none"，predict始终返回is_live=True（降级为不过滤）
```

**统一输入接口：**

对外暴露统一接口 `predict(image_input: bytes | np.ndarray)`，支持直接传入图片字节流或 ndarray。内部自动完成解码和预处理：

```python
def predict(self, image_input) -> dict:
    # 如果输入是 bytes，先解码为 ndarray
    if isinstance(image_input, bytes):
        import numpy as np
        import cv2
        nparr = np.frombuffer(image_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        img = image_input
    # ... 继续预处理
```

| 模型 | 预处理 | 输出 |
|------|--------|------|
| custom | resize 256x256 → RGB → normalize([-1,1]) → Tensor | Sigmoid概率 |
| minifasnet | resize 128x128 → RGB → [0,1] → NCHW；含自适应gamma校正（暗光提亮） | Softmax 2-class [live, spoof] |
| cdcn | resize 256x256 → RGB → normalize([-1,1]) → Tensor | Sigmoid概率 |
| silent_face | resize 按模型要求尺寸 → 颜色空间转换（参考具体库文档）→ ToTensor → Tensor | 二分类概率 |

**输出格式：**

```python
{
    "is_live": bool,        # 是否活体
    "confidence": float,    # 置信度 0-1
    "method": str,          # "custom" / "cdcn" / "silent_face" / "none"
    "model_loaded": bool    # 模型是否成功加载
}
```

**配置项（新增到 app/core/config.py）：**

| 配置名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `ENABLE_LIVENESS` | bool | True | 是否启用活体检测 |
| `LIVENESS_THRESHOLD` | float | 0.5 | 活体判定阈值（< 阈值判定为攻击） |
| `CUSTOM_MODEL_PATH` | Path | models/custom_live.pth | 自研CNN权重路径 |
| `CDCN_MODEL_PATH` | Path | models/cdcn_live.pth | CDCN权重路径 |
| `MINIFASNET_MODEL_PATH` | Path | models/minifasnet_v2.onnx | MiniFASNet ONNX模型路径 |
| `SILENT_FACE_MODEL_PATH` | Path | models/silent_face | Silent-Face模型目录 |

### 4.2 自研 CNN 模型（加分项，可选）

自研 CNN 模型结构、训练流程和评估指标详见附录《自研活体检测模型训练指南》。本节仅列出核心信息：

- 网络结构：4 层 Conv-BN-ReLU-Pool + GAP + FC + Sigmoid
- 输入尺寸：256×256×3
- 输出：活体概率（0-1）
- 训练数据集：CASIA-FASD / OULU-NPU 公开数据集
- **注意：** 自研模型训练作为加分项，基础交付不要求完成。

### 4.3 路由集成：attendance.py

**修改点：**

```python
# 修改后的 attendance_check 函数签名
@router.post("/check")
def attendance_check(
    file: UploadFile = File(...),
    challenge_id: str | None = Form(None),   # 新增：动作挑战ID（兼容旧调用：None 表示跳过动作校验）
    action_verified: bool = Form(False),     # 新增：前端动作检测结果（仅日志记录，不作安全判定）
    action_meta: str | None = Form(None),    # 新增：动作检测元数据（仅日志记录，不作安全判定）
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    # ... 现有代码 ...

    # 校验 challenge_id 有效性（如果提供了 challenge_id）
    if challenge_id is not None and not _validate_challenge(challenge_id):
        raise HTTPException(status_code=400, detail="动作验证凭证无效或已过期")

    # 纹理活体检测：直接对上传的整张图片进行检测
    # 不依赖外部人脸检测模块（当前 face_service.py 为模拟实现）
    # 注：早期技术 API 文档中"裁剪人脸区域"的描述已过时，以本 spec 的整图分析为准。
    image_bytes = file.file.read()
    live_result = liveness_engine.predict(image_bytes)

    # 活体检测策略：
    # - 模型加载失败（model_type="none"）：演示降级，默认通过，不打断流程
    #   （注意：此降级仅用于课程设计演示场景，生产环境不应允许）
    # - 模型加载成功但置信度低：拒绝考勤（400）
    if live_result["model_loaded"] and not live_result["is_live"]:
        raise HTTPException(status_code=400, detail="活体检测未通过，请使用真实人脸")

    record = Attendance(
        ...,
        is_live=live_result["is_live"],
        live_method=live_result["method"],
        ...,
    )
    # ... 现有代码 ...

    return success({
        "record_id": record.record_id,
        # ... 其他字段 ...
        "live_result": {
            "is_live": live_result["is_live"],
            "confidence": live_result["confidence"],
            "method": live_result["method"],
            "model_loaded": live_result["model_loaded"],
        },
    })
```

---

## 5. 数据流时序图

### 5.1 完整考勤流程（含双阶段活体）

```
浏览器(前端)                    后端(FastAPI)                  数据库
    │                              │                             │
    ├─ GET /attendance/action-challenge ──>│                             │
    │<─ 返回 challenge_id + action_type ───┤ 内存存储 challenge(TTL 60s) │
    │                              │                             │
    ├─ MediaPipe 实时检测关键点     │                             │
    ├─ 验证动作时序（眨眼/张嘴）    │                             │
    ├─ 动作通过，采集单帧图像       │                             │
    │                              │                             │
    ├─ POST /attendance/check ─────>│                             │
    │   (image + challenge_id + action_meta)                     │
    │                              ├─ 校验 challenge_id 有效性    │
    │                              ├─ 纹理活体检测（整图输入）      │
    │                              │   ├─ 模型未加载 ──> 默认通过 │
    │                              │   ├─ 模型判定假 ──> 400 拒绝 │
    │                              │   └─ 模型判定真 ──> 继续    │
    │                              ├─ 情绪分析（已有 DeepFace）   │
    │                              ├─ 人脸识别（现有模拟/占位）   │
    │                              ├─ 写入 attendance 表 ───────>│
    │<─ 返回考勤结果 ────────────────┤                             │
```

---

## 6. 测试策略

### 6.1 单元测试

| 测试项 | 测试内容 | 期望结果 |
|--------|----------|----------|
| 模型加载 | 删除 custom_live.pth，验证 CDCN 自动加载 | model_type = "cdcn" |
| 模型降级 | 删除所有模型权重，验证降级为 "none" | predict 返回 is_live=True |
| 纹理检测 | 输入真实人脸照片 | is_live=True（模型加载成功时） |
| 纹理检测 | 输入打印照片翻拍 | is_live=False（模型加载成功时） |
| EAR 计算 | 闭眼帧 EAR < 0.2 | 状态机进入 IN_PROGRESS |
| 动作超时 | 超过 10 秒未完成动作 | 返回 FAILED |

### 6.2 集成测试

| 测试项 | 测试内容 |
|--------|----------|
| 完整考勤 | 前端动作验证 → 后端纹理验证 → 考勤记录写入 |
| 照片攻击 | 上传打印照片 → 期望纹理检测拒绝 |
| 权限隔离 | 学生账号无法查看他人考勤记录 |

---

## 7. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| MediaPipe 在某些浏览器加载失败 | 前端动作检测不可用 | 考勤页显示"跳过动作验证"按钮；点击后直接进入拍照上传流程，依赖后端纹理检测 |
| 后端纹理模型也降级为 none | 两层防线均不可用 | 系统回退到基础版行为（不检测活体），在控制台打印警告日志 |
| 单进程内存 challenge 存储限制 | 多 worker 部署时 challenge 无法共享 | 本设计仅适用于 uvicorn 单 worker；多 worker 需改用 Redis（课程设计场景单进程足够） |
| MiniFASNet/CDCN/Silent-Face 模型下载失败 | 纹理检测不可用 | 降级为 "none" 模式，所有请求默认通过（仅用于演示） |
| 纹理模型误杀率过高 | 真实人脸被误判为攻击 | 通过环境变量 LIVENESS_THRESHOLD 调整阈值（默认 0.5） |
| 自研 CNN 训练数据不足 | 模型精度不达标 | 使用公开数据集，精度不达标不影响基础交付（fallback可用即可） |

---

## 8. 交付标准

### 8.1 必做（基础交付）

- [ ] FaceMeshDetector.vue 实现完整的 MediaPipe 动作检测
- [x] liveness_service.py 实现 MiniFASNet ONNX 纹理检测（含自适应暗光校正）
- [ ] attendance.py 集成真实活体检测结果
- [ ] 前端考勤页面支持动作挑战流程
- [ ] 活体检测失败时正确拒绝考勤

### 8.2 加分项（可选）

- [ ] 自研 CNN 模型训练并达到 FAR≤1%, FRR≤5%
- [ ] 3D 面具攻击防御
- [ ] 活体检测响应时间 ≤ 2s

---

*文档结束*
