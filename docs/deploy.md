# 部署说明

## 1. 运行环境

- Python 3.10+
- Node.js 18+
- Windows 10/11 或其他支持 Python、Node.js 的系统

## 2. 后端启动

在 `backend` 目录下执行：

```bash
copy .env.example .env
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

启动后可访问：

- Swagger 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

默认教师账号：

- 用户名：`teacher`
- 密码：`teacher123`

密码哈希方案使用 `pbkdf2_sha256`，避免部分 Windows 环境下 `bcrypt` 兼容性问题。

### 2.1 模型准备（首次启动）

后端使用 InsightFace `buffalo_l` 模型包（RetinaFace 检测 + ArcFace 512 维特征提取）。首次启动时，如果 `backend/models/buffalo_l/` 目录不存在且没有 `.onnx` 模型文件，系统会自动从 GitHub 下载 `buffalo_l.zip`（约 275MB）并解压。

**注意：** 自动下载可能需要较长时间（取决于网络环境），下载期间任何人脸检测相关请求都会阻塞等待。建议提前下载并放置到 `backend/models/buffalo_l/` 目录。

## 3. 前端启动

在 `frontend` 目录下执行：

```bash
npm install
npm run dev
```

默认开发地址：

- `http://localhost:5173`

接口地址配置在：

- `frontend/.env.local`

```env
VITE_API_BASE_URL=/api/v1
```

前端通过 Vite Dev Server 代理将 `/api` 请求转发到后端 `http://127.0.0.1:8000`，避免跨域问题。

## 4. 演示建议流程

1. 启动后端服务
2. 启动前端服务
3. 使用默认教师账号登录
4. 在"学生管理"中手动新增学生或导入 `docs/sample-students.csv`
5. 上传学生照片建立基础人脸数据
6. 在"基础考勤"中使用摄像头进行活体检测 + 考勤
7. 在"合照识别"页面上传图片并查看活动名单
8. 在"统计分析"页面查看情绪与活动统计图

## 5. 活体检测三级架构

系统采用"前端动作检测 + 后端纹理检测 + 模型自动降级"的三级活体检测架构。

### 5.1 第一级：前端动作活体检测

使用 MediaPipe Face Mesh 实时检测面部 468 个关键点，验证眨眼/张嘴动作的时序连贯性。

**核心算法：**

- EAR（眼睛纵横比）= (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
- MAR（嘴巴纵横比）= (||p51-p59|| + ||p53-p57||) / (2 * ||p49-p55||)

**状态机：**

```
IDLE --点击开始--> PREPARING(500ms 采集 baseline)
                        |
                        +--> DETECTED(动作1) --> IN_PROGRESS(动作1)
                                                      |
                                                      +-- 超时 --> FAILED
                                                      +-- 完成 --> TRANSITIONING
                                                                      |
                                                                      +--> DETECTED(动作2) --> IN_PROGRESS(动作2)
                                                                                                    |
                                                                                                    +-- 超时 --> FAILED
                                                                                                    +-- 完成 --> VERIFIED
```

**阈值说明：**

| 动作 | 触发条件 | 完成条件 |
|------|----------|----------|
| 眨眼 | EAR < 0.18（闭眼） | EAR > 0.22（睁眼） |
| 张嘴 | MAR > baseline * 1.5 | MAR < baseline * 1.2 |

**baseline 计算：** 准备期采集 10 帧 MAR 样本，去掉最高 10% 的异常值后取最小值作为闭合 baseline。

### 5.2 第二级：后端纹理活体检测

对上传的整张图片进行 CNN 纹理分析，区分真实人脸与照片/屏幕翻拍/视频重放攻击。

**LivenessEngine 统一输出：**

```json
{
  "is_live": true,
  "confidence": 0.85,
  "method": "custom",
  "model_loaded": true
}
```

**检测策略：**

- 模型加载成功且 `is_live=false`：拒绝考勤，返回 400
- 模型未加载（`model_loaded=false`）：演示降级，默认通过，记录警告日志

### 5.3 第三级：模型自动降级

LivenessEngine 启动时按以下顺序尝试加载模型，直至成功或全部失败：

```
尝试加载 models/custom_live.pth （自研 CNN，256x256 输入）
    +-- 成功 --> model_type = "custom"
    |
    +-- 失败
          |
          +--> 尝试加载 models/cdcn_live.pth （CDCN，256x256 输入）
          |       +-- 成功 --> model_type = "cdcn"
          |       |
          |       +-- 失败
          |             |
          |             +--> 尝试加载 models/silent_face/ （Silent-Face，80x80 输入）
          |                     +-- 成功 --> model_type = "silent_face"
          |                     |
          |                     +-- 失败 --> model_type = "none"
          |                                     predict 始终返回 is_live=True
```

**当前状态：** 由于 PyTorch 未安装（`torch` 不在 requirements.txt 中），custom 和 CDCN 模型无法加载；Silent-Face 库也未安装。因此当前实际运行状态为 `model_type="none"`，纹理检测始终返回 `is_live=True`。如需启用真实纹理检测，需安装 `torch` 并放置预训练权重文件。

## 6. 当前版本说明

### 6.1 已实现功能

- [x] 完整的人脸识别流程（InsightFace ArcFace 512 维特征提取）
- [x] 前端双动作序列活体检测（MediaPipe Face Mesh + 语音引导）
- [x] 后端 challenge 机制（内存 TTL 存储，防重放）
- [x] 情绪分析（DeepFace + fallback）
- [x] 学生管理、合照识别、考勤记录、统计报表
- [x] 权限隔离（教师/学生角色）

### 6.2 已知限制

- `buffalo_l` 模型首次下载约 275MB，可能耗时较长
- 活体检测纹理模型当前降级为 `none`（需安装 torch + 放置权重才能启用真实检测）
- challenge 存储使用内存字典，仅适用于 FastAPI 单进程开发服务器
- 无 GPU 时自动 fallback 到 CPU 推理，速度较慢

## 7. 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ENABLE_LIVENESS` | `True` | 是否启用活体检测 |
| `LIVENESS_THRESHOLD` | `0.5` | 活体判定阈值 |
| `FACE_SIMILARITY_THRESHOLD` | `0.6` | 1:1 人脸比对阈值 |
| `GROUP_FACE_SIMILARITY_THRESHOLD` | `0.55` | 合照 1:N 比对阈值 |
| `CUSTOM_MODEL_PATH` | `models/custom_live.pth` | 自研 CNN 权重路径 |
| `CDCN_MODEL_PATH` | `models/cdcn_live.pth` | CDCN 权重路径 |
| `SILENT_FACE_MODEL_PATH` | `models/silent_face` | Silent-Face 模型目录 |
