# 班级考勤系统 — 技术文档与API接口详细说明

> 版本：v1.0  
> 日期：2026-04-28  
> 适用：课程设计报告技术实现章节

---

## 1. 系统模块结构

### 1.1 后端模块结构（backend/）

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口，路由挂载
│   ├── core/                # 核心基础设施
│   │   ├── config.py        # 全局配置（环境变量读取）
│   │   ├── security.py      # JWT生成/验证、bcrypt密码、AES-GCM加密
│   │   └── dependencies.py  # 依赖注入（get_db, get_current_user, require_teacher）
│   ├── db/                  # 数据层
│   │   ├── database.py      # SQLAlchemy Engine + SessionLocal
│   │   ├── models.py        # 7张数据表 ORM 定义
│   │   └── init_db.py       # 数据库初始化 + 默认用户创建
│   ├── schemas/             # Pydantic 数据校验模型
│   │   ├── auth.py          # 登录/Token/用户信息 schema
│   │   ├── student.py       # 学生增删改查 schema
│   │   ├── attendance.py    # 考勤提交/查询 schema
│   │   ├── group.py         # 合照上传/活动 schema
│   │   └── emotion.py       # 情绪统计 schema
│   ├── routers/             # API 路由层（按业务模块划分）
│   │   ├── auth.py          # /auth/* 认证相关接口
│   │   ├── students.py      # /students/* 学生管理接口
│   │   ├── attendance.py    # /attendance/* 考勤接口
│   │   ├── group.py         # /group/* 合照识别接口
│   │   └── emotion.py       # /emotion/* 情绪统计接口
│   └── services/            # 算法引擎层（核心业务逻辑）
│       ├── face_engine.py   # RetinaFace检测 + ArcFace识别
│       ├── liveness_engine.py # CDCN/Silent-Face 活体检测
│       ├── emotion_engine.py  # DeepFace 情绪分析
│       └── encryption.py    # AES-256-GCM 特征向量加解密
├── tests/                   # pytest 测试用例
│   ├── conftest.py          # 测试 fixtures（内存数据库、TestClient）
│   └── test_*.py            # 各模块单元测试
├── models/                  # 预训练模型权重存放目录
├── uploads/                 # 上传图片存储目录
├── requirements.txt         # Python 依赖清单
├── .env.example             # 环境变量模板
└── run.py                   # 启动脚本
```

### 1.2 前端模块结构（frontend/）

```
frontend/
├── src/
│   ├── main.js              # Vue 3 应用入口（挂载 App + 注册插件）
│   ├── App.vue              # 根组件（布局框架 + 路由视图）
│   ├── router/
│   │   └── index.js         # Vue Router 路由表（含权限守卫）
│   ├── api/
│   │   └── request.js       # Axios 封装（BaseURL + JWT拦截器 + 401处理）
│   ├── stores/
│   │   └── auth.js          # Pinia 认证状态（token、用户信息、登录态）
│   ├── views/               # 页面级组件（按路由对应）
│   │   ├── Login.vue        # 登录页
│   │   ├── Attendance.vue   # 考勤页（摄像头 + 动作活体 + 结果展示）
│   │   ├── GroupPhoto.vue   # 合照上传页
│   │   ├── Statistics.vue   # 统计报表页（ECharts 图表）
│   │   └── StudentManage.vue # 学生管理页（CRUD + 批量导入）
│   └── components/          # 可复用组件
│       ├── CameraCapture.vue    # 摄像头封装组件（WebRTC）
│       ├── FaceMeshDetector.vue # MediaPipe 动作检测组件
│       └── EmotionChart.vue     # ECharts 情绪统计图表组件
├── package.json             # Node.js 依赖
└── vite.config.js           # Vite 构建配置
```

---

## 2. API 接口详细说明

### 2.1 通用规范

- **Base URL:** `http://localhost:8000/api/v1`
- **认证方式:** Bearer Token（JWT）
- **Content-Type:** 常规接口 `application/json`，文件上传 `multipart/form-data`
- **通用响应格式:**

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

**错误响应格式:**

```json
{
  "detail": "错误描述信息"
}
```

**HTTP 状态码:**

| 状态码 | 含义 | 触发场景 |
|--------|------|----------|
| 200 | 成功 | 请求处理成功 |
| 400 | 请求参数错误 | 图像无效、缺少必填字段 |
| 401 | 未认证 | Token 缺失、过期或无效 |
| 403 | 权限不足 | 学生访问教师接口 |
| 404 | 资源不存在 | 学号不存在、活动不存在 |
| 500 | 服务器内部错误 | 模型加载失败、数据库异常 |

---

### 2.2 认证模块（/auth）

#### 2.2.1 用户登录

- **接口:** `POST /auth/login`
- **权限:** 公开
- **Content-Type:** `application/json`
- **请求体:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名（教师: teacher） |
| password | string | 是 | 密码 |

```json
{
  "username": "teacher",
  "password": "teacher123"
}
```

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

- **错误响应:**
  - `401 Unauthorized`: 用户名或密码错误

---

#### 2.2.2 用户登出

- **接口:** `POST /auth/logout`
- **权限:** 登录用户
- **请求头:** `Authorization: Bearer <token>`
- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "message": "Logout successful"
  }
}
```

- **说明:** 课程设计场景下后端不设 Token 黑名单，依赖客户端删除 Token 和 Token 过期机制。

---

#### 2.2.3 获取当前用户信息

- **接口:** `GET /auth/me`
- **权限:** 登录用户
- **请求头:** `Authorization: Bearer <token>`
- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "username": "teacher",
    "role": "teacher",
    "student_id": null
  }
}
```

---

### 2.3 学生管理模块（/students）

#### 2.3.1 获取学生列表

- **接口:** `GET /students`
- **权限:** 教师
- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "student_id": 1,
      "student_no": "2023001",
      "name": "张三",
      "class_name": "计算机1班",
      "face_image_path": "./uploads/face_1.jpg"
    }
  ]
}
```

- **错误响应:**
  - `403 Forbidden`: 非教师角色

---

#### 2.3.2 添加学生

- **接口:** `POST /students`
- **权限:** 教师
- **Content-Type:** `application/json`
- **请求体:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| student_no | string | 是 | 学号 |
| name | string | 是 | 姓名 |
| class_name | string | 是 | 班级 |

```json
{
  "student_no": "2023001",
  "name": "张三",
  "class_name": "计算机1班"
}
```

- **成功响应 (200):** 返回创建的学生对象
- **错误响应:**
  - `400`: 学号已存在

---

#### 2.3.3 更新学生信息

- **接口:** `PUT /students/{student_id}`
- **权限:** 教师
- **路径参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| student_id | integer | 学生ID |

- **请求体:** 同添加学生（全部字段可选）
- **成功响应 (200):** 更新后的学生对象
- **错误响应:**
  - `404`: 学生不存在

---

#### 2.3.4 删除学生

- **接口:** `DELETE /students/{student_id}`
- **权限:** 教师
- **路径参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| student_id | integer | 学生ID |

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "message": "Deleted"
  }
}
```

---

#### 2.3.5 批量导入学生

- **接口:** `POST /students/batch`
- **权限:** 教师
- **Content-Type:** `multipart/form-data`
- **请求参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | Excel/CSV 文件，含 name/student_no/class_name 列 |

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "imported_count": 30,
    "failed_rows": []
  }
}
```

---

#### 2.3.6 重新采集人脸特征

- **接口:** `POST /students/{student_id}/face`
- **权限:** 教师
- **Content-Type:** `multipart/form-data`
- **路径参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| student_id | integer | 学生ID |

- **请求参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 人脸照片（JPG/PNG） |

- **处理流程:**
  1. 保存图片到 uploads/ 目录
  2. RetinaFace 检测人脸 → ArcFace 提取 512 维特征
  3. AES-256-GCM 加密特征向量
  4. 存入 face_feature 表（覆盖旧特征）

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "message": "Face uploaded and feature extracted"
  }
}
```

- **错误响应:**
  - `400`: 未检测到人脸
  - `404`: 学生不存在

---

### 2.4 考勤模块（/attendance）

#### 2.4.1 获取动作挑战指令

- **接口:** `GET /attendance/action-challenge`
- **权限:** 登录用户
- **说明:** 前端调用此接口获取随机动作指令（眨眼/张嘴），用于动作活体检测
- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "challenge_id": "550e8400-e29b-41d4-a716-446655440000",
    "action_type": "blink",
    "description": "请眨眼",
    "timeout_seconds": 10
  }
}
```

---

#### 2.4.2 提交考勤

- **接口:** `POST /attendance/check`
- **权限:** 登录用户
- **Content-Type:** `multipart/form-data`
- **请求参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image | File | 是 | 人脸图像（动作验证通过后采集的单帧图像） |
| challenge_id | string | 是 | 动作挑战ID |
| action_verified | boolean | 否 | 前端动作检测结果（后端仅作日志记录参考） |
| action_meta | JSON | 否 | 动作检测元数据（EAR/MAR序列、耗时等） |

- **后端处理流程:**
  1. 读取图像 → RetinaFace 检测人脸
  2. 裁剪人脸区域 → CDCN/Silent-Face 活体检测
  3. DeepFace 情绪分析
  4. ArcFace 提取特征 → 与 face_feature 表解密后的特征进行 1:N 比对
  5. 记录考勤数据到 attendance 表

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "考勤成功",
  "data": {
    "student_id": 1,
    "student_no": "2023001",
    "name": "张三",
    "status": "success",
    "is_live": true,
    "live_confidence": 0.98,
    "emotion": "happy",
    "emotion_confidence": 0.85,
    "check_time": "2026-04-28T14:30:00"
  }
}
```

- **错误响应:**
  - `400`: 图像无效 / 未检测到人脸
  - `404`: 学生未识别（人脸库无匹配）

---

#### 2.4.3 查询考勤记录

- **接口:** `GET /attendance/records`
- **权限:** 教师/学生（学生仅可查自己，后端从JWT自动过滤）
- **查询参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date_from | string | 否 | 开始日期（ISO格式，如 2026-04-01） |
| date_to | string | 否 | 结束日期 |
| student_id | integer | 否 | 学号筛选（仅教师可用） |

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "record_id": 1,
      "student_no": "2023001",
      "name": "张三",
      "check_time": "2026-04-28T14:30:00",
      "status": "success",
      "is_live": true,
      "emotion": "happy"
    }
  ]
}
```

---

#### 2.4.4 导出考勤记录

- **接口:** `GET /attendance/export`
- **权限:** 教师
- **查询参数:** 同查询接口
- **响应:** `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **说明:** 返回 Excel 二进制文件，包含考勤记录表格

---

### 2.5 合照识别模块（/group）

#### 2.5.1 上传合照进行识别

- **接口:** `POST /group/upload`
- **权限:** 教师
- **Content-Type:** `multipart/form-data`
- **请求参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| activity_name | string | 是 | 活动名称 |
| event_date | string | 是 | 活动日期（ISO格式） |
| file | File | 是 | 合照图片（JPG/PNG，最大10MB） |

- **后端处理流程:**
  1. 保存合照到 uploads/ 目录
  2. RetinaFace 检测所有人脸
  3. 对每个人脸提取 ArcFace 特征，与 face_feature 表逐一比对（阈值 0.55）
  4. DeepFace 情绪分析（复用 RetinaFace 检测结果）
  5. 保存活动记录和参与名单到 activity / activity_participant 表

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "activity_id": 1,
    "detected_count": 25,
    "recognized_count": 22,
    "participants": [
      {
        "bbox": [100, 200, 150, 280],
        "student_id": 1,
        "confidence": 0.92,
        "emotion": "happy"
      },
      {
        "bbox": [300, 250, 360, 340],
        "student_id": null,
        "confidence": 0.48,
        "emotion": "neutral"
      }
    ]
  }
}
```

- **说明:** `student_id` 为 null 表示未匹配到人脸库中的学生（相似度 < 0.55）

---

#### 2.5.2 获取活动列表

- **接口:** `GET /group/activities`
- **权限:** 教师
- **成功响应 (200):** 活动列表（含 activity_id, activity_name, event_date, participant_count）

---

#### 2.5.3 获取活动详情及参与名单

- **接口:** `GET /group/activities/{activity_id}`
- **权限:** 教师
- **路径参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| activity_id | integer | 活动ID |

- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "activity": {
      "activity_id": 1,
      "activity_name": "春游合影",
      "image_path": "./uploads/group_春游合影_2026-04-20.jpg",
      "event_date": "2026-04-20",
      "participant_count": 22
    },
    "participants": [
      {
        "student_no": "2023001",
        "name": "张三",
        "confidence": 0.92,
        "emotion": "happy"
      }
    ]
  }
}
```

---

#### 2.5.4 获取活动参与统计

- **接口:** `GET /group/statistics`
- **权限:** 教师
- **成功响应 (200):** 各学生活动参与次数统计，支持柱状图/折线图数据格式

---

### 2.6 情绪分析模块（/emotion）

#### 2.6.1 获取情绪统计

- **接口:** `GET /emotion/statistics`
- **权限:** 教师/学生（学生仅可查自己）
- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "distribution": {
      "happy": 45,
      "neutral": 30,
      "sad": 5,
      "surprise": 10,
      "angry": 3,
      "fear": 4,
      "disgust": 3
    }
  }
}
```

---

#### 2.6.2 获取情绪时间线

- **接口:** `GET /emotion/timeline`
- **权限:** 教师/学生（学生仅可查自己）
- **成功响应 (200):**

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "time": "2026-04-28T08:00:00",
      "emotion": "happy",
      "name": "张三"
    },
    {
      "time": "2026-04-28T14:00:00",
      "emotion": "neutral",
      "name": "张三"
    }
  ]
}
```

---

## 3. 数据流时序图

### 3.1 考勤流程

```
浏览器(前端)                          后端(FastAPI)                         数据库
    │                                      │                                    │
    ├─ GET /attendance/action-challenge ──>│                                    │
    │<─ 返回 challenge_id + action_type ───┤                                    │
    │                                      │                                    │
    ├─ WebRTC 开启摄像头 ─────────────────>│                                    │
    ├─ MediaPipe 动作检测(本地)            │                                    │
    ├─ 动作验证通过，采集单帧图像           │                                    │
    │                                      │                                    │
    ├─ POST /attendance/check (image) ────>│                                    │
    │                                      ├─ RetinaFace 人脸检测              │
    │                                      ├─ CDCN 纹理活体检测                 │
    │                                      ├─ DeepFace 情绪分析                 │
    │                                      ├─ ArcFace 特征提取                 │
    │                                      ├─ 查询 face_feature ───────────────>│
    │                                      │<─ 返回加密特征向量 ─────────────────┤
    │                                      ├─ AES解密 + 余弦相似度比对            │
    │                                      ├─ 写入 attendance 表 ──────────────>│
    │<─ 返回考勤结果 ──────────────────────┤                                    │
```

### 3.2 合照识别流程

```
浏览器(前端)                          后端(FastAPI)                         数据库
    │                                      │                                    │
    ├─ POST /group/upload (image) ────────>│                                    │
    │                                      ├─ RetinaFace 检测多人脸            │
    │                                      ├─ 对每个人脸：                      │
    │                                      │   ├─ ArcFace 提取特征              │
    │                                      │   ├─ 1:N 人脸库比对 ─────────────>│
    │                                      │   │                                │
    │                                      │   ├─ DeepFace 情绪分析             │
    │                                      ├─ 写入 activity 表 ────────────────>│
    │                                      ├─ 写入 activity_participant 表 ────>│
    │<─ 返回活动ID + 参与名单 ─────────────┤                                    │
```

---

## 4. 核心算法调用链

### 4.1 人脸检测 → 识别 → 比对

```python
# face_engine.py 调用链
FaceAnalysis.prepare()      # 加载 RetinaFace 模型
FaceAnalysis.get(image)     # 检测人脸 → 返回 [face1, face2, ...]
face.embedding              # ArcFace 提取 512 维特征向量
np.dot(v1, v2) / (norm1 * norm2)  # 余弦相似度计算
```

### 4.2 活体检测降级链

```python
# liveness_engine.py 运行时自动降级
优先级1: 加载 models/custom_live.pth （自研CNN）
  └─ 失败 ──> 优先级2: 加载 models/cdcn_live.pth （CDCN预训练）
                  └─ 失败 ──> 优先级3: Silent-Face-Anti-Spoofing 库
```

### 4.3 特征向量加密/解密

```python
# security.py AES-256-GCM 流程
加密: plaintext_bytes ──> AESGCM.encrypt(nonce, plaintext, None) ──> ciphertext(with tag)
      序列化: nonce(12B) + ciphertext

解密: encrypted_bytes ──> 拆分 nonce(12B) + ciphertext ──> AESGCM.decrypt(nonce, ciphertext, None) ──> plaintext
```

---

## 5. 环境变量配置说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| DATABASE_URL | sqlite:///./attendance.db | SQLite 数据库路径 |
| SECRET_KEY | change-me | JWT 签名密钥 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 60 | Token 过期时间（分钟） |
| FACE_FEATURE_KEY | change-me-32-byte-key!!! | AES-256-GCM 加密密钥（需32字节） |
| UPLOAD_DIR | ./uploads | 上传图片存储目录 |
| MODEL_DIR | ./models | 预训练模型权重目录 |
| FACE_SIMILARITY_THRESHOLD | 0.6 | 单人人脸识别相似度阈值 |
| GROUP_FACE_SIMILARITY_THRESHOLD | 0.55 | 合照人脸识别相似度阈值 |

---

*文档结束*
