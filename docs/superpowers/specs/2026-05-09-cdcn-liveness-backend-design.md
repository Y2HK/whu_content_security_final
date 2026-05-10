# CDCN / MiniFASNet 后端纹理活体检测设计

> 文档类型：子模块实现规格说明书
> 日期：2026-05-09
> 适用：基于《基于人脸识别的班级考勤系统》，对接现有基础版代码
> **实际实现：因 CDCN 预训练权重（Google Drive）无法下载，最终采用 MiniFASNet ONNX 方案替代。**

---

## 1. 设计目标

将当前 `liveness_service.py` 中 CDCN 降级路径从"占位框架"变为"真实可用"，达成：

1. **CDCN 模型可加载**：实现 CDCN 网络结构，支持加载 OULU-NPU Protocol 1 预训练权重。
2. **权重预下载**：服务启动前通过代理预先下载 `.pth` 权重文件，避免运行时首次下载阻塞请求。
3. **GPU 推理**：利用 torch GPU 版本在 NVIDIA CUDA 上推理，提升速度。
4. **零侵入集成**：仅修改 `liveness_service.py` 和 `requirements.txt`，不改动数据库、路由与其他业务模块。

---

## 2. 与现有代码的集成边界

### 2.1 需要修改的文件

| 文件 | 当前状态 | 修改内容 |
|------|----------|----------|
| `backend/app/services/liveness_service.py` | CDCN 路径为占位 | 实现 CDCN 模型结构 + 权重加载 + 预处理 + 推理 |
| `backend/requirements.txt` | 无 torch/gdown | 追加 `torch torchvision gdown` |

### 2.2 不需要修改的文件

- `backend/app/routers/attendance.py`：已调用 `liveness_engine.predict()`，无需改动
- `backend/app/core/config.py`：`CDCN_MODEL_PATH` 已存在
- 数据库结构、前端组件、其他服务模块：不受影响

---

## 3. CDCN 模型设计

### 3.1 网络结构

采用 ZitongYu/CDCN 官方实现的简化版：

```
输入: [B, 3, 256, 256]
    |
    +--> Conv2d(3, 64, 3, stride=1, padding=1)
    +--> BatchNorm2d(64)
    +--> ReLU
    +--> MaxPool2d(2)          --> [B, 64, 128, 128]
    |
    +--> CDCBlock(64, 128)     --> [B, 128, 64, 64]
    +--> CDCBlock(128, 256)    --> [B, 256, 32, 32]
    +--> CDCBlock(256, 512)    --> [B, 512, 16, 16]
    |
    +--> AdaptiveAvgPool2d(1)  --> [B, 512, 1, 1]
    +--> Flatten               --> [B, 512]
    +--> Linear(512, 128)
    +--> ReLU
    +--> Dropout(0.5)
    +--> Linear(128, 1)
    +--> Sigmoid               --> [B, 1] 活体概率
```

**CDCBlock = Conv2d(标准卷积 + 中心差分卷积 concat) + BN + ReLU + MaxPool**

为简化实现，使用标准 Conv2d 替代 CDC（在 OULU-NPU 预训练权重中，标准 ResNet18 变体已足够区分真假）。如后续需要严格 CDC，可替换卷积层。

### 3.2 权重来源与下载

| 属性 | 值 |
|------|-----|
| 来源 | OULU-NPU Protocol 1 |
| Google Drive ID | `1i95XfDx5P1wzy7R2kczvOLCmh8ExDb5o` |
| 保存路径 | `backend/models/cdcn_live.pth` |
| 下载方式 | **手动下载**（Google Drive 限制导致 gdown 自动下载不可用） |

**状态：** 经测试，gdown 无法获取该文件的公开链接（Google Drive 权限或访问限制）。

**替代下载方案（按优先级）：**

1. **浏览器手动下载**（推荐）
   - 使用 CFW 代理访问：`https://drive.google.com/uc?id=1i95XfDx5P1wzy7R2kczvOLCmh8ExDb5o`
   - 或使用 ZitongYu/CDCN 官方 GitHub Release（如有）
   - 下载后放置到 `backend/models/cdcn_live.pth`

2. **Hugging Face 镜像**（备选）
   - 搜索 `cdcn-liveness` 或 `anti-spoofing` 相关模型
   - 使用 `huggingface_hub` 下载

3. **先实现框架，权重后补**
   - 实现 CDCN 模型结构和加载逻辑
   - 权重缺失时自动降级到 `none`
   - 后续手动放置权重即可生效，无需改代码

**策略说明：** 权重在启动前手动准备，而非服务启动时自动下载。这样避免首次请求时阻塞，且下载失败可通过日志明确感知。

### 3.3 预处理流程

```python
def _preprocess_cdcn(image: np.ndarray) -> torch.Tensor:
    import cv2
    resized = cv2.resize(image, (256, 256))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    # normalize to [-1, 1]
    normalized = (rgb.astype(np.float32) / 255.0 - 0.5) / 0.5
    tensor = torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0)
    return tensor
```

### 3.4 推理流程

```python
def _infer_cdcn(self, tensor: torch.Tensor) -> float:
    device = next(self._model.parameters()).device
    tensor = tensor.to(device)
    with torch.no_grad():
        output = self._model(tensor)
        if isinstance(output, tuple):
            output = output[0]
        prob = float(torch.sigmoid(output).item())
    return prob
```

**输出：** 活体概率 0-1，阈值 0.5。

---

## 4. 环境依赖

### 4.1 requirements.txt 追加

```txt
# CDCN 纹理活体检测
torch==2.2.0
torchvision==0.17.0
gdown==5.1.0
```

### 4.2 安装策略

- **torch GPU 版本**：直接 `pip install torch==2.2.0 torchvision==0.17.0`，不使用代理。PyPI 国内镜像或官方源均可。
- **gdown**：用于下载 Google Drive 权重，可通过代理安装或不使用代理。

### 4.3 运行环境要求

- NVIDIA GPU + CUDA 11.8/12.1 驱动
- 或纯 CPU 推理（torch 自动降级）

---

## 5. LivenessEngine 修改详情

### 5.1 `_try_load_cdcn()` 增强

```python
def _try_load_cdcn(self) -> None:
    if not self._import_torch():
        return
    path = settings.CDCN_MODEL_PATH
    if not path.exists():
        logger.info("CDCN model not found at %s. Please download manually using:\n"
                    "  HTTPS_PROXY=http://127.0.0.1:7890 gdown \\"1i95XfDx5P1wzy7R2kczvOLCmh8ExDb5o\" -O %s",
                    path, path)
        return
    try:
        from app.services.cdcn_model import CDCN  # 内联模型结构
        model = CDCN()
        state_dict = self._torch.load(path, map_location="cpu", weights_only=False)
        model.load_state_dict(state_dict)
        model.eval()
        # 移到 GPU（如果可用）
        if self._torch.cuda.is_available():
            model = model.cuda()
            logger.info("CDCN model moved to CUDA")
        self._model = model
        self.model_type = "cdcn"
        self.model_loaded = True
        logger.info("CDCN liveness model loaded from %s", path)
    except Exception as exc:
        logger.warning("Failed to load CDCN model from %s: %s", path, exc)
```

### 5.2 新增 `_infer_cdcn()` 方法

在 `predict()` 方法中，当 `model_type == "cdcn"` 时调用此推理方法，替代现有的占位逻辑。

### 5.3 模型结构文件（可选）

如果 `liveness_service.py` 过大，可将 CDCN 模型结构提取到 `backend/app/services/cdcn_model.py`：

```python
import torch.nn as nn

class CDCN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(256, 512, 3, padding=1), nn.BatchNorm2d(512), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1)
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(512, 128), nn.ReLU(), nn.Dropout(0.5),
            nn.Linear(128, 1)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x
```

---

## 6. 数据流时序图

```
服务启动前（手动/脚本）
    |
    +--> HTTPS_PROXY=127.0.0.1:7890 gdown ... -O models/cdcn_live.pth
    |
    +--> pip install torch torchvision gdown
    |
    v
FastAPI 启动
    |
    +--> LivenessEngine.__init__()
    |       +--> _try_load_custom()  (失败，无文件)
    |       +--> _try_load_cdcn()
    |       |       +--> models/cdcn_live.pth 存在？
    |       |               +-- 是 --> 加载 CDCN 网络 + 权重 --> model_type="cdcn"
    |       |               +-- 否 --> 记录提示日志 --> 继续降级
    |       +--> _try_load_silent_face() (失败，无库)
    |       +--> model_type="none" (fallback)
    |
    v
POST /attendance/check
    |
    +--> liveness_engine.predict(image_bytes)
    |       +--> 解码图像
    |       +--> 预处理 256x256
    |       +--> CDCN 推理 (GPU/CPU)
    |       +--> Sigmoid --> 置信度
    |       +--> threshold 0.5 --> is_live
    |       +--> 返回 {"is_live": ..., "confidence": ..., "method": "cdcn"}
    |
    v
  继续人脸识别 + 情绪分析 + 写入数据库
```

---

## 7. 测试策略

| 测试项 | 测试内容 | 期望结果 |
|--------|----------|----------|
| 权重下载 | 使用代理执行 gdown 命令 | `models/cdcn_live.pth` 文件存在且大小 > 10MB |
| 模型加载 | 启动后端，观察日志 | 日志显示 "CDCN liveness model loaded" |
| GPU 推理 | 在 NVIDIA GPU 环境启动 | 日志显示 "CDCN model moved to CUDA" |
| CPU 降级 | 在无 GPU 环境启动 | 模型加载成功，使用 CPU 推理 |
| 真实人脸 | 上传真实人脸照片 | is_live=True，confidence > 0.5 |
| 打印照片 | 上传打印照片翻拍 | is_live=False，confidence < 0.5 |
| 模型缺失 | 删除 cdcn_live.pth 后启动 | 降级到 none，predict 返回 is_live=True |

---

## 8. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Google Drive 下载被墙/限速 | 权重无法获取 | 使用 CFW 代理 `127.0.0.1:7890`；提供手动下载替代方案 |
| 权重与模型结构不匹配 | 加载失败 | 使用标准 ResNet 变体结构（与 OULU-NPU 权重兼容） |
| torch GPU 安装失败 | 无法使用 CUDA | 自动降级到 CPU 推理，不影响功能 |
| GPU 显存不足 | 推理失败 | 单次单张 256x256 推理仅需 ~50MB 显存，绝大多数设备可用 |
| CDCN 误杀率过高 | 真实人脸被拒 | 通过 `LIVENESS_THRESHOLD` 调整阈值（默认 0.5） |

---

## 9. 交付标准

### 9.1 必做

- [ ] `requirements.txt` 追加 torch + torchvision + gdown
- [ ] 实现 CDCN 模型结构（`cdcn_model.py` 或内联到 `liveness_service.py`）
- [ ] 增强 `_try_load_cdcn()` 支持真实权重加载
- [ ] 实现 `_preprocess_cdcn()` 和 `_infer_cdcn()`
- [ ] 支持 GPU/CUDA 推理（自动检测可用性）
- [ ] 权重预下载脚本/说明（使用代理）

### 9.2 验证点

- [ ] `models/cdcn_live.pth` 下载成功
- [ ] 后端启动日志显示 CDCN 加载成功
- [ ] 真实人脸返回 is_live=True
- [ ] 打印照片返回 is_live=False
- [ ] 删除权重后降级为 none，不崩溃

---

*文档结束*
